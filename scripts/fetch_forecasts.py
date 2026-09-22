"""Fetch and cache soaring forecasts for every active site.

The Open-Meteo part was tested live on 2026-09-22. The RASP part (only run with
--rasp) is still untested: it was written from the SoaringForecast Android app
source (github.com/efoertsch/SoaringForecast, MIT). Inspect cache/rasp and fix
field names before trusting it.

Open-Meteo's free tier counts every location in a multi-point request as one
call and allows 600 calls a minute, 5,000 an hour and 10,000 a day. One run
fetches about 1,600 points, so requests are paced to OM_POINTS_PER_MIN.

Outputs (all under cache/):
  rasp/current.json                     GBSC RASP index (regions, dates, soundings)
  rasp/<region>/<date>/status.json      models, corners, times per date
  rasp/<region>/<date>/<model>/<param>.<HHMM>local.d2.body.png   (selected params)
  rasp_points/<site>.json               blipspot text per site / date / time
  openmeteo/sites.json                  {fetched, sites: {op id: Open-Meteo response}}, hourly GFS, 7 days
  openmeteo/grid_<region>.json          {fetched, R, pts, time, vars}: GFS grid for the map field,
                                        daytime hours only, one value list per variable per point
  manifest.json                         what was fetched, when, errors
"""
import json, pathlib, sys, time, datetime as dt, urllib.error, urllib.request, urllib.parse

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
OM_POINTS_PER_MIN = 450  # stay under Open-Meteo's 600 locations a minute
# Map grids; keep in step with REGIONS in site/template.html (the page reads R and pts from the file).
GRIDS = {"ne": {"la": [39.5, 47], "lo": [-80, -67], "s": .5},
         "east": {"la": [29, 47], "lo": [-90, -67], "s": 1},
         "conus": {"la": [25, 49], "lo": [-124.5, -67], "s": 1.5}}
GRID_HOURS = range(8, 20)  # local hours the page's hour slider covers

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

def now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def openmeteo(points, tz, label):
    """Hourly GFS for a list of (lat, lon), in batches of 50, paced and retried on HTTP 429."""
    out = []
    for i in range(0, len(points), 50):
        ch = points[i:i + 50]
        q = urllib.parse.urlencode(dict(latitude=",".join(f"{la:.3f}" for la, _ in ch),
                                        longitude=",".join(f"{lo:.3f}" for _, lo in ch),
                                        hourly=OM_VARS, wind_speed_unit="kn", forecast_days=7, timezone=tz))
        url = f"https://api.open-meteo.com/v1/gfs?{q}"
        for attempt in range(3):
            try:
                res = get(url); break
            except urllib.error.HTTPError as e:
                if e.code != 429 or attempt == 2:
                    raise
                time.sleep(65)  # minute limit hit; wait for the window to roll over
        j = json.loads(res)
        out += j if isinstance(j, list) else [j]
        print(f"  {label}: {min(i + 50, len(points))}/{len(points)} points", flush=True)
        time.sleep(len(ch) * 60 / OM_POINTS_PER_MIN)
    return out

def fetch_openmeteo_sites():
    ops = [o for o in json.loads((ROOT / "data/operators.json").read_text()) if o["rental"] != "CLOSED"]
    res = openmeteo([(o["lat"], o["lon"]) for o in ops], "auto", "sites")
    save("openmeteo/sites.json", json.dumps({"fetched": now_iso(), "model": "GFS",
                                              "sites": {o["id"]: r for o, r in zip(ops, res)}}))

def fetch_openmeteo_grid(name, R):
    pts = []
    la = R["la"][0]
    while la <= R["la"][1] + 1e-6:
        lo = R["lo"][0]
        while lo <= R["lo"][1] + 1e-6:
            pts.append([round(la, 3), round(lo, 3)]); lo += R["s"]
        la += R["s"]
    res = openmeteo(pts, "America/New_York", f"grid {name}")
    times = res[0]["hourly"]["time"]
    keep = [i for i, t in enumerate(times) if int(t[11:13]) in GRID_HOURS]
    rnd = lambda v: None if v is None else round(v, 1)
    grid = {"fetched": now_iso(), "model": "GFS", "tz": "America/New_York", "R": R, "pts": pts,
            "time": [times[i] for i in keep],
            "vars": {v: [[rnd(r["hourly"][v][i]) for i in keep] for r in res] for v in OM_VARS.split(",")}}
    save(f"openmeteo/grid_{name}.json", json.dumps(grid, separators=(",", ":")))

if __name__ == "__main__":
    step("open-meteo sites", fetch_openmeteo_sites)
    for name, R in GRIDS.items():
        step(f"open-meteo grid {name}", lambda: fetch_openmeteo_grid(name, R))
    # RASP is opt-in until Steve Paavola (GBSC) has agreed to automated fetches; see CLAUDE.md.
    if "--rasp" in sys.argv:
        fetch_rasp()
    manifest["finished"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    save("manifest.json", json.dumps(manifest, indent=1))
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in manifest.items()}, indent=1))
