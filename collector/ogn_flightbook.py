"""OGN FlightBook (flightbook.glidernet.org): takeoffs and landings per airfield per day, no tracks.

API: /api/logbook/<code>/<YYYY-MM-DD>. History from about 2021, only where OGN receivers exist.
Codes: FlightBook knows many small US fields by their FAA code (Sterling = 3B3), bigger ones by ICAO
(Minden = KMEV), so we try the FAA code, then K + code, and remember which one answered.
An unknown code comes back with an empty airfield: that is "no OGN data", not "0 flights".
Devices of aircraft_type 1 are gliders; 2 are tow planes.
"""
import datetime as dt, gzip, json, re
from store import now

BASE = "https://flightbook.glidernet.org/api/logbook"
FIRST_DAY = dt.date(2021, 1, 1)
RECENT_DAYS = 3

def airfield_codes(operators):
    codes = []
    for o in operators:
        if o.get("rental") == "CLOSED":
            continue
        for c in re.findall(r"\(([A-Z0-9]{3,4})\)", o.get("airport", "")):
            if c not in codes:
                codes.append(c)
    return codes

def resolve(db, http, code):
    """FlightBook code for an FAA code, or None if FlightBook does not know the airfield."""
    row = db.execute("SELECT ogn FROM ogn_codes WHERE faa=?", (code,)).fetchone()
    if row:
        return row[0]
    probe = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    for cand in [code] + ([f"K{code}"] if len(code) == 3 and code.isalpha() else []):
        j = json.loads(http.get(f"{BASE}/{cand}/{probe}"))
        a = j.get("airfield") or {}
        if a.get("name"):
            ll = a.get("latlng") or [None, None]
            db.execute("INSERT OR REPLACE INTO ogn_codes VALUES (?,?,?,?,?,?)", (code, cand, a["name"], ll[0], ll[1], now()))
            db.commit()
            return cand
    db.execute("INSERT OR REPLACE INTO ogn_codes VALUES (?,?,?,?,?,?)", (code, None, None, None, None, now()))
    db.commit()
    return None

def fetch_day(db, http, ogn_code, day):
    j = json.loads(http.get(f"{BASE}/{ogn_code}/{day}"))
    devices = j.get("devices") or []
    flights = j.get("flights") or []
    gliders = sum(1 for f in flights if 0 <= (f.get("device") or 0) < len(devices)
                  and devices[f["device"]].get("aircraft_type") == 1)
    db.execute("INSERT OR REPLACE INTO ogn_days VALUES (?,?,?,?,?,?)",
               (ogn_code, day, len(flights), gliders, gzip.compress(json.dumps(j).encode()), now()))
    db.commit()
    return len(flights), gliders

def days_to_fetch(db, ogn_code, end, since=FIRST_DAY):
    have = {d for (d,) in db.execute("SELECT date FROM ogn_days WHERE airfield=?", (ogn_code,))}
    recent = end - dt.timedelta(days=RECENT_DAYS)
    d = end
    while d >= max(since, FIRST_DAY):
        if d.isoformat() not in have or d >= recent:
            yield d.isoformat()
        d -= dt.timedelta(days=1)
