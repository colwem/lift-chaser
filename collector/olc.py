"""OLC (OnLine Contest, onlinecontest.org): the largest glider flight archive, US days back to 2007.

What we use, all of it what the public site itself serves to any visitor:
  1. Flights of a day and region: POST to the daily page with Accept: application/x-olc-flighttraces
     returns [{dsId, id}, ...], the list the page's map uses.
  2. Flight details: the public flight page flightinfo.html?dsId=... (pilot, glider, registration,
     airfield, points, distance, speed, duration, club).
  3. Tracks: the official IGC download, download.html?flightId=..., kept under OLC's limit of
     about 10 files a day.
What we do not do: decode the map traces (/api/maps/trace/...). OLC scrambles them on purpose,
and unscrambling them would be defeating a protection (see docs/glider-flights-plan.md).

US regions are the SSA regions; region 1 is New England. Seasons run October to September and
overlap in September and October, so those months are listed under both seasons.
"""
import datetime as dt, html, http.cookiejar, json, os, re, urllib.request
from store import now, save_track, igc_summary

BASE = "https://www.onlinecontest.org/olc-3.0/gliding"
FIRST_DAY = dt.date(2007, 1, 1)
IGC_PER_DAY = 9            # OLC's terms allow about 10 IGC files a day; stay under it
RECENT_DAYS = 10           # recent days are listed again (late uploads)
# SSA region -> ring index in focus.RINGS_KM (0 = New England)
REGION_RING = {1: 0, 2: 1, 3: 1, 4: 2, 6: 2, 5: 3, 7: 3, 8: 4, 9: 4, 10: 4, 11: 4, 12: 4}

def seasons(day):
    main = day.year + 1 if day.month >= 10 else day.year
    return [main, main + 1] if day.month == 9 else [main - 1, main] if day.month == 10 else [main]

def list_day(db, http, day, region, stage):
    ids = {}
    for sp in seasons(day):
        url = f"{BASE}/daily.html?st=olcp&rt=olc&df={day}&sp={sp}&c=US&sc={region}"
        body = http.post_json(url, {"t": "daily"}, accept="application/x-olc-flighttraces")
        for f in json.loads(body or b"[]"):
            ids[str(f["dsId"])] = f
    new = 0
    for ds, f in ids.items():
        cur = db.execute("""INSERT OR IGNORE INTO flights (source, source_id, score_date, takeoff_country, raw,
                            listed_at, stage) VALUES ('olc',?,?,'US',?,?,?)""",
                         (ds, day.isoformat(), json.dumps({"trace": f, "region": region}), now(), stage))
        new += cur.rowcount
    db.execute("INSERT OR REPLACE INTO listed VALUES ('olc',?,?,?)", (f"{day}:R{region}", now(), len(ids)))
    db.commit()
    return len(ids), new

def _text_lines(page):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.S)
    return [l.strip() for l in html.unescape(re.sub(r"<[^>]+>", "\n", t)).splitlines() if l.strip()]

def _after(lines, label):
    for i, l in enumerate(lines):
        if l.rstrip(":") == label.rstrip(":") and i + 1 < len(lines):
            return lines[i + 1]
    return None

def _num(s):
    m = re.search(r"-?[\d.,]+", s or "")
    return float(m.group(0).replace(",", "")) if m else None

def parse_flightinfo(page):
    L = _text_lines(page)
    head = L[L.index("Flight information") + 1:] if "Flight information" in L else L
    pilot = head[1] if len(head) > 1 and head[0] == "-" else None
    airfield = next((l.split(":", 1)[1].strip() for l in L if l.startswith("Airfield:")), None)
    igc = re.search(r'download\.html\?flightId=(\d+)"', page)
    return {
        "pilot": pilot,
        "aircraft": _after(L, "Type of glider:"),
        "registration": (_after(L, "Callsign:") or "").upper().replace(" ", ""),
        "comp_id": _after(L, "Competition-ID:"),
        "airfield": re.sub(r"\s*\(.*\)$", "", airfield) if airfield else None,
        "points": _num(_after(L, "Points for the flight")),
        "distance_km": _num(_after(L, "scoring distance")),
        "speed_kmh": _num(_after(L, "Speed")),
        "duration": _after(L, "Duration"),
        "club": _after(L, "Club"),
        "igc_flight_id": igc.group(1) if igc else None,
    }

