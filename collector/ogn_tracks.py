"""OGN FlightBook tracks for the club's ships: one IGC file per flight, fetched within 24 hours.

Why: OGN (Open Glider Network) ground receivers hear the trackers in GBSC's K1 (ASK-21 N421GB) and
ASW 19 (N9814A) and forward every position to the OGN servers. FlightBook (flightbook.glidernet.org,
AGPL, gitlab.com/lemoidului/ogn-flightbook) turns those positions into a logbook per airfield and can
hand back any flight as an IGC file. OGN's data rules make it drop positions 24 hours after they were
received (cleanup runs hourly), so this has to run at least once a day and keep its own copy.

How (endpoints read from FlightBook's page code and doc/API.md, checked live 2026-09-24):
  GET /api/logbook/<airfield>                    today's logbook (the airfield's own local date)
  GET /api/logbook/<airfield>/<YYYY-MM-DD>       devices and flights that day (takeoff and landing)
  GET /api/live/igc/<address>/<from>/<to>        IGC file with every fix between two Unix times
  GET /api/live/igc/<address>/<from>             ... from a Unix time until now (open end)
  GET /api/live/igc/<address>/0                  only the last flight, so we do not use it
FlightBook's own "igc" button asks for start_tsp - 30 s to stop_tsp + 30 s (or start_delta and
stop_delta minutes when the logbook gives them); we ask for the same window. API.md warns "Daily high
call rate for same client may be blocked by maintener", so a run makes one logbook call per airfield
and day plus one call per new flight, with a pause between calls (polite.py).

Watch list: data/martin.json, key "ogn_watch": the club's tracker addresses from the OGN device
database (https://ddb.glidernet.org/download/) and the airfields to read. Anything else that flies
at those airfields is ignored.

  python collector/ogn_tracks.py                 yesterday and today at every watched airfield
  python collector/ogn_tracks.py --days 3        look back further (logbooks stay, but IGC files
                                                 older than 24 h come back empty)
  python collector/ogn_tracks.py --out DIR       plain folder mode, no datastore: DIR/<year>/*.igc
                                                 plus DIR/index.jsonl (the GitHub job uses this)
  python collector/ogn_tracks.py --airfield LFLE --watch DDB0D1   watch something else, for testing

Datastore mode (the default) writes each flight three ways: a plain IGC file under
<datastore>/igc/<year>/<date>_<HHMM local>_<registration>_<cn>.igc that opens in any IGC viewer, the
usual compressed copy under tracks/ogn/, and a row in the flights table (source "ogn",
source_id "<address>_<start_tsp>"). Its log is <datastore>/ogn_tracks.log.
"""
import argparse, datetime as dt, json, pathlib, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import store
from store import now, save_track, igc_summary
from polite import Polite, Blocked

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = "https://flightbook.glidernet.org/api"
SOURCE = "ogn"
GAP_S = 3.0                    # between calls to FlightBook
OPEN_END_AFTER_S = 6 * 3600    # landing never detected: after this long, fetch from takeoff to now
LOST_AFTER_S = 26 * 3600       # no fixes came back and the flight is this old: give up (OGN's 24 h)


def watch_list(path=ROOT / "data/martin.json"):
    """{address: device} and the airfield codes from data/martin.json."""
    w = json.loads(path.read_text(encoding="utf-8")).get("ogn_watch", {})
    return {d["address"].upper(): d for d in w.get("devices", [])}, list(w.get("airfields", ["3B3"]))


def logbook(http, code, day=None):
    url = f"{BASE}/logbook/{code}" + (f"/{day}" if day else "")
    return json.loads(http.get(url))


def flights_of(book, watch):
    """(flight, device) pairs for watched devices in one logbook, in takeoff order."""
    devs = book.get("devices") or []
    out = []
    for f in book.get("flights") or []:
        i = f.get("device")
        if i is None or not (0 <= i < len(devs)) or f.get("start_tsp") is None:
            continue
        d = devs[i]
        if (d.get("address") or "").upper() in watch:
            out.append((f, d))
    return sorted(out, key=lambda fd: fd[0]["start_tsp"])


def window(f):
    """Unix times FlightBook's own IGC button asks for. The end is None when no landing was seen."""
    a = f["start_tsp"] - (60 * f["start_delta"] if f.get("start_delta") is not None else 30)
    if f.get("stop_tsp") is None:
        return a, None
    return a, f["stop_tsp"] + (60 * f["stop_delta"] if f.get("stop_delta") is not None else 30)


def fetch_igc(http, address, a, o, day):
    url = f"{BASE}/live/igc/{address}/{a}" + (f"/{o}?date={day}" if o else "")
    return http.get(url)


