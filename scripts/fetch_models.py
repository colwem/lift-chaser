"""Fetch GFS and HRRR straight from NOAA's open data buckets and build the map layers.

For each model in scripts/models.py:
  1. Pick the newest run whose last needed forecast hour is published (or --cycle).
  2. For each map hour, download only the needed GRIB2 fields, using the .idx file
     next to each GRIB2 file to request byte ranges. No key, no rate limit.
  3. Derive soaring fields: W* (thermal updraft velocity), boundary layer top,
     cumulus base, 850 and 700 hPa wind, soaring index, and so on.
  4. Reproject onto a grid whose rows are evenly spaced in Web Mercator, so the
     browser can lay each image straight onto the Leaflet map, and save each
     variable and hour as an 8-bit grayscale PNG (see OUT_VARS in models.py).
  5. Sample every operator's location for the per-site forecasts.

Outputs (under cache/models/, or cache/past/<model>_<cycle>/ with --cycle):
  index.json                          models, runs, hours, variables, ranges, image bounds
  <model>/<YYYYMMDDHH valid UTC>/<var>.png
  sites_<model>.json                  {fetched, model, cycle, sites: {op id: {tz, hourly: {...}}}}
  manifest.json                       what was fetched, errors

Nothing here is archived: NOAA keeps GFS (since 2021) and HRRR (since 2014) on AWS
and Google Cloud, so any past run can be rebuilt with --cycle.

Usage: python scripts/fetch_models.py [--model hrrr|gfs] [--cycle YYYYMMDDHH] [--hours N]
"""
import argparse, concurrent.futures as cf, datetime as dt, json, os, pathlib, re, shutil, sys, threading, time
import urllib.error, urllib.request
from zoneinfo import ZoneInfo

import eccodes
import numpy as np
from PIL import Image
from pyproj import Proj

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from models import MODELS, OUT_VARS, MAP_TZ, MAP_HOURS, site_tz

ROOT = pathlib.Path(__file__).resolve().parent.parent
UA = {"User-Agent": "chase-lift/0.2 (personal soaring planner)"}
WORKERS = int(os.environ.get("WORKERS", 8))
# Stop starting new forecast hours after this many seconds; finished hours are kept.
DEADLINE = time.monotonic() + float(os.environ.get("FETCH_BUDGET_S", 1800))
KT, FT, FPM = 1.943844, 3.28084, 196.85

manifest = {"started": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "ok": [], "errors": []}

def log(msg):
    print(msg, flush=True)

# ---------- download ----------

def http(url, rng=None, tries=4):
    headers = dict(UA)
    if rng:
        headers["Range"] = f"bytes={rng[0]}-{'' if rng[1] is None else rng[1]}"
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 404) or attempt == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == tries - 1:
                raise
        time.sleep(5 * (attempt + 1))

def read_idx(m, cycle, fhr):
    """Return (base URL, .idx lines) from the first mirror that has this file."""
    key = m["key"].format(c=cycle, f=fhr)
    last = None
    for base in m["bases"]:
        try:
            return f"{base}/{key}", http(f"{base}/{key}.idx").decode().splitlines()
        except Exception as e:
            last = e
    raise last

def byte_ranges(lines, patterns, optional=()):
    """Map each field name to the (start, end) byte range of the first .idx record matching it.
    Fields in `optional` may be missing (for example GFS has no time-averaged flux at hour 0)."""
    out = {}
    for name, pat in patterns.items():
        rx = re.compile(pat)
        for k, line in enumerate(lines):
            if rx.search(line):
                start = int(line.split(":")[1])
                end = int(lines[k + 1].split(":")[1]) - 1 if k + 1 < len(lines) else None
                out[name] = (start, end)
                break
        else:
            if name not in optional:
                raise KeyError(f"no .idx record matches {name} ({pat})")
    return out

DECODE_LOCK = threading.Lock()   # eccodes is not thread-safe; downloads stay parallel

def decode(blob):
    with DECODE_LOCK:
        return _decode(blob)

