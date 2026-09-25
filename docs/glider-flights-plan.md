# Plan: glider flights on the map, and flying activity versus the forecast

Written 2026-09-23. Sources were checked live that day; anything not confirmed is marked "unverified".

## Goal

Three views, in Martin's order:

1. **This day of the year, all years:** for a chosen date (for example July 1, plus or minus a window), how many flights happen in each grid cell, over every year of data.
1. **That exact day:** every flight on a chosen date, shown as tracks, or as a heat map when there are too many.
1. **Forecast versus flying:** learn how much flying a given forecast produces at each place, then predict flying activity from the forecast (for example "busy at Harris Hill next Saturday").

## What the sources allow (the short version)

No single source gives US-wide, multi-year, per-cell flight data that we may freely collect. The data exists: WeGlide has about 15,000 US flights in 2025 and OLC goes back to 2007. But both forbid bulk collection without written permission, and asking for permission is on hold (no asking outside people for now). So the plan uses what is open today and leaves room to plug the big archives in later.

| Source | What it has | Access today | May we store it and show it? | Verdict |
|---|---|---|---|---|
| **OGN FlightBook** (Open Glider Network logbook) | Takeoff and landing per airfield per day: times, duration, max altitude, tow. Back to about 2021. Only where OGN receivers exist (thin in the US, mostly around gliderports) | Keyless JSON, one airfield and one date per call | Data license is ODbL (Open Database License), with privacy flags to respect. OGN says not to re-distribute its data older than 24 h, so publishing even derived counts is a grey area | **Use now** for daily counts at covered airfields, kept private (see Decisions) |
| **SkyLines** (skylines.aero, open source) | Uploaded flights with IGC tracks; about 620 US flights in 2025 | Keyless API: flights by date or airport, IGC download | Data license not found (unverified); the project is open source | **Use now** for tracks on a chosen day; too sparse for counts |
| **WeGlide** | Uploaded flights with full tracks; about 15,300 US flights in 2025, back to about 2017 | Keyless reads work today, but the docs say an API key is required, limited to 60 requests a day | The terms forbid extracting a substantial part of the database, or systematic repeated extraction, and require deleting cached data | **Use carefully:** only fetch the tracks of one chosen day on demand, with Martin's own key, and store nothing. No archive |
| **OLC** (OnLine Contest) | Largest archive, back to 2007, daily US pages | No public API; robots.txt blocks crawlers | The terms allow about 10 flight files a day, for your own purposes only | **Link out only** |
| **SoaringSpot** | Complete IGC tracks for US contests | IGC files download from the archive host | Terms not found (unverified) | **Use now** as example tracks; very sparse (about 15 to 20 contest weeks a year) |
| **Our own OGN logger** | Live positions of every FLARM glider OGN hears, from the day we start | Free TCP (Transmission Control Protocol) feed, `aprs.glidernet.org:14580` | Must respect OGN's "do not track" and "do not identify" flags; tracks older than 24 h may not be republished, so keep them private or publish only aggregates | **Start soon:** the only way to build our own multi-year track history without anyone's permission |
| ADS-B (OpenSky, ADS-B Exchange, ADSB.lol) | Aircraft positions from transponders | OpenSky history only for institutions; ADS-B Exchange paid; ADSB.lol free dumps | ADSB.lol is ODbL | **Skip for now:** most US gliders carry no ADS-B, and coverage at gliderport altitudes is poor. Maybe later for tow planes as a proxy for launches |

## Decisions taken (2026-09-23)

1. **Collect and keep every flight** in our own datastore, including from sources whose terms forbid bulk collection (WeGlide, OLC). Martin accepts that risk for private use and will check the legal position before sharing anything. The data stays private until then.
1. **Never fetch the same flight twice:** one row per (source, flight ID); details and track downloaded once; flights seen in two sources linked by registration and takeoff time.
1. **Space before time:** New England first, going back many years, then wider rings (300, 600, 1,200, 2,500 km, then everywhere), each ring's last 2 years before its older history. Set in `collector/focus.py`.
1. **How we collect:** truthful User-Agent, a pause between requests, no logins, no CAPTCHA solving, no changing identity or IP to get past a block. A 403 or 429 stops that source for the run. This keeps the collection alive for years and keeps options open.
1. **Where:** code in `collector/` in this repo; the datastore on Martin's laptop at `~/chase-lift-data` (outside OneDrive), moving to the homelab later.

