# Chase-Lift

Personal soaring-trip planner: site register, global glider list, and forecast map. See CLAUDE.md for the full handoff, data schema and backlog.

**Live site: https://lift-chaser.pages.dev**

## How it is deployed

1. A GitHub Actions job (`.github/workflows/update-forecasts.yml`) runs at 06:15, 12:15 and 18:15 Eastern, on every push to `main` that touches data, scripts or the page, and on demand (repo > Actions > update-forecasts > Run workflow).
1. It fetches forecasts into `cache/`, builds `site/index.html`, and uploads both to the Cloudflare Pages project `lift-chaser`.
1. Cloudflare serves the result as static files. If a fetch fails, the previous forecast is kept, and the page marks it stale after 12 h.

Repo secrets needed: `CLOUDFLARE_API_TOKEN` (Account > Cloudflare Pages > Edit) and `CLOUDFLARE_ACCOUNT_ID`.

## Run it locally (Windows)

Needs Python 3.12. The core scripts use only the standard library. The workbook and PDF builders in `legacy/` also need `openpyxl` and `reportlab`.

If `python` opens the Microsoft Store, turn off the aliases in Settings > Apps > Advanced app settings > App execution aliases (`python.exe` and `python3.exe`), or use `py` instead.

1. Build the page from `data/*.json`:
   `python scripts/build_site.py`
1. Serve the repo root and open http://localhost:8000/site/index.html:
   `python -m http.server 8000 --bind 127.0.0.1`
   In Claude Code, the `site` entry in `.claude/launch.json` does the same.
1. Optional, fill `cache/` with forecasts:
   `python scripts/fetch_forecasts.py`
   This fetches Open-Meteo only. Add `--rasp` to also fetch GBSC RASP, but only after Steve Paavola has agreed to automated fetches (see CLAUDE.md).

`site/index.html` also works when opened straight from disk, because the data is inlined at build time.

## What needs no key

Everything the page uses today is free and keyless: Esri and USGS basemaps, IEM (Iowa Environmental Mesonet) radar and satellite, and Open-Meteo forecasts. `cache/` is git-ignored and regenerated on each fetch.
