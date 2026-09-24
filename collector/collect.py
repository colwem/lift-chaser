"""Slowly collect glider flights into our own datastore (collector/store.py).

Runs each source in its own thread at its own polite pace, for --minutes, then stops cleanly.
Safe to stop at any time and run again: it resumes where it left off and never fetches a flight
or a track twice. A 403 or 429 from a source stops that source for this run (see polite.py).

  python collector/collect.py --minutes 60                 all sources
  python collector/collect.py --minutes 10 --only skylines
  python collector/collect.py --status                     what is in the datastore

Sources today: SkyLines (flights and IGC tracks), OGN FlightBook (daily takeoffs per airfield).
Planned: WeGlide (needs Martin's API key), OLC, SoaringSpot, our own OGN logger.
"""
import argparse, datetime as dt, json, pathlib, sys, threading, time, traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import focus, store, skylines, ogn_flightbook, olc
from polite import Polite, Blocked

ROOT = pathlib.Path(__file__).resolve().parent.parent

def log(msg):
    print(f"{dt.datetime.now():%H:%M:%S} {msg}", flush=True)

def http_for(source, gap, db_lock, opener=None):
    def log_req(src, url, status, n):
        with db_lock:
            db = store.connect(); store.log_request(db, src, url, status, n); db.commit(); db.close()
    return Polite(source, gap, log_req, opener)

def run_skylines(stop, lock):
    """Tracks strictly in focus.py stage order (New England first); list dates only when the
    current stage has no track waiting, so the listing digs back in time as the stages need."""
    db, http = store.connect(), http_for("skylines", 3.0, lock)
    st = focus.stages()
    for sid, raw in db.execute("""SELECT source_id, raw FROM flights WHERE source='skylines'
                                  AND takeoff_lat IS NULL AND track_path IS NULL""").fetchall():
        aid = (json.loads(raw).get("takeoffAirport") or {}).get("id")   # flights listed before staging existed
        if aid and not stop():
            lat, lon = skylines.airport(db, http, aid)
            db.execute("UPDATE flights SET takeoff_lat=?, takeoff_lon=? WHERE source='skylines' AND source_id=?", (lat, lon, sid))
            db.commit()
    skylines.restage(db, st)
    dates = skylines.dates_to_list(db, focus.HISTORY_START, dt.date.today())
    listed = tracks = 0
    shown = None
    while not stop():
        cur = skylines.current_stage(db, st)
        if cur >= len(st):
            log("skylines: every stage is complete"); break
        if cur != shown:
            log(f"skylines now on {focus.describe(cur, st)}"); shown = cur
        nxt = skylines.next_track(db, cur)
        if nxt:
            tracks += skylines.fetch_track(db, http, *nxt)
            continue
        day = next(dates, None)
        if day is None:
            break   # listing complete and nothing waiting in this stage; loop ends, next run moves on
        n, new = skylines.list_date(db, http, day, st)
        listed += 1
        if new:
            log(f"skylines listed {day}: {n} flights, {new} new")
    log(f"skylines done for this run: {listed} dates listed, {tracks} tracks downloaded")

def run_ogn(stop, lock):
    """Airfield-days in focus.py stage order: nearest airfields first, recent years first."""
    db, http = store.connect(), http_for("ogn", 8.0, lock)
    ops = json.loads((ROOT / "data/operators.json").read_text())
    for faa in ogn_flightbook.airfield_codes(ops):
        if stop(): return
        ogn_flightbook.resolve(db, http, faa)
    fields = db.execute("SELECT ogn, name, lat, lon FROM ogn_codes WHERE ogn IS NOT NULL").fetchall()
    end, st, n, done = dt.date.today(), focus.stages(), 0, set()
    for i, (r, since) in enumerate(st):
        ring = [c for c, _, la, lo in fields if r is None or focus.km(la, lo) <= r]
        queues = {c: ogn_flightbook.days_to_fetch(db, c, end, since) for c in ring}
        announced = False
        while queues and not stop():   # round-robin within the ring, newest days first
            for c in list(queues):
                if stop():
                    break
                day = next(queues[c], None)
                if day is None:
                    del queues[c]; continue
                if (c, day) in done:   # already fetched in an earlier stage of this run
                    continue
                done.add((c, day))
                if not announced:
                    log(f"ogn now on {focus.describe(i, st)}: {', '.join(ring)}"); announced = True
                flights, gliders = ogn_flightbook.fetch_day(db, http, c, day)
                n += 1
                if gliders:
                    log(f"ogn {c} {day}: {gliders} glider flights ({flights} incl. tows)")
        if stop():
            break
    log(f"ogn done for this run: {n} airfield-days fetched")