def n_fixes(blob):
    return sum(1 for line in blob.splitlines() if line.startswith(b"B"))


def utc(tsp):
    return dt.datetime.fromtimestamp(tsp, dt.timezone.utc).isoformat(timespec="seconds") if tsp else None


def record(book, f, d, code):
    """What we keep about a flight besides the track: everything FlightBook said, in plain fields."""
    devs = book.get("devices") or []
    tow = devs[f["tow"]] if isinstance(f.get("tow"), int) and 0 <= f["tow"] < len(devs) else None
    reg = (d.get("registration") or d["address"]).replace("-", "")
    cn = d.get("competition") or ""
    hhmm = (f.get("start") or "0000").replace("h", "")
    name = f"{book['date']}_{hhmm}_{reg}" + (f"_{cn}" if cn else "") + ".igc"
    af = book.get("airfield") or {}
    return {
        "score_date": book["date"], "airfield": code, "airfield_name": af.get("name"),
        "takeoff_time": utc(f["start_tsp"]), "landing_time": utc(f.get("stop_tsp")),
        "landing_seen": f.get("stop_tsp") is not None,
        "start_local": f.get("start"), "stop_local": f.get("stop"), "tz": (af.get("time_info") or {}).get("tz_name"),
        "duration_s": f.get("duration"), "max_alt_m": f.get("max_alt"), "max_height_m": f.get("max_height"),
        "address": d["address"].upper(), "device_type": d.get("device_type"), "registration": d.get("registration"),
        "cn": cn, "aircraft": d.get("aircraft"), "aircraft_type": d.get("aircraft_type"),
        "tow": (tow.get("registration") or tow.get("address")) if tow else None, "towing": f.get("towing"),
        "warn": f.get("warn"), "file_name": name,
    }


