# Chase-Lift: handoff for Claude Code

Written 2026-09-22 by Claude (Cowork session) for Claude Code to take over. Read this whole file before changing anything.

## What this is

A personal soaring-trip planner for Martin (GBSC member, pre-solo glider student, lives in Newton MA). Every Wednesday or Thursday he checks the forecast and decides where to fly on Saturday or Sunday. He gets there either by camper van (up to about 4 hours on a Friday evening) or by a cheap Friday-night nonstop flight from BOS (under about $300 round trip, landing by about midnight local).

The product has three parts:

1. **Site register.** Every soaring operator in range: contacts, rental procedure for a visiting licensed pilot, costs, and access time.
1. **Global glider list.** Every glider at those operators, with registration and who may fly it, joined to a glider type table (glide ratio, speeds, span, cockpit size).
1. **Map website.** Weather layers Martin can switch between, with the sites as a clickable overlay. Clicking a site shows its info, its full fleet with performance figures, and that site's forecast.

The target is a hosted static website. A scheduled job fetches and caches forecasts (RASP where someone already runs it, a model-derived index elsewhere). A slower scheduled job keeps the operator and fleet data current.

## About Martin (read before writing anything for him)

- He is an engineer who wants full technical depth. Spell out each acronym in parentheses on first use, define each variable, and briefly define soaring terms of art.
- For documents he will maintain by hand, do not use em dashes, manual column alignment, hand-maintained indentation, or hand-typed list numbers. Use markdown auto-numbering (`1.` on every item).
- He wants real files he can open outside Claude. Tables must fit the page width.
- He likes tables; if one is unreadable, fix the formatting rather than dropping it.
- For research, he wants many searches with varied phrasing and full-page reads, not a summary of the obvious top hits.
- **He is very tall.** Cockpit size is a first-class filter. He flies GBSC's ASK-21 K1 (an earlier note that he did not fit an ASK-21 was wrong; Martin, 2026-09-24). Roomier types: Schweizer 2-33 and 2-32, LET L-23 Super Blanik and L-13, Grob G103 (depends on proportions), Grob G102, DG-505, PW-6 front seat, ASK-13.
- Home club: Greater Boston Soaring Club (GBSC), Sterling MA (3B3).
- Scope decision: focus on **solo rental by a licensed visiting pilot**, meaning after he earns his Private Pilot Glider certificate. Instruction-only options are secondary.

## Current state

| Path | What it is | Status |
|---|---|---|
| `data/operators.json` | 52 operators with lat/lon, access, rental category, procedure, costs, contacts, sources | Researched 2026-09-22 by four parallel web-research agents; see caveats |
| `data/fleet.json` | 178 fleet rows (op, model, reg, seats, rate, who, note, type) | Many N-numbers missing ("") |
| `data/glider_types.json` | 34 glider types: SI units (ld, v_ld km/h, sink m/s, vne km/h, span m), cockpit, approx flag | Nominal figures; `approx: true` rows need checking |
| `data/flights.json` | Friday-evening nonstop tiers from BOS | KAYAK route-page ranges, Sept 2026 |
| `data/ridge_sites.json` | Working wind direction and half-width for ridge sites | Heuristic guesses, refine |
| `data/rasp_sources.json` | Known RASP servers and which sites they cover | Only GBSC NewEngland wired |
| `site/template.html` | Leaflet map app; `__OPS__`, `__FLEET__`, `__TYPES__`, `__RASP__` placeholders | Working (tested with mocked network) |
| `scripts/build_site.py` | Inlines data into template, writes `site/index.html` | Working |
| `scripts/fetch_forecasts.py` | Fetches GBSC RASP (index, status, images, point forecasts) and Open-Meteo per site into `cache/` | **Untested against live servers** |
| `.github/workflows/update-forecasts.yml` | Draft cron plus GitHub Pages deploy | Draft, never run |
| `collector/ogn_tracks.py` | Saves the club ships' OGN (Open Glider Network) tracks from FlightBook as IGC files, one per flight, within OGN's 24 h window; watch list in `data/martin.json` | Working, tested live 2026-09-24; see `docs/ogn-tracks.md` |
| `collector/ogn_aprs.py` | Fallback logger on the raw OGN APRS feed for the same ships; needs an always-on machine | Login and parsing tested 2026-09-24; not deployed |
| `data/martin.json` | Martin's personal file: `ogn_watch` (tracker addresses, airfields) and a reserved `my_flights` list. Research jobs must never edit it | In use |
| `scripts/install_ogn_task.ps1` | Registers the Windows task "chase-lift OGN tracks" (07:30, 13:00, 21:00, runs when the laptop wakes if missed) | Registered on Martin's laptop 2026-09-24 |
| `.github/workflows/ogn-tracks.yml` | The same download twice a day on GitHub, uploaded to a Cloudflare R2 bucket (never to the repo) | Waits for the R2 bucket and the `OGN_R2_BUCKET` repo variable |
| `legacy/` | Original Python data modules and the builders for the xlsx workbook and PDF report delivered to Martin, plus those two deliverables | Reference; the JSON in `data/` is now the source of truth |

