# Glider type reference. Nominal manufacturer / type-data figures, SI units.
# ld = max glide ratio; v_ld = speed for best glide (km/h); sink = min sink (m/s);
# vne = never-exceed speed (km/h); span in m. cockpit: tall-pilot reputation.
# approx=True where the figure is from secondary sources or memory and must be checked
# against the Flight Manual / POH (Pilot's Operating Handbook) before relying on it.
TYPES = {
 "2-33":   dict(name="Schweizer SGS 2-33A", cls="Trainer (metal)", seats=2, span=15.5, ld=23, v_ld=72,  sink=0.94, vne=158, cockpit="Roomy", approx=False),
 "2-32":   dict(name="Schweizer SGS 2-32",  cls="Two-seat (metal)", seats=3, span=17.4, ld=34, v_ld=95,  sink=0.73, vne=254, cockpit="Roomy", approx=False),
 "2-22":   dict(name="Schweizer SGU 2-22",  cls="Trainer (vintage)", seats=2, span=13.4, ld=17, v_ld=77,  sink=1.0,  vne=116, cockpit="Tight", approx=True),
 "1-26":   dict(name="Schweizer SGS 1-26",  cls="One-design (metal)", seats=1, span=12.2, ld=23, v_ld=85,  sink=0.82, vne=183, cockpit="Tight headroom", approx=False),
 "1-34":   dict(name="Schweizer SGS 1-34",  cls="Standard (metal)", seats=1, span=15.0, ld=34, v_ld=85,  sink=0.67, vne=212, cockpit="OK", approx=False),
 "1-35":   dict(name="Schweizer SGS 1-35",  cls="15 m (metal)", seats=1, span=15.0, ld=38, v_ld=97,  sink=0.61, vne=241, cockpit="Reclined, check", approx=True),
 "1-36":   dict(name="Schweizer SGS 1-36 Sprite", cls="Sport (metal)", seats=1, span=14.1, ld=31, v_ld=85, sink=0.67, vne=194, cockpit="OK", approx=True),
 "1-23":   dict(name="Schweizer SGS 1-23", cls="Standard (vintage metal)", seats=1, span=15.2, ld=29, v_ld=80, sink=0.70, vne=225, cockpit="Unknown", approx=True),
 "L-23":   dict(name="LET L-23 Super Blanik", cls="Trainer (metal)", seats=2, span=16.2, ld=28, v_ld=90, sink=0.75, vne=250, cockpit="Roomy", approx=False),
 "L-13":   dict(name="LET L-13 Blanik", cls="Trainer (metal)", seats=2, span=16.2, ld=28, v_ld=85, sink=0.82, vne=253, cockpit="Roomy", approx=False),
 "L-33":   dict(name="LET L-33 Solo", cls="Club (metal)", seats=1, span=14.1, ld=34, v_ld=85, sink=0.66, vne=250, cockpit="OK", approx=True),
 "ASK-21": dict(name="Schleicher ASK-21", cls="Two-seat trainer (GRP)", seats=2, span=17.0, ld=34, v_ld=90, sink=0.65, vne=280, cockpit="Tight for very tall (did not fit Martin)", approx=False),
 "ASK-13": dict(name="Schleicher ASK-13", cls="Trainer (wood/tube)", seats=2, span=16.0, ld=28, v_ld=90, sink=0.81, vne=200, cockpit="Roomy", approx=False),
 "ASW-19": dict(name="Schleicher ASW-19B", cls="Standard (GRP)", seats=1, span=15.0, ld=38.5, v_ld=100, sink=0.60, vne=255, cockpit="Tight above ~6'2\"", approx=False),
 "PW-6":   dict(name="PZL PW-6U", cls="Two-seat trainer (GRP)", seats=2, span=16.0, ld=34, v_ld=95, sink=0.74, vne=260, cockpit="Fairly roomy front", approx=True),
 "PW-5":   dict(name="PZL PW-5 Smyk", cls="World Class (GRP)", seats=1, span=13.44, ld=33, v_ld=80, sink=0.64, vne=220, cockpit="Small", approx=False),
 "G103":   dict(name="Grob G103 Twin Astir / Twin II", cls="Two-seat (GRP)", seats=2, span=17.5, ld=36.5, v_ld=105, sink=0.62, vne=250, cockpit="Good, depends on proportions", approx=False),
 "G103C":  dict(name="Grob G103C Twin III", cls="Two-seat (GRP)", seats=2, span=18.0, ld=38, v_ld=105, sink=0.60, vne=260, cockpit="Good, depends on proportions", approx=True),
 "G102":   dict(name="Grob G102 Astir (CS / Club / Std III)", cls="Club/Standard (GRP)", seats=1, span=15.0, ld=37, v_ld=95, sink=0.62, vne=250, cockpit="Roomy", approx=True),
 "B4":     dict(name="Pilatus B4-PC11", cls="Club (metal, aerobatic)", seats=1, span=15.0, ld=35, v_ld=85, sink=0.64, vne=240, cockpit="Smallish", approx=False),
 "LS-4":   dict(name="Rolladen-Schneider LS-4", cls="Standard (GRP)", seats=1, span=15.0, ld=40.5, v_ld=100, sink=0.60, vne=270, cockpit="Roomy", approx=False),
 "LS-3":   dict(name="Rolladen-Schneider LS-3", cls="15 m (GRP)", seats=1, span=15.0, ld=40, v_ld=100, sink=0.60, vne=270, cockpit="OK", approx=True),
 "LS-6":   dict(name="Rolladen-Schneider LS-6", cls="15 m (GRP)", seats=1, span=15.0, ld=42.5, v_ld=105, sink=0.58, vne=270, cockpit="OK", approx=True),
 "DISCUS": dict(name="Schempp-Hirth Discus CS", cls="Standard (GRP)", seats=1, span=15.0, ld=42, v_ld=100, sink=0.59, vne=250, cockpit="Medium", approx=False),
 "DUO":    dict(name="Schempp-Hirth Duo Discus", cls="Two-seat 20 m (GRP)", seats=2, span=20.0, ld=45, v_ld=100, sink=0.55, vne=250, cockpit="Front seat reputedly roomy", approx=False),
 "DISCUS2":dict(name="Schempp-Hirth Discus-2cT", cls="18 m (GRP, turbo)", seats=1, span=18.0, ld=47, v_ld=105, sink=0.54, vne=280, cockpit="Medium", approx=True),
 "DG505":  dict(name="Glaser-Dirks DG-505 Orion", cls="Two-seat 18/20 m (GRP)", seats=2, span=20.0, ld=44, v_ld=105, sink=0.56, vne=270, cockpit="Good", approx=True),
 "HPH304": dict(name="HpH 304C Wasp", cls="15 m (GRP)", seats=1, span=15.0, ld=43, v_ld=105, sink=0.58, vne=270, cockpit="Unknown", approx=True),
 "IS28":   dict(name="IAR IS-28B2 Lark", cls="Two-seat (metal)", seats=2, span=17.0, ld=34, v_ld=90, sink=0.70, vne=210, cockpit="Unknown", approx=True),
 "PEGASUS":dict(name="Centrair Pegasus 101", cls="Standard (GRP)", seats=1, span=15.0, ld=41, v_ld=100, sink=0.60, vne=250, cockpit="Unknown", approx=True),
 "GENESIS":dict(name="Genesis 2", cls="Standard (composite)", seats=1, span=15.0, ld=42, v_ld=100, sink=0.58, vne=275, cockpit="Moderate", approx=True),
 "SWIFT":  dict(name="Swift S-1 / MDM aerobatic", cls="Aerobatic", seats=1, span=12.7, ld=29, v_ld=95, sink=0.75, vne=290, cockpit="Unknown", approx=True),
 "PUCHACZ":dict(name="SZD-50 Puchacz", cls="Two-seat trainer (GRP)", seats=2, span=16.67, ld=30, v_ld=85, sink=0.70, vne=215, cockpit="Roomy", approx=True),
 "CIRRUS": dict(name="Schempp-Hirth Open Cirrus", cls="Open (GRP, vintage)", seats=1, span=17.7, ld=44, v_ld=95, sink=0.55, vne=220, cockpit="Unknown", approx=True),
}

