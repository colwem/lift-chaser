"""Build site/index.html from data/*.json and site/template.html.

The page inlines the data so it also works when opened from disk (file://).
When hosted, forecast data should come from cache/ (see fetch_forecasts.py);
wiring that in is backlog item 2 in CLAUDE.md.
"""
import json, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
d = root / "data"
ops = json.loads((d / "operators.json").read_text())
fleet = json.loads((d / "fleet.json").read_text())
types = json.loads((d / "glider_types.json").read_text())
rasp_src = json.loads((d / "rasp_sources.json").read_text())
# the template expects fleet rows as arrays: [op, model, reg, seats, rate, who, note, type]
fleet_rows = [[f["op"], f["model"], f["reg"], f["seats"], f["rate"], f["who"], f["note"], f["type"]] for f in fleet]
rasp = {sid: src["base"] for src in rasp_src.values() for sid in src["sites"]}
t = (root / "site" / "template.html").read_text()
for k, v in {"__OPS__": ops, "__FLEET__": fleet_rows, "__TYPES__": types, "__RASP__": rasp}.items():
    t = t.replace(k, json.dumps(v))
(root / "site" / "index.html").write_text(t)
print("wrote site/index.html:", len(ops), "operators,", len(fleet_rows), "gliders")
