"""Model catalogue for fetch_models.py.

One entry per NOAA model. Adding a model (for example RRFS, operational from
2026-10-06) means adding one entry here; fetch_models.py has no model-specific code.

Field patterns are regexes matched against the GRIB2 .idx lines, which look like
"153:129628614:d=2026092312:HPBL:surface:18 hour fcst:". Only the matching byte
ranges are downloaded. Names and levels were checked against live .idx files on
2026-09-23.
"""

INST = r"(?:anl|\d+ hour fcst):$"          # instantaneous value at the valid time
AVE = r"\d+-\d+ hour ave fcst:$"            # time average ending at the valid time

def _fields(lftx, shtfl_suffix):
    return {
        "hpbl": r":HPBL:surface:" + INST,                  # boundary layer height, m
        "shtfl": r":SHTFL:surface:" + shtfl_suffix,        # sensible heat flux, W/m2
        "pres": r":PRES:surface:" + INST,                  # surface pressure, Pa
        "t2": r":TMP:2 m above ground:" + INST,            # K
        "d2": r":DPT:2 m above ground:" + INST,            # K
        "cape": r":CAPE:surface:" + INST,                  # J/kg
        "lftx": lftx + INST,                               # K
        "lcdc": r":LCDC:low cloud layer:" + INST,          # %
        "tcdc": r":TCDC:entire atmosphere:" + INST,        # %
        "prate": r":PRATE:surface:" + INST,                # kg/m2/s
        "gust": r":GUST:surface:" + INST,                  # m/s
        "u850": r":UGRD:850 mb:" + INST, "v850": r":VGRD:850 mb:" + INST,
        "u700": r":UGRD:700 mb:" + INST, "v700": r":VGRD:700 mb:" + INST,
    }

MODELS = {
    "hrrr": {
        "label": "HRRR 3 km",
        "note": "High-Resolution Rapid Refresh, NOAA, 3 km, instantaneous heat flux",
        "bases": ["https://noaa-hrrr-bdp-pds.s3.amazonaws.com",
                  "https://storage.googleapis.com/high-resolution-rapid-refresh"],
        "key": "hrrr.{c:%Y%m%d}/conus/hrrr.t{c:%H}z.wrfsfcf{f:02d}.grib2",
        "cycles": (0, 6, 12, 18),          # only these runs go out to 48 h
        "max_fhr": 48,
        "has_fhr": lambda f: 0 <= f <= 48,
        "days": 2,
        # output image: longitude range, latitude range, pixel size in degrees of longitude
        "out": {"lon": (-134.5, -60.5), "lat": (21.0, 53.0), "dlon": 0.03},
        "fields": _fields(r":LFTX:500-1000 mb:", INST),
    },
    "gfs": {
        "label": "GFS 25 km",
        "note": "Global Forecast System, NOAA, 0.25 deg; heat flux is a time average",
        "bases": ["https://noaa-gfs-bdp-pds.s3.amazonaws.com",
                  "https://storage.googleapis.com/global-forecast-system"],
        "key": "gfs.{c:%Y%m%d}/{c:%H}/atmos/gfs.t{c:%H}z.pgrb2.0p25.f{f:03d}",
        "cycles": (0, 6, 12, 18),
        "max_fhr": 180,
        "has_fhr": lambda f: 0 <= f <= 120 or (120 < f <= 384 and f % 3 == 0),
        "days": 7,
        "out": {"lon": (-130.0, -60.0), "lat": (20.0, 55.0), "dlon": 0.25},
        "fields": _fields(r":LFTX:surface:", AVE),
        "optional": {"shtfl"},   # hour 0 (the analysis) has no time-averaged flux, so no W* then
    },
}

# Output variables: stored as 8-bit PNGs, value = lo + byte * (hi - lo) / 254, byte 255 = no data.
# Units are the page's display units. Ranges are wide enough not to clip real values;
# the page's color scales are separate and can be narrower.
OUT_VARS = {
    "score": {"lo": 0, "hi": 10, "unit": ""},
    "wstar": {"lo": 0, "hi": 1200, "unit": "fpm"},
    "blh":   {"lo": 0, "hi": 15000, "unit": "ft"},
    "cbase": {"lo": 0, "hi": 18000, "unit": "ft"},
    "w850":  {"lo": 0, "hi": 80, "unit": "kt"},
    "d850":  {"lo": 0, "hi": 360, "unit": "deg"},
    "w700":  {"lo": 0, "hi": 100, "unit": "kt"},
    "gust":  {"lo": 0, "hi": 80, "unit": "kt"},
    "cape":  {"lo": 0, "hi": 5000, "unit": "J/kg"},
    "li":    {"lo": -15, "hi": 15, "unit": ""},
    "low":   {"lo": 0, "hi": 100, "unit": "%"},
    "tcdc":  {"lo": 0, "hi": 100, "unit": "%"},
    "prate": {"lo": 0, "hi": 20, "unit": "mm/h"},
}

# Local hours shown on the map (Eastern time). 08:00 to 21:00 ET also covers
# 11:00 to 17:00 local in the Mountain and Pacific time zones for site scores.
MAP_TZ = "America/New_York"
MAP_HOURS = range(8, 22)

# Time zone per state for site forecasts; a few states are split, handled by longitude.
STATE_TZ = {
    **dict.fromkeys("CT DE DC GA MA MD ME NC NH NJ NY OH PA RI SC VA VT WV MI".split(), "America/New_York"),
    **dict.fromkeys("AL AR IA IL LA MN MO MS OK WI".split(), "America/Chicago"),
    **dict.fromkeys("CO MT NM UT WY".split(), "America/Denver"),
    **dict.fromkeys("CA NV WA".split(), "America/Los_Angeles"),
    "AZ": "America/Phoenix", "HI": "Pacific/Honolulu", "AK": "America/Anchorage",
}
SPLIT_TZ = {  # state: (longitude boundary, zone east of it, zone west of it)
    "FL": (-85.0, "America/New_York", "America/Chicago"),
    "TN": (-85.6, "America/New_York", "America/Chicago"),
    "KY": (-86.0, "America/New_York", "America/Chicago"),
    "IN": (-87.0, "America/New_York", "America/Chicago"),
    "TX": (-104.9, "America/Chicago", "America/Denver"),
    "KS": (-101.5, "America/Chicago", "America/Denver"),
    "NE": (-101.0, "America/Chicago", "America/Denver"),
    "SD": (-100.5, "America/Chicago", "America/Denver"),
    "ND": (-101.0, "America/Chicago", "America/Denver"),
    "ID": (-115.0, "America/Denver", "America/Los_Angeles"),
    "OR": (-117.5, "America/Denver", "America/Los_Angeles"),
}

def site_tz(op):
    state = op["city"].rsplit(",", 1)[-1].strip()
    if state in SPLIT_TZ:
        lon_b, east, west = SPLIT_TZ[state]
        return east if op["lon"] >= lon_b else west
    return STATE_TZ.get(state, "America/New_York")