### How the map works today

- Leaflet 1.9.4 from cdnjs.
- Basemaps: Esri Light Gray (default), USGS Topo, Esri Topo, Esri Shaded Relief, Esri Imagery.
- Live overlays: NEXRAD (Next Generation Weather Radar) base reflectivity tiles and GOES-East (Geostationary Operational Environmental Satellite) visible and IR (infrared) WMS (Web Map Service) layers, all from Iowa Environmental Mesonet (IEM).
- Forecast field: the browser pulls the GFS (Global Forecast System) model from Open-Meteo over a lat/lon grid and draws colored rectangles. Variables:
  - boundary layer height
  - estimated cumulus base, taken as (T minus Td) x 400 ft, where T is the 2 m temperature and Td the 2 m dew point in deg C
  - 850 hPa wind with arrows
  - gusts
  - CAPE (Convective Available Potential Energy)
  - lifted index
  - low cloud
  - precipitation probability
  - a heuristic soaring index
- Per-site forecast: Open-Meteo with `timezone=auto`, reduced to an 11:00 to 17:00 local window. It feeds the ranked "best sites" list and the popups.
- Clicking a site opens a right-hand drawer: operator info, then a fleet table joined to type data (L/D, best-glide speed in kt, min sink in fpm, Vne in kt, span, cockpit note).
- The sidebar "Glider list" is the global glider list. It can be filtered by the visible sites, by visitor access and by text, and sorted by L/D or min sink.

### Known issues

1. **"API KEY REQUIRED" tiles.** Martin opened the first version from disk and saw this across the map. The default basemap was CARTO `light_all`. It has been replaced with Esri and USGS ArcGIS tile services that need no key, but **this has not been confirmed in his browser**. If it recurs, find the layer responsible by toggling basemaps. Once hosted over https with a Referer header, OSM and CARTO tiles become usable again.
1. `fetch_forecasts.py` has never reached the live servers. The cloud sandbox had no route to soargbsc.net or api.open-meteo.com.
1. Grid forecast is fetched live from the browser: 50 points per request, up to about 700 points. This should move to the cache.
1. The soaring index is a rough sort, not a forecast.
   - Thermal part: boundary layer depth of 1,500 ft AGL scores 0, rising to full marks at 6,500 ft. It is then reduced for low cloud, rain probability and CAPE above 1,500.
   - Ridge part: 850 hPa wind of 12 to 35 kt within the site's half-width of its working direction.
   - It saturates at 10 too easily for ridge sites.
1. Drive-time rings are straight-line circles from Newton, not isochrones.
1. The fleet can be wrong: clubs sell and add gliders, and several fleet pages were blocked during research. Registration numbers came from FAA (Federal Aviation Administration) registry owner-name searches where possible.
1. Glider type numbers are nominal. Rows marked `approx` came from memory or secondary sources.

## RASP: what exists and how to read it

