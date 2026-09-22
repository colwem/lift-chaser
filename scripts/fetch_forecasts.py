"""Fetch and cache soaring forecasts for every active site.

UNTESTED against the live servers: written 2026-09-22 from the SoaringForecast
Android app source (github.com/efoertsch/SoaringForecast, MIT) and the Open-Meteo
docs. The cloud sandbox that wrote this could not reach soargbsc.net or
api.open-meteo.com. Run it, inspect cache/, and fix field names before trusting it.

Outputs (all under cache/):
  rasp/current.json                     GBSC RASP index (regions, dates, soundings)
  rasp/<region>/<date>/status.json      models, corners, times per date
  rasp/<region>/<date>/<model>/<param>.<HHMM>local.d2.body.png   (selected params)
  rasp_points/<site>.json               blipspot text per site / date / time
  openmeteo/sites.json                  hourly GFS per site (all regions)
  manifest.json                         what was fetched, when, errors
"""
import json, pathlib, sys, time, datetime as dt, urllib.request, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache"
# Add a contact address here once you decide which one to publish to these servers.
UA = {"User-Agent": "chase-lift/0.1 (personal soaring planner)"}
RASP_PARAMS_IMG = ["wstar_bsratio", "hglider", "zsfclclmask", "blwind", "wind850", "press850"]
RASP_PARAMS_POINT = "wstar bsratio hglider zsfclcl zsfclcldif zblcl blwind bltopwind sfcwind wind850 rain1 cape"
RASP_TIMES = ["1000", "1200", "1400", "1600"]
OM_VARS = ("boundary_layer_height,temperature_2m,dew_point_2m,cape,lifted_index,cloud_cover_low,"
           "precipitation_probability,wind_speed_850hPa,wind_direction_850hPa,wind_gusts_10m")
PAUSE = 1.0  # seconds between requests to other people's servers; be polite

manifest = {"started": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "ok": [], "errors": []}

def get(url, data=None):
    req = urllib.request.Request(url, data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def save(path, blob):
    p = CACHE / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(blob if isinstance(blob, bytes) else blob.encode())

def step(label, fn):
    try:
        out = fn(); manifest["ok"].append(label); return out
    except Exception as e:  # keep going; one dead source must not kill the run
        manifest["errors"].append(f"{label}: {e!r}"); return None
    finally:
        time.sleep(PAUSE)

def fetch_rasp():
    ops = {o["id"]: o for o in json.loads((ROOT / "data/operators.json").read_text())}
    for region, src in json.loads((ROOT / "data/rasp_sources.json").read_text()).items():
        base = src["base"].rstrip("/")
        cur = step(f"rasp current {region}", lambda: get(f"{base}/current.json"))
        if not cur:
            continue
        save("rasp/current.json", cur)
        cur_j = json.loads(cur)
        # current.json shape (from app model Regions.java): {"regions":[{"name":..,"dates":[..],"soundings":[..]}]}
        reg = next((r for r in cur_j.get("regions", []) if r.get("name") == region), None)
        for date in (reg or {}).get("dates", [])[:3]:
            st = step(f"rasp status {region} {date}", lambda: get(f"{base}/{region}/{date}/status.json"))
            if not st:
                continue
            save(f"rasp/{region}/{date}/status.json", st)
            models = [m.get("name") for m in json.loads(st).get("models", [])] or ["gfs"]
            model = models[0]
            for t in RASP_TIMES:
                for p in RASP_PARAMS_IMG:
                    rel = f"{region}/{date}/{model}/{p}.{t}local.d2.body.png"
                    img = step(f"rasp img {rel}", lambda: get(f"{base}/{rel}"))
                    if img:
                        save(f"rasp/{rel}", img)
            for sid in src["sites"]:
                o = ops.get(sid)
                if not o or o["rental"] == "CLOSED":
                    continue
                for t in RASP_TIMES:
                    body = urllib.parse.urlencode(dict(region=region, date=date, model=model, time=t,
                                                       lat=o["lat"], lon=o["lon"], param=RASP_PARAMS_POINT)).encode()
                    txt = step(f"rasp point {sid} {date} {t}",
                               lambda: get(f"{base}/cgi/get_rasp_blipspot.cgi", data=body))
                    if txt:
                        f = CACHE / f"rasp_points/{sid}.json"
                        cur_pts = json.loads(f.read_text()) if f.exists() else {}
                        cur_pts.setdefault(date, {})[t] = txt.decode("utf-8", "replace")
                        save(f"rasp_points/{sid}.json", json.dumps(cur_pts, indent=1))

def fetch_openmeteo():
    ops = [o for o in json.loads((ROOT / "data/operators.json").read_text()) if o["rental"] != "CLOSED"]
    out = {}
    for i in range(0, len(ops), 50):
        ch = ops[i:i + 50]
        q = urllib.parse.urlencode(dict(latitude=",".join(f"{o['lat']:.3f}" for o in ch),
                                        longitude=",".join(f"{o['lon']:.3f}" for o in ch),
                                        hourly=OM_VARS, wind_speed_unit="kn", forecast_days=7, timezone="auto"))
        res = step(f"open-meteo batch {i}", lambda: get(f"https://api.open-meteo.com/v1/gfs?{q}"))
        if res:
            j = json.loads(res); j = j if isinstance(j, list) else [j]
            for o, r in zip(ch, j):
                out[o["id"]] = r
    save("openmeteo/sites.json", json.dumps(out))

if __name__ == "__main__":
    fetch_openmeteo()
    # RASP is opt-in until Steve Paavola (GBSC) has agreed to automated fetches; see CLAUDE.md.
    if "--rasp" in sys.argv:
        fetch_rasp()
    manifest["finished"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    save("manifest.json", json.dumps(manifest, indent=1))
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in manifest.items()}, indent=1))
