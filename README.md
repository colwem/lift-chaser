# Chase-Lift

Personal soaring-trip planner: site register, global glider list, and forecast map. See BACKLOG.md for what is planned and CLAUDE.md for the full handoff and data schema.

**Live site: https://lift-chaser.pages.dev**

## Where the forecasts come from

1. **NOAA HRRR** (High-Resolution Rapid Refresh, 3 km, days 1 and 2) and **NOAA GFS** (Global Forecast System, 25 km, days 1 to 7), downloaded by `scripts/fetch_models.py` straight from NOAA's open data buckets on AWS, with Google Cloud as a fallback. Only the needed fields are downloaded, using the `.idx` index next to each GRIB2 file. No key, no rate limit.
1. From those fields the job derives W* (thermal updraft velocity), boundary layer top, cumulus base, 850 and 700 hPa wind, the soaring index, and more. It writes one 8-bit PNG per variable and hour (`cache/models/`) plus per-site forecasts.
1. Open-Meteo (`scripts/fetch_forecasts.py`) is kept only as a fallback while the NOAA pipeline proves itself.

Nothing is archived: NOAA keeps GFS (since 2021) and HRRR (since 2014), so any past run can be rebuilt with `python scripts/fetch_models.py --cycle YYYYMMDDHH`. The only thing kept is a one-line-per-run log on the `archive` branch (`runs.jsonl`).

## How it is deployed

1. A GitHub Actions job (`.github/workflows/update-forecasts.yml`) runs 4 times a day (02:30, 08:30, 14:30 and 20:30 UTC, each about 2.5 h after an HRRR 48 h run), on every push to `main` that touches data, scripts or the page, and on demand (repo > Actions > update-forecasts > Run workflow).
1. It fetches forecasts into `cache/`, builds `site/index.html`, and uploads both to the Cloudflare Pages project `lift-chaser`.
1. Cloudflare serves the result as static files. If every model fetch fails, nothing is deployed and the site keeps its last version, which the page marks stale after 12 h. The build stamp under the page title shows which commit is live.

Repo secrets needed: `CLOUDFLARE_API_TOKEN` (Account > Cloudflare Pages > Edit) and `CLOUDFLARE_ACCOUNT_ID`.

## Run it locally (Windows)

Needs Python 3.12. `pip install -r requirements.txt` for the NOAA pipeline (eccodes, numpy, pillow, pyproj). The workbook and PDF builders in `legacy/` also need `openpyxl` and `reportlab`.

If `python` opens the Microsoft Store, turn off the aliases in Settings > Apps > Advanced app settings > App execution aliases (`python.exe` and `python3.exe`), or use `py` instead.

1. Build the page from `data/*.json`:
   `python scripts/build_site.py`
1. Serve the repo root and open http://localhost:8000/site/index.html:
   `python -m http.server 8000 --bind 127.0.0.1`
   In Claude Code, the `site` entry in `.claude/launch.json` does the same.
1. Fill `cache/` with forecasts (about 4 minutes, about 270 MB):
   `python scripts/fetch_models.py`
   Options: `--model hrrr` or `--model gfs` for one model, `--hours 2` for a quick test, `--cycle YYYYMMDDHH` to rebuild a past run into `cache/past/`.
1. Optional, the Open-Meteo fallback: `python scripts/fetch_forecasts.py`. Add `--rasp` to also fetch GBSC RASP, but only after Steve Paavola has agreed to automated fetches (on hold).

`site/index.html` also works when opened straight from disk, because the site data is inlined at build time; forecasts then come live from Open-Meteo.

## What needs no key

Everything the page uses today is free and keyless: NOAA model data, Esri and USGS basemaps, IEM (Iowa Environmental Mesonet) radar and satellite, and the Open-Meteo fallback. `cache/` is git-ignored and regenerated on each run.