# Fleet model string -> type key (first regex match wins)
import re
MATCH = [
 (r"2-33","2-33"),(r"2-32","2-32"),(r"2-22","2-22"),(r"1-26","1-26"),(r"1-34","1-34"),(r"1-35","1-35"),(r"1-36","1-36"),(r"1-23","1-23"),
 (r"L-23|L-23 / L-33|Super Blanik|L-23 Blanik","L-23"),(r"L-13","L-13"),(r"L-33","L-33"),
 (r"ASK-21","ASK-21"),(r"ASK-13","ASK-13"),(r"ASW-19","ASW-19"),(r"PW-6","PW-6"),(r"PW-5","PW-5"),
 (r"Twin III|G103C","G103C"),(r"G103|Twin Astir|Twin II","G103"),(r"G102|Astir","G102"),(r"B4|B-4","B4"),
 (r"LS-4","LS-4"),(r"LS-3","LS-3"),(r"LS-6","LS-6"),(r"Duo Discus","DUO"),(r"Discus-2","DISCUS2"),(r"Discus","DISCUS"),
 (r"DG-505","DG505"),(r"304C","HPH304"),(r"IS-28","IS28"),(r"Pegasus","PEGASUS"),(r"Genesis","GENESIS"),(r"Swift","SWIFT"),
 (r"Puchacz|KR-03","PUCHACZ"),(r"Cirrus","CIRRUS"),
]
def type_key(model):
    for pat,k in MATCH:
        if re.search(pat, model): return k
    return None

def kt(kmh): return round(kmh/1.852)
def fpm(ms): return round(ms*196.85)
