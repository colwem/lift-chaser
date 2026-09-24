"""Our own flight datastore: one SQLite file plus compressed track files.

Every flight is stored once per source, keyed by (source, source_id), so nothing is ever fetched
twice: listing a date only adds flights we have not seen, and a track is downloaded only when
track_path is empty. Flights seen in more than one source are linked later through
(registration, takeoff_time); see match_duplicates().

Location: $CHASE_LIFT_DATA, default ~/chase-lift-data (kept out of OneDrive, which can corrupt a
busy SQLite file, and out of the Git repo).
"""
import datetime as dt, gzip, json, os, pathlib, sqlite3

DATA = pathlib.Path(os.environ.get("CHASE_LIFT_DATA", pathlib.Path.home() / "chase-lift-data"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS flights (
  source TEXT NOT NULL,            -- skylines, weglide, olc, soaringspot, ogn
  source_id TEXT NOT NULL,
  score_date TEXT,                 -- local flying date as the source reports it, YYYY-MM-DD
  takeoff_time TEXT, landing_time TEXT,   -- UTC ISO 8601
  takeoff_airport TEXT, takeoff_country TEXT,
  takeoff_lat REAL, takeoff_lon REAL,     -- from the track when the source gives no position
  aircraft TEXT, aircraft_kind TEXT, registration TEXT, comp_id TEXT, pilot TEXT,
  distance_km REAL, speed_kmh REAL, score REAL,
  max_alt_m REAL, bbox TEXT,              -- from the track: [west, south, east, north]
  private INTEGER DEFAULT 0,
  raw TEXT,                        -- the source's record as JSON, so nothing is lost
  listed_at TEXT NOT NULL,
  track_path TEXT, track_fetched_at TEXT, track_error TEXT,
  same_as TEXT,                    -- "source:source_id" of the record this duplicates, if any
  stage INTEGER,                   -- download priority from focus.py: 0 = New England, recent
  PRIMARY KEY (source, source_id)
);
CREATE INDEX IF NOT EXISTS flights_date ON flights(score_date);
CREATE INDEX IF NOT EXISTS flights_reg_time ON flights(registration, takeoff_time);

-- Dates (or airfield-dates) already listed, so a backfill resumes where it stopped.
CREATE TABLE IF NOT EXISTS listed (
  source TEXT NOT NULL, key TEXT NOT NULL, listed_at TEXT NOT NULL, n INTEGER,
  PRIMARY KEY (source, key)
);

-- OGN FlightBook: one row per airfield and day (takeoffs and landings, no tracks).
CREATE TABLE IF NOT EXISTS ogn_days (
  airfield TEXT NOT NULL, date TEXT NOT NULL,
  n_flights INTEGER, n_gliders INTEGER, raw BLOB,   -- raw = gzip-compressed JSON logbook
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (airfield, date)
);

-- Every request we make, for politeness budgets and to show what was done.
CREATE TABLE IF NOT EXISTS requests (
  source TEXT, url TEXT, status INTEGER, bytes INTEGER, at TEXT
);
"""

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def init():
    """Create the datastore and tables. Call once, before any threads start."""
    DATA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATA / "flights.db", timeout=60)
    db.execute("PRAGMA journal_mode=WAL")   # lets readers and one writer work at the same time
    db.executescript(SCHEMA)
    if "stage" not in {r[1] for r in db.execute("PRAGMA table_info(flights)")}:   # datastores made before 2026-09-23
        db.execute("ALTER TABLE flights ADD COLUMN stage INTEGER")
    db.execute("CREATE INDEX IF NOT EXISTS flights_stage ON flights(source, stage, score_date)")
    db.execute("CREATE TABLE IF NOT EXISTS ogn_codes (faa TEXT PRIMARY KEY, ogn TEXT, name TEXT, lat REAL, lon REAL, checked_at TEXT)")
    # airports as each source describes them, looked up once, for the space-first ordering in focus.py
    db.execute("""CREATE TABLE IF NOT EXISTS airports (source TEXT, id TEXT, name TEXT, icao TEXT, country TEXT,
                  lat REAL, lon REAL, PRIMARY KEY (source, id))""")
    db.commit(); db.close()

def connect():
    return sqlite3.connect(DATA / "flights.db", timeout=60)   # sources write from separate threads

def track_file(source, source_id, ext="igc"):
    """Where a track is stored: tracks/<source>/<last 3 digits>/<id>.<ext>.gz"""
    p = DATA / "tracks" / source / str(source_id)[-3:].zfill(3) / f"{source_id}.{ext}.gz"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def save_track(source, source_id, blob, ext="igc"):
    p = track_file(source, source_id, ext)
    with gzip.open(p, "wb", compresslevel=6) as f:
        f.write(blob)
    return str(p.relative_to(DATA))

def read_track(rel_path):
    with gzip.open(DATA / rel_path, "rb") as f:
        return f.read()

def log_request(db, source, url, status, nbytes=0):
    db.execute("INSERT INTO requests VALUES (?,?,?,?,?)", (source, url, status, nbytes, now()))

def igc_summary(blob):
    """Takeoff position, bounding box and max GPS altitude from an IGC file's B records."""
    lats, lons, alts = [], [], []
    for line in blob.decode("ascii", "replace").splitlines():
        if len(line) >= 35 and line[0] == "B" and line[24] in "AV":
            try:
                lat = int(line[7:9]) + int(line[9:14]) / 60000
                lon = int(line[15:18]) + int(line[18:23]) / 60000
                lat = -lat if line[14] == "S" else lat
                lon = -lon if line[23] == "W" else lon
                lats.append(lat); lons.append(lon); alts.append(int(line[30:35]))
            except ValueError:
                continue
    if not lats:
        return None
    return {"takeoff_lat": round(lats[0], 5), "takeoff_lon": round(lons[0], 5), "max_alt_m": max(alts),
            "bbox": json.dumps([round(min(lons), 4), round(min(lats), 4), round(max(lons), 4), round(max(lats), 4)])}

def match_duplicates(db):
    """Link flights that appear in several sources: same registration, takeoff within 10 minutes."""
    rows = db.execute("""SELECT a.source, a.source_id, b.source, b.source_id FROM flights a JOIN flights b
                         ON a.registration = b.registration AND a.registration <> ''
                         AND a.source < b.source AND a.same_as IS NULL AND b.same_as IS NULL
                         AND abs(julianday(a.takeoff_time) - julianday(b.takeoff_time)) < 10.0 / 1440""").fetchall()
    for s1, i1, s2, i2 in rows:
        db.execute("UPDATE flights SET same_as=? WHERE source=? AND source_id=?", (f"{s1}:{i1}", s2, i2))
    db.commit()
    return len(rows)