### What that means per source, as of 2026-09-23

1. **SkyLines** and **OGN FlightBook:** collecting (`python collector/collect.py --minutes N`).
1. **OGN FlightBook tracks of the club ships** (added 2026-09-24): FlightBook also serves each flight as an IGC file for 24 hours (`/api/live/igc/<address>/<from>/<to>`). `collector/ogn_tracks.py` saves the flights of the GBSC ships with trackers (K1 and the ASW 19 today; watch list in `data/martin.json`) three times a day from a Windows scheduled task, and `.github/workflows/ogn-tracks.yml` does the same on GitHub into the private branch `ogn-tracks`. Details and the endpoint notes: `docs/ogn-tracks.md`. This is Martin's backup record of his own flights, and it is the first OGN track data we keep.
1. **WeGlide:** answers only requests that look like a web browser (a truthful User-Agent gets HTTP 403), so it waits for an API key. Martin cannot create an account yet because WeGlide does not recognise his SSA number; once that is sorted, the key allows 60 requests a day, which lists about 6,000 flights a day (100 per request) plus some tracks.
1. **OLC:** collecting (`collector/olc.py`). Each day's US flights by SSA region (region 1 = New England first) come from the list the daily page's own map requests; each flight's details come from its public flight page. The map's track files are deliberately scrambled by OLC, so we do not use them. The official IGC download needs a logged-in OLC user (about 10 files a day per user, from pilots who allow downloads): the collector logs in as Martin with `OLC_USER` and `OLC_PASSWORD`, which he sets himself with `setx`. Login works (2026-09-23), but OLC answers "You must first claim a valid flight to use this function": only users who have claimed a valid flight of their own may download others' IGC files. Tracks wait until Martin claims one; flight details are collected meanwhile.
1. **SoaringSpot:** not started.
1. **SeeYou Cloud (Naviter):** pilots sync flights to it straight from their instruments, so it may hold flights that never reach OLC or WeGlide. No public search or API was found on 2026-09-23; look again. OLC's "open in SeeYou" option passes the same IGC file to SeeYou's viewer, so it is not a separate source and must not be used to get around OLC's download limit.

## Decisions still open

1. **Private or public site.** Several restrictions (OGN older than 24 h, WeGlide caching) are about *redistribution*. If the site is behind a Cloudflare Access login that only Martin can pass, it is personal use, and much more is clearly allowed. The code repo can stay public either way. Recommendation: put the flight layers (at least) behind a login.
1. **A WeGlide API key.** Martin creates a WeGlide account and generates a key himself. Blocked for now: his SSA number is not yet in WeGlide's system.
1. **Where the OGN logger runs.** It has to run all the time, which GitHub Actions cannot do. Options: Martin's homelab, or a small always-on cloud machine (a few dollars a month). Recommendation: the homelab, if it is on around the clock.

## Phases

### Phase 1: links out (hours of work, no risk)

1. In the site panel and for any chosen date, add links to that day's flights elsewhere: WeGlide's day view, OLC's US daily page, SkyLines' day list, and the OGN FlightBook page for the site's airfield.
1. Useful at once, needs no data handling, and checks the date logic the later phases need.

### Phase 2: airfield activity counts from OGN FlightBook

1. **Airfield list:** our operators' airfields first, then every FAA-registered gliderport and airport with known glider operations (ties into "Sites: every glider operation in the US" in BACKLOG.md).
1. **Backfill:** one call per airfield per day from about 2021, spread over many days at a gentle rate (the API may block a client that calls too often). For 50 airfields over 5 years that is about 90,000 calls; at 2,000 a day it takes about 6 weeks. Start with the busiest few airfields.
1. **Keep only derived daily numbers,** not the raw logbook: per airfield per day, the number of glider flights, total and median duration, and maximum altitude. A few MB in all. Store them in a private place (Decision 1), because OGN FlightBook history is not guaranteed to stay online. This is the one flight dataset we archive.
1. **Daily update** of yesterday's counts by the scheduled job.
1. **Map:** airfield circles sized by flights, for "that exact day" and for "this day of the year, all years" (plus or minus N days, default 7), with the number of years behind each average.
1. **Coverage caveat on the map:** an airfield with no OGN receiver shows "no data", never "0 flights".

### Phase 3: tracks for a chosen day

