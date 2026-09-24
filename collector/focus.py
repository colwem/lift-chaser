"""Where and when to collect first: space before time.

Martin's rule (2026-09-23): New England first, going back many years; once a couple of years are
in, widen the circle. The collectors work through STAGES in order and only start a stage when
every earlier stage is finished. Edit CENTER, RINGS_KM or RECENT_YEARS to change the focus.
"""
import datetime as dt, math

CENTER = (43.0, -71.9)          # middle of New England (central New Hampshire)
RINGS_KM = [300, 600, 1200, 2500, None]   # None = the rest of the world
RECENT_YEARS = 2
HISTORY_START = dt.date(2010, 1, 1)

def stages(today=None):
    """[(radius_km or None, first date)], e.g. (300, 2 years ago), (300, 2010), (600, 2 years ago), ..."""
    today = today or dt.date.today()
    recent = today.replace(year=today.year - RECENT_YEARS)
    out = []
    for r in RINGS_KM:
        out += [(r, recent), (r, HISTORY_START)]
    return out

def km(lat, lon, center=CENTER):
    """Great-circle distance from the centre, in km."""
    p1, p2 = math.radians(center[0]), math.radians(lat)
    dp, dl = p2 - p1, math.radians(lon - center[1])
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))

def stage_of(lat, lon, day, st):
    """Index of the first stage that covers this place and date."""
    if lat is None:
        return len(st) - 1
    d = km(lat, lon)
    for i, (r, since) in enumerate(st):
        if (r is None or d <= r) and day >= since:
            return i
    return len(st) - 1

def describe(i, st):
    r, since = st[i]
    where = "everywhere else" if r is None else f"within {r} km of New England"
    return f"stage {i + 1}/{len(st)}: {where}, from {since}"
