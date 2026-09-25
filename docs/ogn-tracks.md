# OGN tracks of the club ships: how they are collected

Written 2026-09-24 after David's email about the trackers in K1 and the ASW 19. Every endpoint below was exercised live that day.

## What OGN is and where the K1's positions go

1. **FLARM** is an air-to-air collision warning device. It broadcasts the aircraft's GPS position and vector on 868 MHz (Europe) or 902 to 928 MHz (North America) about once a second so other FLARMs nearby can warn their pilots.
1. **OGN (Open Glider Network)** is an open-source project that reverse engineered the FLARM radio protocol. Volunteers run ground receivers (a Raspberry Pi with a software-defined radio) that hear FLARM and OGN tracker transmissions and forward every position to OGN's servers. An **OGN tracker** is OGN's own, cheaper transmitter; it only sends, it does not warn.
1. The servers redistribute positions over **APRS-IS (Automatic Packet Reporting System, Internet Service)**, a plain-text feed borrowed from amateur radio. Live maps such as glideandseek.com and puretrack.io are clients of that feed.
1. **The OGN device database (DDB)** at https://ddb.glidernet.org maps a tracker's 24-bit address to a registration, competition ID and type, and holds each owner's privacy choices ("tracked" and "identified"). The club registered its trackers with both flags on, which is why K1 shows up by name.
1. **OGN's data rules** (https://www.glidernet.org/ogn-data-usage/): the data is under the ODbL (Open Database License), you must follow the DDB privacy flags when re-distributing, and you must not re-distribute OGN data older than 24 hours. That last rule is why every OGN service deletes positions after a day, and why we need our own daily copy.

## The club's trackers

From the DDB (2026-09-24) and FlightBook's logbook for Sterling (3B3, flights since 2025-07-12):

| Ship | Registration | CN | Tracker address | Type | Flights logged at 3B3 | Last logged |
|---|---|---|---|---|---|---|
| ASK-21 K1 | N421GB | K1 | A4FFEE | I (ICAO address) | 452 | 2026-09-19 |
| ASW-19B | N9814A | US | ADB1C0 | I | 32 | 2026-08-15 |
| ASK-21 K2 | N721RC | K2 | A9A8BD | O (OGN tracker) | 12 | 2026-04-08 |
| L-23 Super Blanik | N373BA | 3BA | A43F0A | I | 4 | 2025-08-28 |
| SGS 1-34 | N1156S | 34 and 134 | A04201, F4F0D2 | I and F (FLARM) | 3 | 2025-07-26 |
| SGS 1-26E | N33917 | 26 | A3B9D9 | I | 9 | 2025-12-07 |

The FAA registry confirms N421GB, N721RC, N9814A, N373BA, N1156S and N33917 as registered to the club's PO Box 655 in Sterling. The 2-33 and the L-33 registrations in `data/fleet.json` are still unknown (N233GB and N289BA, which also fly from Sterling, belong to MIT Soaring Association). David says only K1 and the ASW 19 have working installations today; the others are watched anyway so their flights are kept the day a tracker comes back.

The watch list lives in `data/martin.json` under `ogn_watch` (addresses and airfields). Research jobs never touch that file.

## Where the tracks can be had

| Source | What it gives | How long it keeps positions | Access |
|---|---|---|---|
| **FlightBook** (flightbook.glidernet.org) | A logbook per airfield and day (takeoff, landing, duration, max altitude, tow) and an IGC file per flight | 24 h after each position, cleanup hourly | Keyless HTTP API, used here |
| OGN APRS feed (aprs.glidernet.org:14580) | Every position, live, as text lines | Nothing is kept; you record what you hear while connected | Free TCP login, no password |
| KTrax (ktrax.kisstech.ch) | Logbook and tracking, with a REST API | Not stated | API only for paying subscribers, key on request |
| PureTrack (puretrack.io) | Live map with IGC download of any track | 7 days for its own data, but OGN data only 24 h | Pro subscription for anything older than 48 h |
| glideandseek.com, live.glidernet.org | Live maps | About an hour of history | Web pages only |
| WeGlide, OLC | Pilots' own uploads from flight recorders | Forever | Only if the pilot uploads; the K1's tracker is not a flight recorder |

FlightBook is the one to use: it already does takeoff and landing detection, it hands back a standard IGC file, and it runs on OGN's own domain. The APRS feed is the fallback if FlightBook ever goes away, but it needs a machine that is on whenever the club flies.

## FlightBook's API, as used by `collector/ogn_tracks.py`

The endpoints come from FlightBook's page code (`js/app.*.js`, the `igc()` function) and its `doc/API.md` (gitlab.com/lemoidului/ogn-flightbook, AGPL).