1. **Sources, fetched on demand when Martin opens a date, not collected in bulk:**
   1. WeGlide: one call for the US flight list of that date, then one per track, within the 60 a day. A typical summer weekend day is about 55 US flights, so it just fits; on bigger days, show the longest flights first.
   1. SkyLines and SoaringSpot: the same idea, no key needed.
   1. Our OGN logger, once it runs (Phase 5).
1. **Where the fetch runs:** a small Cloudflare Pages Function (serverless code on the same site, free tier) that holds the WeGlide key as a secret, so the key never reaches the browser. It returns simplified tracks and keeps nothing afterwards.
1. **Display:**
   1. Few flights: thin lines colored by altitude, hover for aircraft type, distance and speed, no pilot names. A "replay" slider that moves every glider along its track by time of day.
   1. Many flights: switch to a density heat map built in the browser from the same tracks.
   1. Respect privacy flags: skip WeGlide "protected" flights and OGN "do not track" aircraft.

### Phase 4: our own heat maps ("digitize the tracks")

1. Turn each track we are allowed to keep into grid cells: which cells it passed through, and how long it spent in each. Use the same Web Mercator grid and 8-bit PNG format as the forecast layers, so the page code is reused. Start at 0.1 deg (about 10 km) cells.
1. Layers: flights per cell per day, time spent per cell (where the lift is), and average height per cell.
1. "This day of the year, all years" per cell becomes possible once enough years accumulate from the logger, or immediately if WeGlide or OLC ever grant bulk access (On hold).

### Phase 5: our own OGN logger

1. First step done 2026-09-24: `collector/ogn_aprs.py` logs in to `aprs.glidernet.org:14580` read-only, subscribes to the club ships by callsign (`b/` filter) or to a radius (`r/`), keeps the raw lines per UTC day and converts them to IGC. It only needs an always-on machine (Decision 3) and a wider filter to become the US-wide logger below.
1. A small always-on program (Decision 3) connected to the OGN feed with a US-wide filter.
1. It keeps glider positions only (aircraft type 1), drops "do not track" devices, and hides the identity of "do not identify" devices.
1. It thins tracks to one point every 10 s, splits them into flights, and writes one compressed file per day. Rough estimate (unverified): a few MB per busy day for the US.
1. This raw track archive is ephemeral data nobody else keeps, so we keep it, privately.
1. Each night it feeds Phase 4 (cells) and Phase 2 (counts at airfields without a FlightBook record).

### Phase 5b: flying activity versus the forecast (goal 3)

1. **Join** each airfield-day (Phase 2 counts) with the forecast for that place and day. Past forecasts come from rebuilt NOAA runs (`fetch_models.py --cycle`; HRRR back to 2014, GFS back to 2021), or ERA5 reanalysis for what actually happened.
1. **Explain the counts** with the weather (W*, boundary layer top, cloud, wind, rain) and the calendar: weekend or weekday, holiday, season, and the airfield's own normal level. A count model (Poisson or negative binomial regression) suits "flights per day".
1. **Check it honestly:** fit on earlier years, test on the latest year, and report how well it predicts.
1. **Use it:** "expected flights" for each airfield next weekend from the current forecast, on the map and in the site panel. Also a better soaring index, calibrated on "days people actually flew well here".
1. **Performance** (distance, speed) needs tracks or scored flights, so this part waits for enough Phase 3 and 5 data, or for bulk access (On hold).

## On hold (needs someone else)

1. Written permission from WeGlide for a research export or bulk access: it would unlock per-cell multi-year history from about 2017 and performance statistics at once.
1. Permission from OLC for daily US data back to 2007.
1. OGN: confirm whether publishing aggregated counts older than 24 h is fine.

## Storage summary

| Data | Kept? | Why |
|---|---|---|
| OGN FlightBook raw logbooks | No, only daily counts per airfield | Counts are small; the service may not keep its history forever |
| WeGlide, SkyLines, SoaringSpot tracks | No, fetched on demand | WeGlide terms; the providers keep them |
| Our OGN logger tracks | Yes, privately | Nobody else keeps them |
| Cell heat-map grids | Rebuilt from the above when needed | Derived data |

## First steps, in order

1. Phase 1 links out.
1. Decisions 1 to 3 from Martin.
1. Phase 2 for GBSC (Sterling), Harris Hill and 3 or 4 other covered airfields, to see how complete OGN coverage really is before scaling up.