def run_olc(stop, lock):
    """OLC in focus.py stage order. SSA regions stand in for the rings (region 1 = New England).
    Per stage: list the days (one request per day and region), fetch each flight's details page,
    and download official IGC files for the best-placed flights, at most olc.IGC_PER_DAY a day."""
    db, http = store.connect(), http_for("olc", 5.0, lock, olc.OPENER)   # keeps the logged-in session
    st, today = focus.stages(), dt.date.today()
    listed = {k for (k,) in db.execute("SELECT key FROM listed WHERE source='olc'")}
    recent_cut = today - dt.timedelta(days=olc.RECENT_DAYS)
    n_list = n_det = n_igc = 0
    for i, (radius, since) in enumerate(st):
        ring = focus.RINGS_KM.index(radius)
        regions = [r for r, g in olc.REGION_RING.items() if g == ring]
        if not regions:
            continue
        log(f"olc now on {focus.describe(i, st)}: SSA regions {regions}")
        day = today
        while not stop():
            # 1. details for flights already listed in this stage or earlier
            ds = db.execute("""SELECT source_id FROM flights WHERE source='olc' AND pilot IS NULL AND stage<=?
                               ORDER BY stage, score_date DESC LIMIT 1""", (i,)).fetchone()
            if ds:
                olc.fetch_details(db, http, ds[0]); n_det += 1
                continue
            # 2. an IGC file, if today's allowance is not used up
            if not olc.LOGIN_NEEDED and olc.igc_today(db) < olc.IGC_PER_DAY:
                fetched = False
                for sid, raw in db.execute("""SELECT source_id, raw FROM flights WHERE source='olc' AND track_path IS NULL
                                              AND track_error IS NULL AND pilot IS NOT NULL AND stage<=?
                                              ORDER BY stage, score_date DESC LIMIT 50""", (i,)).fetchall():
                    fid = json.loads(raw).get("details", {}).get("igc_flight_id")
                    if not fid:   # the pilot did not make the IGC file public: skip it for good
                        db.execute("UPDATE flights SET track_error='no public IGC' WHERE source='olc' AND source_id=?", (sid,))
                        db.commit(); continue
                    n_igc += olc.fetch_igc(db, http, sid, fid); fetched = True
                    break
                if fetched:
                    continue
            # 3. list the next day of this stage
            while day >= max(since, olc.FIRST_DAY) and all(
                    f"{day}:R{r}" in listed and day < recent_cut for r in regions):
                day -= dt.timedelta(days=1)
            if day < max(since, olc.FIRST_DAY):
                break   # this stage is listed and detailed; move on
            for r in regions:
                if stop():
                    break
                n, new = olc.list_day(db, http, day, r, i)
                listed.add(f"{day}:R{r}"); n_list += 1
                if new:
                    log(f"olc {day} region {r}: {n} flights, {new} new")
            day -= dt.timedelta(days=1)
        if stop():
            break
    if olc.LOGIN_NEEDED == "claim":
        log("olc: logged in, but OLC only allows IGC downloads after you have claimed a valid flight "
            "of your own; skipping tracks until then")
    elif olc.LOGIN_NEEDED:
        log("olc: IGC downloads need a logged-in OLC user and the login did not work; "
            "check OLC_USER and OLC_PASSWORD (set with setx; see collector/olc.py)")
    log(f"olc done for this run: {n_list} day-regions listed, {n_det} flight pages read, {n_igc} IGC files")

SOURCES = {"skylines": run_skylines, "ogn": run_ogn, "olc": run_olc}

def status():
    db = store.connect()
    q = lambda s, *a: db.execute(s, a).fetchall()
    print(f"datastore: {store.DATA}")
    for src, n, t, first, last in q("""SELECT source, count(*), count(track_path), min(score_date), max(score_date)
                                        FROM flights GROUP BY source"""):
        print(f"  {src}: {n} flights ({t} with tracks), {first} to {last}")
    us = q("SELECT count(*) FROM flights WHERE takeoff_country='US'")[0][0]
    print(f"  of which took off in the US: {us}")
    st = focus.stages()
    oldest = q("SELECT min(key) FROM listed WHERE source='skylines'")[0][0]
    print(f"  skylines listing reaches back to {oldest}; tracks by stage (done / waiting):")
    for i in range(len(st)):
        d, w = q("""SELECT count(track_path), sum(track_path IS NULL AND track_error IS NULL AND private=0)
                    FROM flights WHERE source='skylines' AND stage=?""", i)[0]
        print(f"    {focus.describe(i, st)}: {d} / {w or 0}")
    for c, n, g, first, last in q("""SELECT airfield, count(*), sum(n_gliders), min(date), max(date)
                                     FROM ogn_days GROUP BY airfield ORDER BY sum(n_gliders) DESC"""):
        print(f"  ogn {c}: {n} days, {g} glider flights, {first} to {last}")
    print(f"  requests made: {q('SELECT count(*) FROM requests')[0][0]}, blocked (401/403/429): "
          f"{q('SELECT count(*) FROM requests WHERE status IN (401,403,429)')[0][0]}")
    size = sum(p.stat().st_size for p in store.DATA.rglob('*') if p.is_file()) / 1e6
    print(f"  disk: {size:.1f} MB")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=60)
    ap.add_argument("--only", choices=list(SOURCES), action="append")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    store.init()
    if a.status:
        return status()
    deadline = time.monotonic() + a.minutes * 60
    stop = lambda: time.monotonic() > deadline
    lock = threading.Lock()
    def guarded(name, fn):
        try:
            fn(stop, lock)
        except Blocked as e:
            log(f"STOPPED {e}")
        except Exception:
            log(f"ERROR in {name}:\n{traceback.format_exc()}")
    threads = [threading.Thread(target=guarded, args=(n, SOURCES[n])) for n in (a.only or SOURCES)]
    for t in threads: t.start()
    for t in threads: t.join()
    matched = store.match_duplicates(store.connect())
    if matched:
        log(f"linked {matched} flights seen in more than one source")
    status()

if __name__ == "__main__":
    main()