def _decode(blob):
    h = eccodes.codes_new_from_message(blob)
    try:
        vals = eccodes.codes_get_values(h).astype(np.float32)
        if eccodes.codes_get(h, "bitmapPresent"):
            vals[vals == eccodes.codes_get(h, "missingValue")] = np.nan
        keys = {}
        for k in ("gridType", "Nx", "Ny", "Ni", "Nj", "DxInMetres", "DyInMetres", "LaDInDegrees", "LoVInDegrees",
                  "Latin1InDegrees", "Latin2InDegrees", "latitudeOfFirstGridPointInDegrees",
                  "longitudeOfFirstGridPointInDegrees", "iDirectionIncrementInDegrees",
                  "jDirectionIncrementInDegrees", "jScansPositively", "radius"):
            try:
                keys[k] = eccodes.codes_get(h, k)
            except Exception:
                pass
        return vals, keys
    finally:
        eccodes.codes_release(h)

def fetch_hour(pool, m, cycle, fhr):
    url, lines = read_idx(m, cycle, fhr)
    ranges = byte_ranges(lines, m["fields"], m.get("optional", ()))
    futs = {name: pool.submit(lambda r=r: decode(http(url, r))) for name, r in ranges.items()}
    fields, grid = {}, None
    for name, fut in futs.items():
        fields[name], grid = fut.result()
    for name in m["fields"]:  # missing optional fields become "no data"
        if name not in fields:
            fields[name] = np.full_like(fields["t2"], np.nan)
    return fields, grid

# ---------- grids ----------

def make_mapper(g):
    """Return f(lat, lon) -> flat index into the native grid, -1 where outside it (nearest point)."""
    if g["gridType"] == "lambert":
        R = g.get("radius") or 6371229
        proj = Proj(proj="lcc", lat_1=g["Latin1InDegrees"], lat_2=g["Latin2InDegrees"], lat_0=g["LaDInDegrees"],
                    lon_0=g["LoVInDegrees"], a=R, b=R)
        x0, y0 = proj(g["longitudeOfFirstGridPointInDegrees"], g["latitudeOfFirstGridPointInDegrees"])
        nx, ny, dx, dy = g["Nx"], g["Ny"], g["DxInMetres"], g["DyInMetres"]
        sign = 1 if g["jScansPositively"] else -1
        def f(lat, lon):
            x, y = proj(lon, lat)
            i = np.rint((x - x0) / dx).astype(np.int64)
            j = np.rint(sign * (y - y0) / dy).astype(np.int64)
            ok = (i >= 0) & (i < nx) & (j >= 0) & (j < ny)
            return np.where(ok, j * nx + i, -1)
        return f
    if g["gridType"] == "regular_ll":
        ni, nj = g["Ni"], g["Nj"]
        lat0, lon0 = g["latitudeOfFirstGridPointInDegrees"], g["longitudeOfFirstGridPointInDegrees"]
        di, dj = g["iDirectionIncrementInDegrees"], g["jDirectionIncrementInDegrees"]
        sign = 1 if g["jScansPositively"] else -1
        def f(lat, lon):
            i = np.rint(((np.asarray(lon) - lon0) % 360) / di).astype(np.int64) % ni
            j = np.rint(sign * (np.asarray(lat) - lat0) / dj).astype(np.int64)
            ok = (j >= 0) & (j < nj)
            return np.where(ok, j * ni + i, -1)
        return f
    raise ValueError(f"unsupported grid {g['gridType']}")

def mercator_grid(out):
    """Pixel-centre lat/lon for an image whose rows are evenly spaced in Web Mercator y."""
    (w, e), (s, n), d = out["lon"], out["lat"], out["dlon"]
    width = int(round((e - w) / d))
    y = lambda lat: np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))
    ys, yn = y(s), y(n)
    height = int(round((yn - ys) / np.radians(d)))
    lons = w + (np.arange(width) + 0.5) * (e - w) / width
    yc = yn - (np.arange(height) + 0.5) * (yn - ys) / height        # row 0 is the north edge
    lats = np.degrees(2 * np.arctan(np.exp(yc)) - np.pi / 2)
    LAT, LON = np.meshgrid(lats, lons, indexing="ij")
    return LAT, LON, width, height

# ---------- derived fields ----------

def clip01(a):
    return np.clip(a, 0, 1)

def thermal_score(blh_ft, low, prate, cape):
    """Soaring index, 0 to 10. Same formula as thermalScore() in site/template.html.
    Rain uses the model precipitation rate (mm/h): the NOAA models give a rate, not a probability."""
    s = clip01((blh_ft - 1500) / 5000) * 10
    s = s * (1 - clip01((low - 30) / 60) * 0.7)
    s = s * (1 - clip01((prate - 0.1) / 1.0) * 0.8)
    return np.where(cape > 1500, s * 0.7, s)