RASP (Regional Atmospheric Soaring Prediction, Dr. Jack Glendening's WRF-based package; WRF = Weather Research and Forecasting model) produces BLIPMAPs (Boundary Layer Information Prediction MAPs). We do not run RASP. We read other people's runs, cache them, and credit them.

### GBSC RASP (New England): primary source

- Operator: Steve Paavola, Greater Boston Soaring Club. Web UI at https://www.soargbsc.net/rasp/ (older host `soargbsc.com`).
- Regions: `NewEngland` (always generated) and `Mifflin` (central PA, may be discontinued).
- The endpoints below come from the open-source SoaringForecast app (github.com/efoertsch/SoaringForecast, MIT license; `SoaringForecastApi.java`, `AppRepository.java`):
  1. `GET /rasp/current.json`: regions, available dates, sounding locations.
  1. `GET /rasp/{region}/{yyyy-mm-dd}/status.json`: models available (gfs, nam, rap), lat/lon corners, and forecast times.
  1. `GET /rasp/{region}/{date}/{model}/{param}.{HHMM}local.d2.{body|head|foot|side}.png`: map images. `body` is the map; `head`, `foot` and `side` hold the title and color scales. An older pattern `{param}.curr.{HHMM}lst.d2.body.png` also appears in that code.
  1. `GET /rasp/{region}/{date}/{model}/sounding{N}.{HHMM}local.d2.png`: Skew-T soundings for the locations in `current.json`.
  1. `POST /rasp/cgi/get_rasp_blipspot.cgi` with form fields `region`, `date`, `model`, `time`, `lat`, `lon` and `param` (space-separated list): a text point forecast. **This is the best way to get per-site numbers.**
- Parameter names are in the app's `app/src/main/res/raw/forecast_options_json`. The useful ones:
  - `wstar` (thermal updraft velocity W*)
  - `bsratio` (buoyancy/shear ratio)
  - `wstar_bsratio`
  - `hglider` (thermalling height)
  - `hwcrit`, `dwcrit` (height and depth where the updraft reaches 225 fpm)
  - `zsfclcl`, `zsfclcldif`, `zsfclclmask` (cumulus cloudbase, cumulus potential)
  - `zblcl`, `zblcldif` (overdevelopment cloudbase and potential)
  - `blwind`, `bltopwind`, `blwindshear`
  - `wind850`, `wind950`
  - `wblmaxmin` (convergence)
  - `press850`, `press700` (vertical velocity, which shows wave)
  - `rain1`, `cape`, `blcloudpct`
  - `stars` (star rating)
- Etiquette, required before automating:
  - Martin is a GBSC member, so have him email Steve Paavola first. Ask permission and how often he may fetch, and offer attribution and a link.
  - Fetch no more than about 3 times a day, with a pause between requests (1 s is set in the script).
  - Cache everything and never hot-link images from the public page.

### Overlaying RASP images

`status.json` should give corner coordinates. RASP `body.png` images are usually in a Lambert conformal projection, so an `L.imageOverlay` on lat/lon bounds will be slightly off. There are two options. The simple one: accept the error and show the raw image in the site drawer, not on the map. The accurate one: pull point values via blipspot at each site (preferred), or reproject the image server-side with GDAL (Geospatial Data Abstraction Library) using the grid definition from the RASP run.

### Other regions

| Region | Source | Notes |
|---|---|---|
| New England, central PA | GBSC RASP (above) | Primary |
| Colorado (Black Forest, Front Range) | http://soarbfss.org/rasp/rasp2.html ; Dave Leonard's Front Range RASP (linked from soarcsa.org weather page) | Check format and permission |
| Pacific Northwest | wxtofly.net (TJ Olney) | Out of Martin's range |
| California | canv.raspmaps.com, santaynez.raspmaps.com, topaflyers.com/RASP, soaringpredictor.info | Out of range |
| US-wide | Dr. Jack RAP BLIPMAPs (drjack.info/blip/RAP) | Historically subscription; site did not load during research |
| Southeast, Florida, Texas, Arizona, Mid-Atlantic, Midwest | None found | Use the model-derived index |

A directory of RASP sites: https://www.spots.guru/en/blogs/rasp-forecast-models-global-directory-for-soaring-pilots. Paid services worth linking out to (no scraping): SkySight, XC Skies.

### Model-derived fallback (everywhere)

Open-Meteo is free with no key and allows multiple coordinates per request.
- Endpoints: `/v1/gfs` (GFS, plus HRRR, the High-Resolution Rapid Refresh, in CONUS through `models=`) and `/v1/forecast`.
- Hourly variables used: `boundary_layer_height, temperature_2m, dew_point_2m, cape, lifted_index, convective_inhibition, cloud_cover_low/mid/high, precipitation_probability, sunshine_duration, wind_speed_850hPa, wind_direction_850hPa, wind_gusts_10m`.
- Consider adding: `wind_speed_700hPa` (wave), `temperature_850hPa` and `temperature_700hPa` (lapse rate), and HRRR for days 1 and 2.
- Cache results server-side. Do not have every page view hit Open-Meteo.

## Target architecture

1. **Static site.** Hosting options are GitHub Pages, Cloudflare Pages or Martin's homelab (he runs personal servers; ask which). It serves `index.html`, `data/*.json` and `cache/**`.
1. **Forecast job (deterministic, no LLM).** A GitHub Actions cron (draft in `.github/workflows/`), or systemd timer or cron on the homelab. Run 2 or 3 times a day: `fetch_forecasts.py`, then build, then deploy. Keep 7 days of RASP dates and prune older ones.
1. **Data refresh job (LLM research).** A Claude scheduled task (Cowork "scheduled task") monthly, plus on demand before a trip. For each operator: re-read the website, rates and fleet pages; run an FAA registry owner-name search (https://registry.faa.gov/AircraftInquiry/Search/NameResult?Nametxt=OWNER+NAME); then update `operators.json` and `fleet.json`, set `last_verified`, and open a PR with a human-readable diff. It must never touch Martin's personal fields (see schema).
1. **Workbook and PDF.** Regenerate from JSON with the builders in `legacy/`; port them to read JSON.

## Data schema (source of truth: `data/`)

`operators.json` item:
- `id` (stable key, uppercase)
- `name`
- `kind` (Club, Commercial, Event, and so on)
- `region`
- `airport` (name plus FAA identifier)
- `city`
- `lat`, `lon`, `approx` (true when the coordinates are only approximately right)
- `access`: one of VAN, VANEDGE, FLY, FAR
- `travel`, `lift`, `season`
- `web`, `phone`, `email`, `contacts`
- `rental`: one of RENT, GUEST, JOIN, UNK, CLOSED
- `rank` (ease of short-notice rental within region; 0 = unranked)
- `procedure`, `costs`, `tall`, `sources`, `last_verified`

`fleet.json` item:
- `op`, `model`, `reg` (N-number, "" if unknown), `seats`, `rate`
- `who` (who may fly it)
- `note` (tall-pilot or operator note)
- `type` (key into glider_types)
- `last_verified`

Planned personal fields, kept in a separate file `data/martin.json` so research jobs cannot clobber them:
- `sat_in` (Y/N plus a note)
- `checkout_date`
- `current_until`
- contact log entries (date, operator, person, method, asked, outcome, next step, status)

`glider_types.json` value: `name`, `cls`, `seats`, `span` (m), `ld`, `v_ld` (km/h), `sink` (m/s), `vne` (km/h), `cockpit`, `approx`. Display in kt and fpm (km/h / 1.852; m/s x 196.85).

## Backlog, in priority order

1. Confirm the basemap fix in Martin's browser (known issue 1).
1. Get hosting decided and deployed. Make the page read `cache/openmeteo/sites.json` and a cached grid file, falling back to live Open-Meteo only when the cache is missing.
1. Email draft for Martin to send Steve Paavola about RASP use. Then run `fetch_forecasts.py` for real, fix field names against the actual `current.json`, `status.json` and blipspot output, and write parsers.
1. RASP in the UI:
   - a "RASP" layer group whose parameter dropdown uses GBSC's parameter list
   - per-site RASP numbers in the drawer (W* in fpm, hglider, Cu base, BL wind, wind850)
   - soundings in the drawer
1. Improve the index. Use RASP W* and hglider where available. Give ridge sites real ridge-line orientations; wave hints come from 700 hPa wind plus stability. Add a per-day map animation.
1. Global glider list upkeep:
   - fill the missing N-numbers
   - verify the `approx` type figures from TCDS (Type Certificate Data Sheets) and flight manuals
   - add dimensions that matter to a tall pilot (canopy height, seat-back to pedal distance) where published
   - add Martin's measurements (ask him)
1. Personal layer: checkouts, currency and "sat in it" per glider, with the map filtering to "I can fly this solo tomorrow".
1. Drive-time isochrones from Newton for a Friday 17:30 departure (for example OpenRouteService or OSRM, Open Source Routing Machine) instead of circles.
1. Flight tier refresh: re-check Friday-evening nonstops and fares quarterly.
1. Mobile layout pass; Martin often checks from his phone.
1. OGN tracks (done 2026-09-24, `docs/ogn-tracks.md`): set up the R2 bucket so the GitHub job starts; find the 2-33 and L-33 registrations; mark Martin's own flights in `data/martin.json`; run `collector/ogn_aprs.py` on the homelab as the fallback.

## Research caveats carried over

- Closed or not operating:
  - Stowe Soaring (VT, dissolved 2019)
  - Ridge Soaring Gliderport, Julian PA (closed 2022)
  - Turf Soaring (AZ)
  - Southwest Soaring (TX)
  - Kutztown (PA)
  - Eastern Soaring Center (WV): closed for 2026.
  - Bermuda High (SC): not scheduling new instruction.
  - Skyline Soaring: home field FRR (Front Royal) closed for repaving, so the club moved to Petersburg WV from 2026-09-16 for about 8 weeks.
- Seminole-Lake Gliderport (FL) has been listed for sale since 2022.
- Van Sant's FAA identifier is 9N1, not 9N8. Franconia is 1B5.
- Spirit Airlines ceased operations 2026-05-02.
- Many clubs publish nothing about visitors. `UNK` means call them.

## Checks before handing anything back to Martin

1. `python scripts/build_site.py` runs clean. Open `site/index.html` and confirm there are no console errors and no "API KEY REQUIRED" tiles.
1. Clicking any site shows the drawer with the fleet table. The glider list filters and sorts.
1. The forecast shows a timestamp and source. Stale cache (over 12 h) is flagged in the UI.
1. The JSON validates: every `fleet.op` exists in operators, and every `fleet.type` exists in glider_types.
1. No em dashes in documents Martin maintains by hand.
