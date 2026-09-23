"""Build site/index.html from data/*.json and site/template.html.

The page inlines the data so it also works when opened from disk (file://).
When hosted, forecast data should come from cache/ (see fetch_forecasts.py);
wiring that in is backlog item 2 in CLAUDE.md.
"""
import datetime as dt, json, os, pathlib, subprocess
root = pathlib.Path(__file__).resolve().parent.parent
d = root / "data"
ops = json.loads((d / "operators.json").read_text())
fleet = json.loads((d / "fleet.json").read_text())
types = json.loads((d / "glider_types.json").read_text())
rasp_src = json.loads((d / "rasp_sources.json").read_text())
# the template expects fleet rows as arrays: [op, model, reg, seats, rate, who, note, type]
fleet_rows = [[f["op"], f["model"], f["reg"], f["seats"], f["rate"], f["who"], f["note"], f["type"]] for f in fleet]
rasp = {sid: src["base"] for src in rasp_src.values() for sid in src["sites"]}
# build stamp shown on the page, so it is obvious which version is live
try:
    sha = os.environ.get("GITHUB_SHA") or subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
except OSError:
    sha = ""
dirty = not os.environ.get("GITHUB_SHA") and subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True).stdout.strip()
build = {"sha": (sha or "local")[:7] + (" + local changes" if dirty else ""), "time": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
t = (root / "site" / "template.html").read_text()
for k, v in {"__OPS__": ops, "__FLEET__": fleet_rows, "__TYPES__": types, "__RASP__": rasp, "__BUILD__": build}.items():
    t = t.replace(k, json.dumps(v))
(root / "site" / "index.html").write_text(t)
print("wrote site/index.html:", len(ops), "operators,", len(fleet_rows), "gliders")
