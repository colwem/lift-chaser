"""SkyLines (skylines.aero): open-source flight archive with IGC tracks.

List: /api/flights/date/YYYY-MM-DD (public flights of that scoring date, worldwide).
Airport: /api/airports/<id> (name, ICAO, location [lon, lat]), looked up once per airport.
Track: /files/<igc filename>. History from about 2012; small volumes (about 620 US flights in 2025).

Listing is cheap (one request covers a whole day worldwide), so every date is listed, newest first.
Track downloads follow collector/focus.py: New England first, then wider rings.
"""
import datetime as dt, json
import focus
from store import now, save_track, igc_summary

BASE = "https://skylines.aero"
RECENT_DAYS = 14   # pilots upload late, so recent dates are listed again on every run

def airport(db, http, aid):
    row = db.execute("SELECT lat, lon FROM airports WHERE source='skylines' AND id=?", (str(aid),)).fetchone()
    if row:
        return row
    a = json.loads(http.get(f"{BASE}/api/airports/{aid}"))
    lon, lat = (a.get("location") or [None, None])[:2]
    db.execute("INSERT OR REPLACE INTO airports VALUES ('skylines',?,?,?,?,?,?)",
               (str(aid), a.get("name"), a.get("icao"), a.get("countryCode"), lat, lon))
    db.commit()   # never hold a write open across a network call: the other source's thread would wait
    return lat, lon

def list_date(db, http, day, st):
    d = json.loads(http.get(f"{BASE}/api/flights/date/{day}"))
    fresh = [f for f in d.get("flights", []) if not db.execute(
        "SELECT 1 FROM flights WHERE source='skylines' AND source_id=?", (str(f["id"]),)).fetchone()]
    # all network lookups first, then the writes in one short transaction
    coords = {ap["id"]: airport(db, http, ap["id"]) for f in fresh if (ap := f.get("takeoffAirport") or {}).get("id")}
    new = 0
    for f in fresh:
        ap = f.get("takeoffAirport") or {}
        lat, lon = coords.get(ap.get("id"), (None, None))
        model = f.get("model") or {}
        score_date = f.get("scoreDate") or day
        db.execute("""INSERT INTO flights (source, source_id, score_date, takeoff_time, landing_time,
              takeoff_airport, takeoff_country, takeoff_lat, takeoff_lon, aircraft, aircraft_kind, registration,
              comp_id, pilot, distance_km, speed_kmh, score, private, raw, listed_at, stage)
              VALUES ('skylines',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (str(f["id"]), score_date, f.get("takeoffTime"), f.get("landingTime"),
             ap.get("name"), ap.get("countryCode"), lat, lon, model.get("name"), model.get("type"),
             (f.get("registration") or "").upper().replace(" ", ""), f.get("competitionId"),
             (f.get("pilot") or {}).get("name") or f.get("pilotName"),
             (f.get("distance") or 0) / 1000, (f.get("speed") or 0) * 3.6, f.get("score"),
             int(bool(f.get("private")) or (f.get("privacyLevel") or 0) > 0), json.dumps(f), now(),
             focus.stage_of(lat, lon, dt.date.fromisoformat(score_date), st)))
        new += 1
    db.execute("INSERT OR REPLACE INTO listed VALUES ('skylines',?,?,?)", (day, now(), len(d.get("flights", []))))
    db.commit()
    return len(d.get("flights", [])), new

def dates_to_list(db, start, end):
    """Newest first. Dates listed before are skipped, except the last RECENT_DAYS."""
    done = {k for (k,) in db.execute("SELECT key FROM listed WHERE source='skylines'")}
    recent = end - dt.timedelta(days=RECENT_DAYS)
    d = end
    while d >= start:
        if d.isoformat() not in done or d >= recent:
            yield d.isoformat()
        d -= dt.timedelta(days=1)

def restage(db, st):
    """Recompute every waiting flight's stage (the 'last 2 years' boundary moves with the calendar)."""
    rows = db.execute("""SELECT source_id, takeoff_lat, takeoff_lon, score_date FROM flights
                         WHERE source='skylines' AND track_path IS NULL""").fetchall()
    db.executemany("UPDATE flights SET stage=? WHERE source='skylines' AND source_id=?",
                   [(focus.stage_of(la, lo, dt.date.fromisoformat(d), st), sid) for sid, la, lo, d in rows])
    db.commit()

def current_stage(db, st):
    """First stage not finished: listing has not reached back to its start date, or tracks are waiting."""
    oldest = db.execute("SELECT min(key) FROM listed WHERE source='skylines'").fetchone()[0] or "9999"
    for i, (_, since) in enumerate(st):
        waiting = db.execute("""SELECT 1 FROM flights WHERE source='skylines' AND track_path IS NULL
                                AND track_error IS NULL AND private=0 AND stage<=? LIMIT 1""", (i,)).fetchone()
        if oldest > since.isoformat() or waiting:
            return i
    return len(st)   # everything done

def next_track(db, stage):
    return db.execute("""SELECT source_id, raw FROM flights WHERE source='skylines' AND track_path IS NULL
                         AND track_error IS NULL AND private=0 AND stage<=?
                         ORDER BY stage, score_date DESC LIMIT 1""", (stage,)).fetchone()

def fetch_track(db, http, sid, raw):
    name = (json.loads(raw).get("igcFile") or {}).get("filename")
    try:
        blob = http.get(f"{BASE}/files/{name}")
    except Exception as e:
        if type(e).__name__ == "Blocked":
            raise
        db.execute("UPDATE flights SET track_error=? WHERE source='skylines' AND source_id=?", (repr(e)[:200], sid))
        db.commit()
        return False
    rel = save_track("skylines", sid, blob)
    s = igc_summary(blob) or {}
    db.execute("""UPDATE flights SET track_path=?, track_fetched_at=?, takeoff_lat=coalesce(?, takeoff_lat),
                  takeoff_lon=coalesce(?, takeoff_lon), max_alt_m=?, bbox=? WHERE source='skylines' AND source_id=?""",
               (rel, now(), s.get("takeoff_lat"), s.get("takeoff_lon"), s.get("max_alt_m"), s.get("bbox"), sid))
    db.commit()
    return True