1. `GET https://flightbook.glidernet.org/api/logbook/3B3` returns today's logbook on the airfield's own calendar (`date` in `America/New_York`). `GET .../logbook/3B3/2026-09-19` returns a past day. The reply has `devices` (address, registration, competition, aircraft, `aircraft_type` 1 = glider, 2 = tow plane) and `flights` (index into `devices`, `start_tsp` and `stop_tsp` as Unix times, `start` and `stop` as local `HHhMM`, `duration` s, `max_alt` m, `tow`).
1. `GET .../api/live/igc/<address>/<from>/<to>?date=YYYY-MM-DD` returns an IGC file with every fix between two Unix times. FlightBook's own "igc" button asks for `start_tsp` minus 30 s to `stop_tsp` plus 30 s (or `start_delta` and `stop_delta` minutes when the logbook gives them), so the script asks for the same window. The reply is empty (0 bytes) once the positions are older than 24 hours.
1. `GET .../api/live/igc/<address>/<from>` with no end returns everything from `from` until now. The script uses this for a flight whose landing FlightBook never detected, once the flight is 6 hours old.
1. `GET .../api/live/igc/<address>/0` returns only the aircraft's last flight, not the day, so it is not used.
1. `API.md` warns that a "daily high call rate for same client may be blocked by maintainer". A run makes one logbook call per airfield and day (two days by default) plus one call per new flight, 3 s apart, with a truthful User-Agent. A 403 or 429 stops the run (see `collector/polite.py`).

The IGC file FlightBook writes starts with `AOGNOGN`, has `HFDTE` (UTC date), `HFGTYGLIDERTYPE`, `HFGIDGLIDERID` and `HFFTYFRTYPE:OGN-FLIGHTBOOK` headers, then one `B` record per received position: UTC time, latitude, longitude, fix validity `A`, pressure altitude 0 (there is no pressure sensor) and GPS altitude in metres. A busy day at Sterling gave about one fix every 5 to 10 s. The file has no `G` security record, so it is not valid for badges or contests; it is a backup of where the glider went.

## What runs, and when

1. **Laptop, three times a day.** The Windows scheduled task "chase-lift OGN tracks" (registered with `scripts/install_ogn_task.ps1`) runs `python collector/ogn_tracks.py` at 07:30, 13:00 and 21:00. If the laptop was asleep it runs as soon as it wakes ("start when available"), so opening the laptop once a day is enough. It writes:
   1. `~/chase-lift-data/igc/<year>/<date>_<HHMM local>_<registration>_<cn>.igc`, plain files that open in any IGC viewer (SeeYou, XCSoar, igcviewer.bgaladder.net).
   1. `~/chase-lift-data/igc/index.jsonl`, one line per flight with everything the logbook said.
   1. A compressed copy and a row in the flights datastore (`source` "ogn"), so `python collector/collect.py --status` lists them.
   1. `~/chase-lift-data/ogn_tracks.log`, what each run did.
1. **GitHub, twice a day.** `.github/workflows/ogn-tracks.yml` runs the same script at 01:00 and 12:00 UTC on GitHub's machines and uploads new files to a Cloudflare R2 bucket (object storage), never to GitHub: no data goes in the repo (Martin, 2026-09-24). A week away from the laptop then loses nothing. It does nothing until the bucket is set up (steps at the top of the workflow file). GitHub disables scheduled workflows after 60 days without a push to the repo, so a quiet winter needs one push, or a manual "Run workflow" click.
1. **Every collector run.** `python collector/collect.py` runs the same pass first, before the slow sources.

Finding your own flight: the file name carries the local takeoff time, so match it against your logbook. `index.jsonl` has the tow plane (when OGN heard it) and duration for a second check. `data/martin.json` has a `my_flights` list reserved for marking which files are yours.

## The fallback: our own feed logger, `collector/ogn_aprs.py`

1. Connects to `aprs.glidernet.org` port 14580 and logs in read-only with `user CHASELIFT pass -1 vers chase-lift 0.1 filter b/...`. The server answers `# logresp CHASELIFT unverified, server GLIDERN1` and starts sending lines; "unverified" is normal for a read-only client.
1. The filter names the senders to pass: each watched address with each of the three prefixes OGN uses for a sender's callsign, `FLR` (FLARM), `OGN` (OGN tracker) and `ICA` (ICAO address), for example `ICAA4FFEE` for K1. A radius filter `r/42.43/-71.79/50` would pass everything within 50 km of Sterling instead.
1. Every 20 s the server sends a `# aprsc ...` line as its keep-alive; the client must also send something (a line starting with `#`) about once a minute or the server drops it. The logger reconnects after 30 s if the connection dies.
1. Raw lines go to `~/chase-lift-data/aprs/<UTC date>.log`. `python collector/ogn_aprs.py --to-igc <log>` turns a day's log into one IGC file per aircraft (no takeoff and landing detection; FlightBook does that better).
1. It has to run on an always-on machine to be useful. On the homelab: `python collector/ogn_aprs.py` under a systemd service or a `screen` session, with `CHASE_LIFT_DATA` pointing at a local folder.

## Checked on 2026-09-24

1. Logbook for LFLE (Chambery, a busy French field) that afternoon: 25 flights. The IGC window for a 2 h ASK-23 flight returned 43,695 bytes and 1,174 fixes. Six windows for an ASK-13 with six flights returned six files (82 to 488 fixes each) that together matched the open-ended fetch from the first takeoff (1,572 fixes).
1. K1's seven flights of 2026-09-19 were still in the logbook, but their IGC windows returned 0 bytes, as the 24 hour rule predicts; the script recorded them as lost rather than trying again.
1. APRS login and both filter styles worked from Martin's laptop; a 300 km radius around Sterling produced 35 position lines in 40 s on a Thursday afternoon, from FLARMs at Sugarbush (0B7), an OGN tracker at 1I5 and ADS-B relays.
