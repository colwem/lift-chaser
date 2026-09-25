# Chase-Lift backlog

Things to build or decide, grouped by theme, roughly in priority order within each group. Add items anywhere. "Needs Martin" marks items that wait on a decision, an account, or information only Martin has.

Started 2026-09-23 from the working session notes. This file replaces the backlog list in CLAUDE.md.

Ground rule: no asking outside people to do work for the project for now. Prefer sources that need nobody's permission or effort. Anything that needs someone else goes under "On hold" at the bottom.

## Next up

1. Watch the NOAA pipeline for a week; then drop the Open-Meteo fallback (fetch step, cache files, live browser fetch and its throttling code).
1. Page support for past runs: a run or date picker that loads `cache/past/<cycle>/` built by `fetch_models.py --cycle`, plus a workflow input to build one on demand.
1. Apply the recommended CLAUDE.md updates (current state table, known issues, development environment, hosting decision, backlog pointer to this file).
1. Mock up the "everything on one page" layout (see Display) so Martin can react to it before it is built.

## Map resolution: finest detail available

Done for GFS (0.25 deg) and HRRR (3 km): `scripts/fetch_models.py` fetches NOAA data directly and the page draws it at native resolution. Remaining:

1. Shrink the images (HRRR is about 0.4 to 1 MB per variable and hour, about 255 MB per run): try lossless WebP, or map tiles if the full-US image gets slow on a phone.
1. Add RRFS (Rapid Refresh Forecast System, operational 2026-10-06, expected to replace HRRR eventually) as one more entry in `scripts/models.py`.

## Forecast data

1. Done: W* (thermal updraft velocity) = (g / T x H / (rho x c_p) x z_i)^(1/3) from NOAA surface heat flux H and boundary layer height z_i, in `fetch_models.py`. GFS W* uses a time-averaged flux, HRRR an instantaneous one. Next: check it against RASP or SkySight on a few days.
1. Compute the established soaring parameters from the model data too: thermal index at several levels, height where the thermal index reaches -3, trigger temperature, cloudbase and cumulus potential. These are what NWS soaring forecasts and RASP publish.
1. Add ECMWF (European Centre for Medium-Range Weather Forecasts) and ensemble forecasts; use the ensemble spread as a confidence measure.
1. Add more variables: 700 hPa wind (wave), 850 and 700 hPa temperature (lapse rate), convective inhibition, sunshine duration.

## Soaring index

1. Replace or back up our heuristic with the established indices above (thermal index, W*, star-style rating), and show which one is used.
1. Stop ridge sites saturating at 10 so easily.
1. Real ridge-line orientations per site instead of the heuristic directions in `ridge_sites.json`.
1. Wave hints from 700 hPa wind plus stability.
1. Fix the help text: it says ridge wind must be "within 40 degrees", but per-site half-widths range from 35 to 45.

## Forecast archive and verification: going back in time

1. Decided: nothing is archived. NOAA keeps GFS (since 2021) and HRRR (since 2014) on AWS and Google Cloud, and MRMS, RTMA/URMA, NBM, soundings and METARs are all kept by their providers. `fetch_models.py --cycle YYYYMMDDHH` rebuilds any past run. Only a one-line-per-run log is kept, on the `archive` branch (`runs.jsonl`), recording what the site showed and when.
1. If a NOAA archive ever disappears from both AWS and Google, revisit keeping our own copy.
1. Date picker that works for past dates too, without breaking the interface. For a past date, show:
   1. The forecast as it was issued (choose how many days ahead: 1, 3 or 7 days before).
   1. What actually happened (observed or analyzed).
   1. The difference between them, as a map.
1. Sources for "what actually happened", all public and keyless:
   1. Rain: MRMS (Multi-Radar Multi-Sensor), NOAA's gridded blend of radar and rain gauges, which is exactly the "best guess where there is no gauge". Stage IV precipitation analysis as a check.
   1. Surface weather: RTMA and URMA (Real-Time and Un-Restricted Mesoscale Analysis), NOAA's hourly 2.5 km gridded analyses of temperature, dew point, wind, gusts and sky cover.
   1. Upper air: radiosonde soundings (twice a day) and aircraft profiles (AMDAR, Aircraft Meteorological Data Relay) for real boundary layer depth and lapse rate.
   1. Cloud base and ceilings: METARs (routine airport weather reports) from the IEM (Iowa Environmental Mesonet) archive.
   1. Everything else, including boundary layer height: ERA5 reanalysis (about 5 days behind).