def wind(u, v):
    speed = np.hypot(u, v) * KT
    frm = (np.degrees(np.arctan2(-u, -v)) + 360) % 360     # meteorological: direction the wind comes FROM
    return speed, frm

def derive(F):
    T, Td, H, zi = F["t2"], F["d2"], F["shtfl"], F["hpbl"]
    rho = F["pres"] / (287.05 * T)
    # W* = (g / T * H / (rho * c_p) * z_i)^(1/3); no thermals when the surface is not heating the air
    wstar = np.cbrt(np.where(H > 0, 9.81 / T * H / (rho * 1005.0) * zi, 0.0))
    wstar[np.isnan(H)] = np.nan   # flux not available (GFS hour 0): unknown, not zero
    w850, d850 = wind(F["u850"], F["v850"])
    w700, _ = wind(F["u700"], F["v700"])
    prate = F["prate"] * 3600.0
    blh = zi * FT
    out = {
        "wstar": wstar * FPM,
        "blh": blh,
        "cbase": np.maximum(0, T - Td) * 400.0,            # spread rule: 400 ft per deg C
        "w850": w850, "d850": d850, "w700": w700,
        "gust": F["gust"] * KT,
        "cape": F["cape"], "li": F["lftx"],
        "low": F["lcdc"], "tcdc": F["tcdc"], "prate": prate,
    }
    out["score"] = thermal_score(blh, F["lcdc"], prate, F["cape"])
    site = {  # per-site forecast values, named like Open-Meteo so the page code can read either
        "boundary_layer_height": zi, "temperature_2m": T - 273.15, "dew_point_2m": Td - 273.15,
        "cape": F["cape"], "lifted_index": F["lftx"], "cloud_cover_low": F["lcdc"], "cloud_cover": F["tcdc"],
        "precipitation": prate, "wind_speed_850hPa": w850, "wind_direction_850hPa": d850,
        "wind_speed_700hPa": w700, "wind_gusts_10m": F["gust"] * KT, "wstar": wstar,
    }
    return out, site

def encode(a, var):
    lo, hi = OUT_VARS[var]["lo"], OUT_VARS[var]["hi"]
    b = np.rint((a - lo) / (hi - lo) * 254)
    b = np.clip(np.nan_to_num(b, nan=255), 0, 255).astype(np.uint8)
    b[np.isnan(a)] = 255
    return b

# ---------- hours ----------