class Folder:
    """Plain files: DIR/<year>/<name>.igc and DIR/index.jsonl, one line per flight (also what we skip on)."""

    def __init__(self, root):
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index = self.root / "index.jsonl"
        self.have = {}
        if self.index.exists():
            for line in self.index.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    self.have[r["id"]] = r

    def has(self, fid):
        return fid in self.have

    def _append(self, rec):
        with self.index.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        self.have[rec["id"]] = rec

    def put(self, fid, rec, blob, airfield=None):
        p = self.root / rec["score_date"][:4] / rec["file_name"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(blob)
        self._append({"id": fid, **rec, "file": str(p.relative_to(self.root)).replace("\\", "/"),
                      "fixes": n_fixes(blob), "bytes": len(blob), "fetched_at": now()})
        return p

    def lost(self, fid, rec, why, airfield=None):
        self._append({"id": fid, **rec, "file": None, "lost": why, "fetched_at": now()})


class Datastore(Folder):
    """The flights table and tracks/ogn/ in store.DATA, plus the plain files under store.DATA/igc."""

    INSERT = """INSERT OR REPLACE INTO flights (source, source_id, score_date, takeoff_time, landing_time,
                takeoff_airport, takeoff_country, takeoff_lat, takeoff_lon, aircraft, aircraft_kind,
                registration, comp_id, max_alt_m, raw, listed_at, stage) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""

    def __init__(self):
        store.init()
        super().__init__(store.DATA / "igc")
        self.db = store.connect()

    def has(self, fid):
        row = self.db.execute("SELECT track_path, track_error FROM flights WHERE source=? AND source_id=?",
                              (SOURCE, fid)).fetchone()
        return bool(row and (row[0] or row[1]))

    def _row(self, fid, rec, lat, lon, country):
        import focus
        try:
            stage = focus.stage_of(lat, lon, dt.date.fromisoformat(rec["score_date"]), focus.stages()) if lat else 0
        except Exception:
            stage = 0
        return (SOURCE, fid, rec["score_date"], rec["takeoff_time"], rec["landing_time"], rec["airfield"],
                country, lat, lon, rec["aircraft"], "glider" if rec.get("aircraft_type") == 1 else None,
                rec["registration"], rec["cn"], rec["max_alt_m"], json.dumps(rec), now(), stage)

    def put(self, fid, rec, blob, airfield=None):
        p = super().put(fid, rec, blob)
        rel = save_track(SOURCE, fid, blob)
        s = igc_summary(blob) or {}
        ll = ((airfield or {}).get("latlng") or [None, None])[:2]
        self.db.execute(self.INSERT, self._row(fid, rec, ll[0], ll[1], (airfield or {}).get("country")))
        self.db.execute("""UPDATE flights SET track_path=?, track_fetched_at=?, takeoff_lat=coalesce(?, takeoff_lat),
                           takeoff_lon=coalesce(?, takeoff_lon), max_alt_m=coalesce(?, max_alt_m), bbox=?
                           WHERE source=? AND source_id=?""",
                        (rel, now(), s.get("takeoff_lat"), s.get("takeoff_lon"), s.get("max_alt_m"), s.get("bbox"),
                         SOURCE, fid))
        self.db.commit()
        return p

    def lost(self, fid, rec, why, airfield=None):
        super().lost(fid, rec, why)
        ll = ((airfield or {}).get("latlng") or [None, None])[:2]
        self.db.execute(self.INSERT, self._row(fid, rec, ll[0], ll[1], (airfield or {}).get("country")))
        self.db.execute("UPDATE flights SET track_error=? WHERE source=? AND source_id=?", (why, SOURCE, fid))
        self.db.commit()


def run_once(sink, http, watch, airfields, days=2, log=print, stop=lambda: False):
    """One pass: the last `days` logbook days at each airfield, and the IGC file of every new watched flight."""
    new = lost = seen = 0
    for code in airfields:
        try:
            book = logbook(http, code)          # today, on the airfield's own calendar
        except Blocked:
            raise
        except Exception as e:
            log(f"ogn tracks: {code}: {e}")
            continue
        airfield = book.get("airfield") or {}
        if not airfield.get("name"):
            log(f"ogn tracks: FlightBook does not know airfield {code}")
            continue
        today = dt.date.fromisoformat(book["date"])
        for k in range(days):
            if stop():
                return new, lost, seen
            day = (today - dt.timedelta(days=k)).isoformat()
            if k:
                try:
                    book = logbook(http, code, day)
                except Blocked:
                    raise
                except Exception as e:
                    log(f"ogn tracks: {code} {day}: {e}")
                    continue
            for f, d in flights_of(book, watch):
                seen += 1
                fid = f"{d['address'].upper()}_{f['start_tsp']}"
                if sink.has(fid):
                    continue
                a, o = window(f)
                age = time.time() - (o or f["start_tsp"])
                if o is None and age < OPEN_END_AFTER_S:
                    continue                    # no landing yet: probably still airborne, look again later
                rec = record(book, f, d, code)
                try:
                    blob = fetch_igc(http, d["address"], a, o, day)
                except Blocked:
                    raise
                except Exception as e:
                    log(f"ogn tracks: {rec['file_name']}: {e}")
                    continue
                if n_fixes(blob) == 0:
                    if age > LOST_AFTER_S:
                        sink.lost(fid, rec, "no fixes left on FlightBook (older than 24 h)", airfield)
                        lost += 1
                        log(f"ogn tracks: LOST {rec['file_name']}: FlightBook has no fixes left")
                    continue
                p = sink.put(fid, rec, blob, airfield)
                new += 1
                log(f"ogn tracks: saved {p.name} ({n_fixes(blob)} fixes"
                    + ("" if rec["landing_seen"] else ", landing not detected, open-ended") + ")")
    return new, lost, seen


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=int, default=2, help="logbook days to read, counting back from today (default 2)")
    ap.add_argument("--out", help="plain folder mode: write IGC files and index.jsonl here instead of the datastore")
    ap.add_argument("--airfield", action="append", help="FlightBook airfield code(s) instead of the watch list's")
    ap.add_argument("--watch", action="append", help="extra device address(es) to watch, for testing")
    a = ap.parse_args()
    watch, airfields = watch_list()
    for addr in a.watch or []:
        watch[addr.upper()] = {"address": addr.upper()}
    if a.airfield:
        airfields = a.airfield
    if a.out:
        sink, logf = Folder(a.out), None
    else:
        sink = Datastore()
        logf = (store.DATA / "ogn_tracks.log").open("a", encoding="utf-8")

    def log(msg):
        line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
        print(line, flush=True)
        if logf:
            logf.write(line + "\n")
            logf.flush()

    def log_req(src, url, status, n):
        if not a.out:
            db = store.connect()
            store.log_request(db, src, url, status, n)
            db.commit()
            db.close()

    http = Polite(SOURCE, GAP_S, log_req)
    log(f"ogn tracks: watching {', '.join(sorted(watch))} at {', '.join(airfields)}, {a.days} day(s)")
    try:
        new, lost, seen = run_once(sink, http, watch, airfields, a.days, log)
    except Blocked as e:
        log(f"ogn tracks: STOPPED {e}")
        sys.exit(2)
    log(f"ogn tracks: {seen} watched flights in the logbooks, {new} new IGC files, {lost} lost")


if __name__ == "__main__":
    main()
