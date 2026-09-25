"""Our own OGN receiver-side logger: record the club ships' positions straight from the OGN feed.

This is the fallback for the day FlightBook is down. It needs a machine that is on while the club
flies (the homelab, not the laptop), and it records only what it hears while connected.

The feed is APRS-IS (Automatic Packet Reporting System, Internet Service) at aprs.glidernet.org port
14580, plain text over TCP (checked live 2026-09-24). Read-only login: "user <name> pass -1 vers
<app> <version> filter <filter>". The server answers "# logresp <name> unverified, server GLIDERNx",
sends a "# aprsc ..." line about every 20 s as a keep-alive, and drops the connection if we send
nothing, so we send a "# keepalive" line every minute. Filters (www.aprs-is.net/javAPRSFilter.aspx):
b/CALL1/CALL2 passes named senders; r/lat/lon/km passes everything within a radius. A sender's
callsign is the tracker's address with a prefix for its type: FLR (FLARM), OGN (OGN tracker),
ICA (ICAO address); we subscribe to all three spellings of each watched address.

A position line looks like (OGN-flavoured APRS, wiki.glidernet.org/wiki:ogn-flavoured-aprs):
  ICAA4FFEE>OGNTRK,qAS,3B3:/171148h4225.55N/07147.58W'155/046/A=001503 !W17! id05A4FFEE -217fpm ...
  callsign>tocall,path,receiver:/HHMMSSh DDMM.mmN/DDDMM.mmW course/speed(kt)/A=altitude(ft)
  !Wxy! adds a third decimal to minutes; idTTAAAAAA has flags and type bits; then climb (fpm), turn rate.

  python collector/ogn_aprs.py                  run until stopped; writes <datastore>/aprs/<date>.log
  python collector/ogn_aprs.py --to-igc FILE    convert one day's log into IGC files, one per aircraft
The daily log keeps raw lines (nothing is lost); --to-igc makes plain IGC files from them, one flight
per aircraft per day (no takeoff and landing detection yet; FlightBook does that better).
"""
import argparse, datetime as dt, pathlib, re, socket, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import store

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOST, PORT = "aprs.glidernet.org", 14580
APP = ("chase-lift", "0.1")
PREFIXES = ("FLR", "OGN", "ICA")
POS = re.compile(r"^(?P<call>[A-Z0-9]+)>[^:]*,(?P<rx>[A-Za-z0-9-]+):/(?P<t>\d{6})h(?P<lat>\d{4}\.\d{2})(?P<ns>[NS])"
                 r".(?P<lon>\d{5}\.\d{2})(?P<ew>[EW]).(?P<crs>\d{3})/(?P<spd>\d{3})/A=(?P<alt>-?\d{6})"
                 r"(?: !W(?P<w1>\d)(?P<w2>\d)!)?(?P<rest>.*)$")


def watched_calls():
    from ogn_tracks import watch_list
    watch, _ = watch_list()
    return [p + a for a in sorted(watch) for p in PREFIXES]


def connect(filter_str, user="CHASELIFT"):
    s = socket.create_connection((HOST, PORT), timeout=90)
    f = s.makefile("rwb", buffering=0)
    f.readline()                                                       # "# aprsc ..." banner
    f.write(f"user {user} pass -1 vers {APP[0]} {APP[1]} filter {filter_str}\r\n".encode())
    resp = f.readline().decode("latin1").strip()
    if "logresp" not in resp:
        raise ConnectionError(f"unexpected login answer: {resp}")
    return s, f


def log_forever(calls, out_dir, log=print):
    filt = "b/" + "/".join(calls)
    out_dir.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            s, f = connect(filt)
            log(f"ogn aprs: connected, filter {filt}")
            last_keepalive = time.monotonic()
            while True:
                line = f.readline()
                if not line:
                    raise ConnectionError("server closed the connection")
                text = line.decode("latin1").rstrip("\r\n")
                if not text.startswith("#"):
                    day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
                    with (out_dir / f"{day}.log").open("a", encoding="latin1") as o:
                        o.write(f"{int(time.time())} {text}\n")
                if time.monotonic() - last_keepalive > 60:
                    f.write(b"# keepalive chase-lift\r\n")
                    last_keepalive = time.monotonic()
        except (OSError, ConnectionError) as e:
            log(f"ogn aprs: {e}; reconnecting in 30 s")
            time.sleep(30)


def parse(text):
    m = POS.match(text)
    if not m:
        return None
    g = m.groupdict()
    lat = int(g["lat"][:2]) + float(g["lat"][2:] + (g["w1"] or "0")) / 60
    lon = int(g["lon"][:3]) + float(g["lon"][3:] + (g["w2"] or "0")) / 60
    return {"call": g["call"], "rx": g["rx"], "hms": g["t"], "lat": -lat if g["ns"] == "S" else lat,
            "lon": -lon if g["ew"] == "W" else lon, "alt_m": int(g["alt"]) * 0.3048,
            "course": int(g["crs"]), "speed_kt": int(g["spd"])}


def to_igc(log_path, out_dir):
    """One IGC file per aircraft from a day's raw log. Fixes are in UTC; the log's date is the UTC day."""
    day = pathlib.Path(log_path).stem                                  # YYYY-MM-DD
    by_call = {}
    for line in pathlib.Path(log_path).read_text(encoding="latin1").splitlines():
        p = parse(line.split(" ", 1)[1]) if " " in line else None
        if p:
            by_call.setdefault(p["call"], []).append(p)
    out_dir.mkdir(parents=True, exist_ok=True)
    for call, fixes in by_call.items():
        fixes.sort(key=lambda p: p["hms"])
        d = dt.date.fromisoformat(day)
        lines = ["AXXXchase-lift OGN APRS logger", f"HFDTEDATE:{d:%d%m%y}", f"HFGIDGLIDERID:{call}",
                 "HFFTYFRTYPE:OGN APRS feed via chase-lift", "HFDTMGPSDATUM:WGS84"]
        for p in fixes:
            la, lo = abs(p["lat"]), abs(p["lon"])
            lines.append(f"B{p['hms']}{int(la):02d}{int((la % 1) * 60000):05d}{'S' if p['lat'] < 0 else 'N'}"
                         f"{int(lo):03d}{int((lo % 1) * 60000):05d}{'W' if p['lon'] < 0 else 'E'}"
                         f"A00000{int(p['alt_m']):05d}")
        (out_dir / f"{day}_{call}.igc").write_bytes(("\r\n".join(lines) + "\r\n").encode("ascii"))
    return len(by_call)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--to-igc", metavar="LOG", help="convert one day's raw log to IGC files instead of listening")
    ap.add_argument("--minutes", type=float, help="listen for this long, then stop (default: forever)")
    a = ap.parse_args()
    out = store.DATA / "aprs"
    if a.to_igc:
        n = to_igc(a.to_igc, out / "igc")
        print(f"wrote {n} IGC file(s) to {out / 'igc'}")
        return
    calls = watched_calls()
    if a.minutes:
        import threading
        threading.Thread(target=log_forever, args=(calls, out), daemon=True).start()
        time.sleep(a.minutes * 60)
        return
    log_forever(calls, out)


if __name__ == "__main__":
    main()