def map_hours(m, cycle):
    """(valid UTC time, forecast hour) for every map hour this run covers."""
    tz = ZoneInfo(MAP_TZ)
    first = cycle.astimezone(tz).date()
    out = []
    for d in range(m["days"] + 1):
        day = first + dt.timedelta(days=d)
        for h in MAP_HOURS:
            valid = dt.datetime(day.year, day.month, day.day, h, tzinfo=tz).astimezone(dt.timezone.utc)
            fhr = int((valid - cycle).total_seconds() // 3600)
            if valid >= cycle and fhr <= m["max_fhr"] and m["has_fhr"](fhr):
                out.append((valid, fhr))
    return out

def newest_cycle(m):
    """Newest run whose last needed forecast hour is already published."""
    now = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    for back in range(0, 49):
        c = now - dt.timedelta(hours=back)
        if c.hour not in m["cycles"]:
            continue
        hours = map_hours(m, c)
        if not hours:
            continue
        try:
            read_idx(m, c, hours[-1][1])
            return c
        except Exception:
            continue
    raise RuntimeError("no complete run found in the last 48 h")

# ---------- main per model ----------

def build_model(name, cycle, out_root, max_hours=None):
    m = MODELS[name]
    cycle = cycle or newest_cycle(m)
    hours = map_hours(m, cycle)[:max_hours]
    log(f"{name}: run {cycle:%Y-%m-%d %HZ}, {len(hours)} map hours")
    LAT, LON, width, height = mercator_grid(m["out"])
    ops = [o for o in json.loads((ROOT / "data/operators.json").read_text()) if o["rental"] != "CLOSED"]
    model_dir = out_root / name
    tmp_dir = out_root / f".{name}.new"
    shutil.rmtree(tmp_dir, ignore_errors=True)
    done, site_rows, pix, site_idx = [], [], None, None
    with cf.ThreadPoolExecutor(WORKERS) as pool:
        for valid, fhr in hours:
            if time.monotonic() > DEADLINE:
                manifest["errors"].append(f"{name}: time budget used up after {len(done)} of {len(hours)} hours")
                break
            t0 = time.time()
            F, grid = fetch_hour(pool, m, cycle, fhr)
            if pix is None:
                mapper = make_mapper(grid)
                pix = mapper(LAT, LON)
                site_idx = mapper(np.array([o["lat"] for o in ops]), np.array([o["lon"] for o in ops]))
            out, site = derive(F)
            vdir = tmp_dir / f"{valid:%Y%m%d%H}"
            vdir.mkdir(parents=True, exist_ok=True)
            def write(var, a=None):
                img = np.where(pix >= 0, out[var].ravel()[np.maximum(pix, 0)], np.nan)
                Image.fromarray(encode(img, var), "L").save(vdir / f"{var}.png", compress_level=9)
            list(pool.map(write, OUT_VARS))
            site_rows.append((valid, {k: np.where(site_idx >= 0, v.ravel()[np.maximum(site_idx, 0)], np.nan) for k, v in site.items()}))
            done.append((valid, fhr))
            log(f"  {name} f{fhr:03d} valid {valid:%m-%d %HZ}: {time.time() - t0:.1f} s")
    if not done:
        raise RuntimeError(f"{name}: no hours fetched")
    # swap the new images in only after the run finished, so a failure never leaves a half-written model
    shutil.rmtree(model_dir, ignore_errors=True)
    tmp_dir.rename(model_dir)

    fetched = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    sites = {}
    for k, o in enumerate(ops):
        tz = site_tz(o)
        hourly = {"time": [v.astimezone(ZoneInfo(tz)).strftime("%Y-%m-%dT%H:00") for v, _ in site_rows]}
        for var in site_rows[0][1]:
            hourly[var] = [None if np.isnan(r[var][k]) else round(float(r[var][k]), 2) for _, r in site_rows]
        sites[o["id"]] = {"tz": tz, "hourly": hourly}
    (out_root / f"sites_{name}.json").write_text(json.dumps(
        {"fetched": fetched, "model": m["label"], "cycle": cycle.isoformat(), "sites": sites}, separators=(",", ":")))

    (s, n), (w, e) = m["out"]["lat"], m["out"]["lon"]
    return {"label": m["label"], "note": m["note"], "cycle": cycle.isoformat(), "fetched": fetched,
            "bounds": [[s, w], [n, e]], "width": width, "height": height,
            "hours": [v.strftime("%Y%m%d%H") for v, _ in done], "path": f"{name}/{{hour}}/{{var}}.png",
            "sites": f"sites_{name}.json"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=list(MODELS), action="append", help="default: all models")
    ap.add_argument("--cycle", help="rebuild a past run, YYYYMMDDHH (UTC); written under cache/past/")
    ap.add_argument("--hours", type=int, help="only the first N map hours (for testing)")
    a = ap.parse_args()
    cycle = dt.datetime.strptime(a.cycle, "%Y%m%d%H").replace(tzinfo=dt.timezone.utc) if a.cycle else None
    out_root = ROOT / "cache" / ("past/" + a.cycle if a.cycle else "models")
    out_root.mkdir(parents=True, exist_ok=True)
    idx_path = out_root / "index.json"
    index = json.loads(idx_path.read_text()) if idx_path.exists() else {"models": {}}
    index["vars"] = OUT_VARS
    for name in a.model or list(MODELS):
        try:
            index["models"][name] = build_model(name, cycle, out_root, a.hours)
            manifest["ok"].append(name)
        except Exception as e:  # keep the previous files and index entry for this model
            manifest["errors"].append(f"{name}: {e!r}")
            log(f"ERROR {name}: {e!r}")
    # A model whose images are not on disk (it failed on a fresh runner) must not stay in the index,
    # or the page would ask for missing files; the page then uses the other model.
    for name in list(index["models"]):
        if not (out_root / name).is_dir():
            del index["models"][name]
    index["generated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    idx_path.write_text(json.dumps(index, indent=1))
    manifest["finished"] = index["generated"]
    (out_root / "manifest.json").write_text(json.dumps(manifest, indent=1))
    log(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in manifest.items()}))
    sys.exit(1 if manifest["errors"] and not manifest["ok"] else 0)

if __name__ == "__main__":
    main()