def fetch_details(db, http, ds):
    """Read a flight's public page once. pilot is set to '' when unknown, so a flight is never read twice."""
    try:
        blob = http.get(f"{BASE}/flightinfo.html?dsId={ds}")
        page = blob.decode("utf-8", "replace")
        if "�" in page:   # some OLC pages are Windows-1252, not UTF-8 (e.g. "Glasflügel")
            page = blob.decode("cp1252", "replace")
    except Exception as e:
        if type(e).__name__ == "Blocked":
            raise
        db.execute("UPDATE flights SET pilot='', track_error=? WHERE source='olc' AND source_id=?", (repr(e)[:200], ds))
        db.commit()
        return None
    d = parse_flightinfo(page)
    d["pilot"] = d["pilot"] or ""
    raw = json.loads(db.execute("SELECT raw FROM flights WHERE source='olc' AND source_id=?", (ds,)).fetchone()[0])
    raw["details"] = d
    db.execute("""UPDATE flights SET pilot=?, aircraft=?, aircraft_kind='glider', registration=?, comp_id=?,
                  takeoff_airport=?, distance_km=?, speed_kmh=?, score=?, raw=? WHERE source='olc' AND source_id=?""",
               (d["pilot"], d["aircraft"], d["registration"], d["comp_id"], d["airfield"], d["distance_km"],
                d["speed_kmh"], d["points"], json.dumps(raw), ds))
    db.commit()
    return d

def igc_today(db):
    return db.execute("""SELECT count(*) FROM requests WHERE source='olc' AND url LIKE '%download.html?flightId=%'
                         AND status=200 AND at >= ?""", (dt.date.today().isoformat(),)).fetchone()[0]

# ---------- logged-in session, for the IGC download ----------
# OLC lets each registered user download about 10 IGC files a day, from pilots who allow it.
# The collector logs in as Martin with OLC_USER and OLC_PASSWORD, which Martin sets himself
# (setx ...); the values are never written to code, logs or the datastore.
JAR = http.cookiejar.CookieJar()
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(JAR))
SECURE = "https://www.onlinecontest.org/olc-3.0/secure"
LOGIN_NEEDED = False
_login_tried = False

def _setting(name):
    """An environment variable, or on Windows the user-level value saved by setx (which programs
    started before the setx do not see)."""
    v = os.environ.get(name)
    if not v and os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                v = winreg.QueryValueEx(k, name)[0]
        except OSError:
            v = None
    return v

def logged_in(http):
    page = http.get(f"{SECURE}/memberadmin.html").decode("utf-8", "replace")
    return 'name="_name__"' not in page      # the header login form disappears once logged in

def login(http):
    """Log in with OLC_USER / OLC_PASSWORD. Returns True if OLC then treats us as logged in."""
    user, pw = _setting("OLC_USER"), _setting("OLC_PASSWORD")
    if not (user and pw):
        return False
    # Submit the full login page's form as a browser would: its hidden field and submit button
    # are part of what the server expects, next to username and password.
    page = http.get(f"{SECURE}/login.html").decode("utf-8", "replace")
    # the page has four login forms; the full one is the one that also offers name and birthday
    form = next((f for f in re.findall(r"<form[^>]*>.*?</form>", page, re.S) if "loginFirstName" in f), "")
    fields = {}
    for tag in re.findall(r"<input[^>]*>", form):
        attr = dict(re.findall(r'([\w.:-]+)="([^"]*)"', tag))
        if attr.get("type") in ("hidden", "submit") and attr.get("name"):
            fields[attr["name"]] = html.unescape(attr.get("value", ""))
    fields.update({"_ident_": user, "_name__": pw})
    http.post_form(f"{SECURE}/login.html", fields)
    return logged_in(http)

def fetch_igc(db, http, ds, flight_id):
    """Official IGC download, as the logged-in user. If OLC answers with its login page, log in
    (once per run) and retry; if that fails, stop downloading tracks for this run."""
    global LOGIN_NEEDED, _login_tried
    blob = http.get(f"{BASE}/download.html?flightId={flight_id}")
    if b"claim a valid flight" in blob:
        # OLC only lets users who have claimed a valid flight of their own download others' IGC files
        # (checked 2026-09-23). Nothing to do but wait until Martin has claimed one.
        LOGIN_NEEDED = "claim"
        return False
    if b"login" in blob[:20000].lower() and not blob.lstrip().startswith(b"A"):
        if not _login_tried:
            _login_tried = True
            if login(http):
                return fetch_igc(db, http, ds, flight_id)
        LOGIN_NEEDED = True                     # leave the flight waiting for the next run
        return False
    if not blob.lstrip().startswith(b"A"):      # not an IGC file (e.g. a limit page)
        db.execute("UPDATE flights SET track_error=? WHERE source='olc' AND source_id=?", ("not an IGC file", ds))
        db.commit()
        return False
    rel = save_track("olc", ds, blob)
    s = igc_summary(blob) or {}
    db.execute("""UPDATE flights SET track_path=?, track_fetched_at=?, takeoff_lat=?, takeoff_lon=?, max_alt_m=?, bbox=?
                  WHERE source='olc' AND source_id=?""",
               (rel, now(), s.get("takeoff_lat"), s.get("takeoff_lon"), s.get("max_alt_m"), s.get("bbox"), ds))
    db.commit()
    return True