1. Score forecast skill per model, lead time and region, so the page can say how far to trust a forecast at a given range.

## Glider flights: tracks, activity heat maps, and flying versus forecast

Full plan with sources, terms and phases: `docs/glider-flights-plan.md`. In short: links out first; daily flight counts per airfield from OGN FlightBook (about 2021 on); tracks for a chosen day fetched on demand (WeGlide with Martin's own key, SkyLines, SoaringSpot); our own OGN logger for a track history going forward; then a model of flights per day from the forecast. Decisions needed from Martin: private or public site, a WeGlide API key, where the logger runs. Bulk access to WeGlide and OLC is on hold.

1. Collect and keep every flight from WeGlide, OLC, SkyLines, SoaringSpot and OGN in our own datastore, each flight fetched exactly once, with duplicates across sources matched up. Private until the legal side is settled (Martin's decision, 2026-09-23).
1. Done 2026-09-24: the club ships' OGN tracks (K1 and the ASW 19) are saved as IGC files every day from FlightBook, on the laptop (scheduled task) and, once the R2 bucket is set up, by GitHub Actions into Cloudflare R2 (no data in the repo). See `docs/ogn-tracks.md`. Next: mark Martin's own flights in `data/martin.json`, and run `collector/ogn_aprs.py` on the homelab as the fallback logger.
1. Separate weather from everything else that drives flying ("exposure"): more flights happen on weekends and 3-day weekends, in the summer holidays, on the days a club operates, and near places where glider pilots live. Build a baseline of expected flights per site and day without weather, and use it as a mask so that what is left over is the effect of the weather. Inputs to consider:
   1. Calendar: day of week, US federal holidays and the 3-day weekends around them, school vacations, club operating days and seasons.
   1. Where glider pilots live: the FAA releasable airmen database lists certificated pilots with their ratings (including glider) and home city, state and ZIP, so it gives the pilot population within a drive time of each site. SSA membership by region is a cross-check.
   1. Travel time from those pilots to each site (the same drive-time work as in Trips).
   1. The site's own history: its normal level of flying for that week of the year.
   1. In the model: the baseline enters as an offset (the expected count without weather), so the weather terms explain only the departures from normal.
1. Correlate predicted soaring quality with what glider pilots actually did: number of flights recorded in the area that day, and their average performance (distance, speed, contest points, maximum height).
1. Use the result to calibrate the soaring index and the climatology ratings, so "good day" means "a day people actually flew well here".
1. Show it on the map for past dates: predicted index next to actual flight count and performance.
1. Depends on the track archive research below.

## Climatology: planning weeks or months ahead

1. Done 2026-09-23: research on glider track archives, see `docs/glider-flights-plan.md`.
1. Check which variables ERA5 (ECMWF reanalysis, 1940 to present) provides through Open-Meteo's historical weather API, especially boundary layer height, CAPE and cloud.
1. Date picker beyond the 7-day forecast.
1. Absolute heat map: flights per grid cell within plus or minus 7 days of the chosen date, over all years.
1. Normalized heat map: that count divided by the cell's average weekly count, with smoothing for cells with few flights.
1. For each site and date window, the historical distribution of the established soaring indices (thermal index, W*, star rating and so on), shown as percentages per rating.
1. Prototype that for 3 or 4 sites before building the global maps.
1. Blend forecast and climatology between about 10 days and 2 weeks out.
1. Good soaring days per year, per gliderport: a map with a circle at each gliderport sized (and colored) by the average number of good soaring days a year, with a date-range filter (for example only January, or June to August) so it answers "where is it good in January". Also as a smooth heat map between gliderports.
   1. Needs a definition of a good day that holds up: for example soaring index or W* above a threshold for at least a few hours between 11:00 and 17:00 local, or a ridge day; show the threshold and let it be changed.
   1. Built from the same daily history as the point inspector (rebuilt NOAA runs or ERA5 reanalysis), averaged over as many years as available, with the number of years shown.
   1. Later, calibrated against real flying (Glider flights section): days that produced good flights at that site.

## Calendar scrubbing: watching weather develop over days, seasons and years

Sliding through the hours of a day and watching the map change works well. Extend it to the calendar.

1. Multi-day slider: one slider spanning several days of hours (for example the whole 7-day forecast), with a play button.
1. Fixed-time day slider: pick a time of day (for example 13:00) and slide through the days, so each step shows the same hour on the next day.
1. Year scale: the same fixed-time slider across a whole year, to see how conditions develop through the seasons. For past years this uses rebuilt past runs (see Forecast archive) or reanalysis.
1. Choose what a past day shows: the forecast as issued (and how many days ahead), or what actually happened.
1. Keep it fast: a year at one hour a day is 365 images per variable, so the year view likely needs smaller images (coarser grid or tiles), preloading, and precomputed daily files.

## Point inspector: everything for one grid cell

Click any grid cell (not only a gliderport) to open a panel at the bottom of the map with everything known for that spot, past and future.

1. The current forecast values for that cell, every variable, hour by hour, from each model.
1. Graph of the soaring index (and any other variable) by day of year, averaged over all years, with the spread (for example 25th to 75th percentile). The seasonal shape at that spot.
1. Graph by absolute date: scroll back through the actual history, for example to July 2020, and see the forecast issued for that day (and what happened, once verification data is in).
1. Overlays on the same graphs: glider flights at that cell per day (see Glider flights), and forecast versus observed.
1. Data behind it: a per-cell daily time series built once from NOAA archives and extended each day. It is derived data that can be rebuilt, so it may be stored and pruned freely. HRRR reaches back to 2014 on AWS; GFS on AWS starts 2021, and older GFS runs are at NCAR RDA and NCEI if needed.
1. Pick the grid for this: the full 3 km HRRR grid over 10 years is large, so start with a coarser grid (for example 0.25 deg) or daily values at 13:00 only.

## Display: everything on one page

1. Wall of synced small maps, one per variable (W*, thermal top, cloudbase, wind, cloud cover, CAPE and so on). Pan or zoom one and all follow.
1. One time slider driving all maps, with a play button to animate the day.
1. Day strip: every site x the next 7 days as a colored table.
1. Site panel:
   1. Meteogram (hours x variables as colored rows).
   1. Sounding (Skew-T diagram) from model data.
   1. Models side by side for the same site and time.
   1. Fleet table (already there).
   1. Trip options for the selected date (see Trips).
1. Pick the forecast source by lead time (HRRR, then GFS and ensembles, then climatology) and always label which source is shown.
1. Help text for every forecast layer: a short "what it is, how it is computed, how to read it, what it misses" note next to the variable picker, with a longer version one click away. For example the soaring index: its thermal part (boundary layer depth from 1,500 ft = 0 to 6,500 ft = full), the cuts for low cloud, rain and CAPE, the ridge part, and that it is our own heuristic, not a published index. Same for W* (the formula and its inputs), cumulus base (the spread rule), lifted index, CAPE and so on. Also say which model each layer comes from and its resolution.
1. Deep links to SkySight, XC Skies and Windy for the same place and time.
1. Mobile layout pass; Martin often checks from his phone.
1. Fleet table still needs sideways scrolling in narrow windows.

## Sites: every glider operation in the US

1. Widen the scope from "in range of Boston" to the whole US, keeping access category (van, fly, far) as a filter rather than a limit.
1. Build the master list from several sources and cross-check them:
   1. FAA (Federal Aviation Administration) NASR (National Airspace System Resources) airport data, which lists registered gliderports as their own facility type, plus airports whose records mention glider operations.
   1. SSA (Soaring Society of America) club, chapter and commercial operator listings.
   1. Where tracks actually start: airfields with launches in WeGlide, OLC or SkyLines archives. This finds active operations that directories miss, and inactive ones they still list.
   1. OurAirports and OpenAIP data as a cross-check.
1. For each new operation, research the same fields as today (rental category, procedure, costs, fleet, contacts, sources, `last_verified`), region by region, with the monthly refresh job keeping them current.
1. Track coverage: a count of operations per state, verified or not, so gaps are visible.
1. Secondary, maybe out of scope: every airport Martin could land a glider at, as a toggleable layer (runway length and surface, from FAA NASR or OurAirports). Useful for cross-country planning and outlandings.

## Trips: getting there for the selected date

For a selected date (for example Saturday October 11), clicking a site shows the gliders, the rental terms (or "no terms known"), and the ways to get there, each with a link.

1. Departure rule: leave the evening before after work (default 17:30 from Newton), and return the day after flying or Sunday evening. Settable.
1. Driving:
   1. Drive time with traffic for that departure time: TomTom Routing (free key, handles departure time) or Google Routes API. Needs Martin for the key.
   1. A link that opens the driving route in Google Maps, which needs no key.
   1. Replace the straight-line rings with real drive-time areas for the same departure.
1. Flying:
   1. Nearest airline airports to each site, and the drive from the airport to the site.
   1. A prefilled Kayak search link for the selected dates (Kayak search pages take airports and dates in the address, no key needed), which opens ready to book.
   1. Prices and itineraries through an affiliate program, which pays the site for clicks or bookings (researched 2026-09-23):
      1. KAYAK Affiliate Network (also momondo, Cheapflights): deep links, widgets and an API; pays on clicks and bookings; apply and get approved, no stated traffic minimum. Apply first. Needs Martin.
      1. Travelpayouts (Aviasales): open signup; data API with nonstop prices for a route and date, cached up to 48 h; pays about 1.1 to 1.3 % of the fare on bookings. Fallback, weaker on US fares.
      1. Skip for now: Skyscanner (needs 5,000 monthly visitors), Kiwi.com (invitation only), Expedia (now a creator program), Google Flights (no affiliate program).
      1. Affiliate income makes the site commercial, so Open-Meteo's free tier would no longer apply. Another reason the forecasts now come from NOAA.
   1. Filter to Martin's rules: evening nonstop from BOS, under about $300 round trip, landing by about midnight.
1. Show the best option first (fastest door-to-door or cheapest), with total time and cost.

## Sites and gliders data

1. Fill the 77 missing N-numbers, preferably from the FAA releasable aircraft database download rather than one owner-name search at a time.
1. Verify the 19 glider types marked `approx` from TCDS (Type Certificate Data Sheets) and flight manuals.
1. Add cockpit dimensions that matter to a tall pilot (canopy height, seat-back to pedal distance) where published.
1. Add Martin's measurements (height, sitting height, leg length) and use them to rate cockpit fit. Needs Martin.
1. Monthly data refresh job: re-read operator websites, rates and fleet pages, update `operators.json` and `fleet.json`, set `last_verified`, open a pull request with a readable diff. Decide whether it runs as a Cowork scheduled task or in GitHub (GitHub needs an Anthropic API key). Needs Martin.
1. Re-verify the research caveats (closures, Spirit Airlines, Skyline Soaring's temporary move and so on).

## Personal layer

1. `data/martin.json`, kept separate so research jobs cannot overwrite it: `sat_in` (Y/N plus note), `checkout_date`, `current_until`, and a contact log (date, operator, person, method, asked, outcome, next step, status).
1. Filter the map to "gliders I can fly solo tomorrow".

## Plumbing and cleanup

1. Make `build_site.py` inline `labels.json`, `ridge_sites.json` and `flights.json`; the page currently uses hard-coded copies and ignores those files.
1. Port the workbook and PDF builders in `legacy/` to read the JSON in `data/` instead of `legacy/data.py`.
1. Add `.gitattributes` with `* text=auto eol=lf` to stop the line-ending warnings.
1. Move the repo out of OneDrive (or exclude it from sync) to protect `.git`. Needs Martin.
1. Optional: custom domain through Cloudflare Registrar. Needs Martin.
1. Optional: Cloudflare Access login in front of the site, once `martin.json` or anything private is on it. Needs Martin.
1. Confirm the basemap tile retry works when a tile really fails (only seen working in tests so far).
1. Check that GitHub's email about failed scheduled runs actually arrives.

## On hold: needs other people

1. GBSC RASP (Regional Atmospheric Soaring Prediction), run by Steve Paavola. Would need his permission before any automated use. Not now. If it ever happens:
   1. Run `fetch_forecasts.py --rasp` and fix field names against the real `current.json`, `status.json` and blipspot output.
   1. RASP map layer, per-site RASP numbers and soundings in the site panel.
1. Other RASP sources (Colorado: soarbfss.org, Dave Leonard's Front Range RASP): same issue, check terms before any use.

## Done

1. Local development setup: Python 3.12, Git, GitHub CLI, local preview server.
1. Private repo on GitHub (colwem/lift-chaser) and deploys to Cloudflare Pages at https://lift-chaser.pages.dev.
1. Forecast cache fetched by GitHub Actions 3 times a day; page reads the cache, shows fetch time, flags data older than 12 h.
1. Page throttles and retries live Open-Meteo requests; loading spinner, progress bar and build stamp.
1. Fixed: clicking a site on the map now opens its drawer; fleet table fits the drawer.
1. Basemap "API KEY REQUIRED" tiles gone (Esri and USGS tiles, no key).
1. NOAA HRRR (3 km) and GFS (25 km) straight from AWS, with W*, at native resolution on the map, a value readout under the cursor, and per-site forecasts from the same data (2026-09-23).
1. Soaring index 0 color no longer looks like missing data; region picker replaced by a model picker.
