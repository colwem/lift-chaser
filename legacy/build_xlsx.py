import sys; sys.path.insert(0, "/home/claude/soar")
from data import OPS, FLEET, FLIGHTS, RENTAL_LABEL, ACCESS_LABEL
from gliders import TYPES, type_key, kt, fpm
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

F = "Arial"
HDR_FILL = PatternFill("solid", fgColor="1F3A4D")
HDR_FONT = Font(name=F, bold=True, color="FFFFFF", size=10)
BODY = Font(name=F, size=10)
LINK = Font(name=F, size=10, color="1F5FA8", underline="single")
thin = Side(style="thin", color="C9D3DA")
BORDER = Border(bottom=thin)
WRAP = Alignment(wrap_text=True, vertical="top")
RENT_FILL = {"RENT":"D8EFD9","GUEST":"E5EEF8","JOIN":"F3EFE3","UNK":"FFF3CD","CLOSED":"EEEEEE"}

wb = Workbook()

def sheet(title, headers, widths, rows, link_cols=(), fill_col=None):
    ws = wb.create_sheet(title)
    ws.append(headers)
    for c in range(1, len(headers)+1):
        cell = ws.cell(row=1, column=c); cell.fill = HDR_FILL; cell.font = HDR_FONT; cell.alignment = WRAP
        ws.column_dimensions[get_column_letter(c)].width = widths[c-1]
    for r in rows:
        ws.append(r)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.font = BODY; cell.alignment = WRAP; cell.border = BORDER
            if cell.column in link_cols and isinstance(cell.value, str) and cell.value.startswith("http"):
                cell.hyperlink = cell.value; cell.font = LINK
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions
    return ws

# README
ws = wb.active; ws.title = "Read Me"
lines = [
 ("Chase-Lift Soaring Register", True),
 ("Compiled 2026-09-22 for Martin (GBSC). Rates, policies and fleets are as published by each operator on that date; anything marked 'unverified' or 'call' needs a phone call before a trip.", False),
 ("", False),
 ("Sheets", True),
 ("Operators: one row per site. Rank = ease of short-notice rental for a visiting licensed pilot (1 = easiest) within its region; 0 = not ranked.", False),
 ("Rental Procedures: what it takes to rent, costs, tall-pilot notes, sources.", False),
 ("Fleet Register: every glider found, with N-number where the FAA registry or fleet page gave one; performance columns pull from Glider Types.", False),
 ("Glider Types: glide ratio, speeds, span and cockpit notes per type.", False),
 ("Travel: flight tiers from Boston on a Friday evening.", False),
 ("Contact Log: fill this in as you build relationships (one row per call/email/visit).", False),
 ("", False),
 ("Rental categories", True),
] + [(f"{k}: {v}", False) for k,v in RENTAL_LABEL.items()] + [
 ("", False),
 ("Access", True),
] + [(f"{k}: {v}", False) for k,v in ACCESS_LABEL.items()] + [
 ("", False),
 ("Standing prerequisites for renting anywhere", True),
 ("Current SSA (Soaring Society of America) membership; nearly every club requires it.", False),
 ("Non-owner (renter) glider insurance with hull cover; Arizona Soaring needs $15k-100k by type, Seminole-Lake $40k, SoaringNV proof of policy.", False),
 ("Logbook showing currency; a checkout at each new site, done on a first visit in good weather, then short-notice trips by phone.", False),
 ("Tall-pilot rule: sit in the actual glider before planning a trip around it. Tall-pilot notes are general type reputation unless the operator stated a limit.", False),
]
ws.column_dimensions["A"].width = 110
for i,(t,b) in enumerate(lines, start=1):
    c = ws.cell(row=i, column=1, value=t); c.font = Font(name=F, size=14 if i==1 else 10, bold=b); c.alignment = Alignment(wrap_text=True)

ops_sorted = sorted(OPS, key=lambda o: (["New England","NY/NJ/PA","Mid-Atlantic","Southeast","Midwest","Florida","Texas","Mountain West","Southwest"].index(o["region"]), o["rank"] if o["rank"] else 99))

# Operators
headers = ["ID","Operator","Type","Region","Airport","Town","Access","Travel from Newton","Soaring","Season / days","Rental status","Rank","Gliders listed","Phone","Email","Contacts","Website","Lat","Lon","Last verified"]
widths  = [11,30,13,12,22,17,15,26,22,24,18,6,9,18,24,26,30,9,9,11]
rows = []
for i,o in enumerate(ops_sorted, start=2):
    rows.append([o["id"],o["name"],o["kind"],o["region"],o["airport"],o["city"],ACCESS_LABEL[o["access"]],o["travel"],o["lift"],o["season"],
                 RENTAL_LABEL[o["rental"]], o["rank"] or None, f"=COUNTIF('Fleet Register'!$A:$A,A{i})",
                 o["phone"],o["email"],o["contacts"],o["web"],o["lat"],o["lon"],"2026-09-22"])
ws = sheet("Operators", headers, widths, rows, link_cols=(17,))
for r in range(2, ws.max_row+1):
    key = ops_sorted[r-2]["rental"]
    ws.cell(row=r, column=11).fill = PatternFill("solid", fgColor=RENT_FILL[key])
    if ops_sorted[r-2]["approx"]:
        ws.cell(row=r, column=18).comment = None
dv = DataValidation(type="list", formula1='"' + ",".join(RENTAL_LABEL.values()) + '"', allow_blank=True)
ws.add_data_validation(dv); dv.add(f"K2:K{ws.max_row}")

# Procedures
headers = ["ID","Operator","Rental status","Procedure for a visiting licensed pilot","Costs","Tall-pilot notes","Sources"]
widths = [11,28,16,60,48,30,40]
rows = [[o["id"],o["name"],RENTAL_LABEL[o["rental"]],o["procedure"],o["costs"],o["tall"],o["sources"]] for o in ops_sorted]
ws = sheet("Rental Procedures", headers, widths, rows)
for r in range(2, ws.max_row+1):
    ws.cell(row=r, column=3).fill = PatternFill("solid", fgColor=RENT_FILL[ops_sorted[r-2]["rental"]])

# Glider types
headers = ["Type key","Type","Class","Seats","Span (m)","Max L/D","Best-glide speed (kt)","Min sink (fpm)","Vne (kt)","Cockpit / tall pilot","Figures approximate?"]
widths = [10,30,20,6,8,8,10,9,8,26,11]
trows = [[k,t["name"],t["cls"],t["seats"],t["span"],t["ld"],kt(t["v_ld"]),fpm(t["sink"]),kt(t["vne"]),t["cockpit"],"Yes, verify" if t["approx"] else "No"] for k,t in TYPES.items()]
wt = sheet("Glider Types", headers, widths, trows)
n = wt.max_row + 2
wt.cell(row=n, column=1, value="Nominal type figures (manufacturer data / type references). L/D = maximum glide ratio; Vne = never-exceed speed; min sink = lowest still-air sink rate. Always use the actual aircraft's flight manual.").font = Font(name=F, size=10, italic=True)

# Fleet
name = {o["id"]:o["name"] for o in OPS}
headers = ["Operator ID","Operator","Glider","Type key","Registration (N-number)","Seats","Rate","Who can fly it","Tall-pilot note","Max L/D","Best-glide kt","Min sink fpm","Vne kt","Sat in it? (Y/N)","My checkout date","Notes"]
widths = [11,26,26,9,20,6,22,16,20,7,8,8,7,9,11,20]
rows=[]
for i,f in enumerate(FLEET, start=2):
    look = lambda col: f"=IFERROR(INDEX('Glider Types'!${col}:${col},MATCH(D{i},'Glider Types'!$A:$A,0)),\"\")"
    rows.append([f[0], name[f[0]], f[1], type_key(f[1]), f[2] or "not found", f[3], f[4], f[5], f[6], look("F"), look("G"), look("H"), look("I"), None, None, None])
ws = sheet("Fleet Register", headers, widths, rows)
yellow = PatternFill("solid", fgColor="FFF7CC")
for r in range(2, ws.max_row+1):
    for c in (14,15,16): ws.cell(row=r, column=c).fill = yellow

# Travel
headers = ["Tier","Destination","Carriers (nonstop from BOS)","Friday evening timing","Round-trip fare (KAYAK typical)","Nearest soaring"]
widths = [6,14,22,28,28,40]
ws = sheet("Travel", headers, widths, [list(f) for f in FLIGHTS])
n = ws.max_row + 2
notes = ["Tier A: plausibly under $300 booked 2-3 days out. Tier B: sometimes, watch for sales. Tier C: rarely.",
         "Fares from KAYAK route pages, Sept 2026; booking within 2 weeks runs 10-100% above average. Spirit ceased operations 2 May 2026.",
         "Earliest realistic BOS departure leaving Newton at 5:30 pm Friday: about 7:00-7:15 pm."]
for i,t in enumerate(notes):
    c = ws.cell(row=n+i, column=1, value=t); c.font = Font(name=F, size=10, italic=True)

# Contact log
headers = ["Date","Operator ID","Operator","Person","Method","What I asked","Outcome","Next step","Status"]
widths = [11,11,28,18,10,34,34,28,16]
ws = sheet("Contact Log", headers, widths, [["2026-09-22 (example)","SUGAR","=IFERROR(INDEX(Operators!$B:$B,MATCH(B2,Operators!$A:$A,0)),\"\")","Front desk","Phone","Rental checkout rules for licensed visitor; which ship fits a tall pilot","(example row)","Book checkout day","Not started"]])
for r in range(3, 60):
    ws.cell(row=r, column=3, value=f'=IFERROR(INDEX(Operators!$B:$B,MATCH(B{r},Operators!$A:$A,0)),"")').font = BODY
dv2 = DataValidation(type="list", formula1='"Not started,Contacted,Checkout booked,Checked out,Member"', allow_blank=True)
ws.add_data_validation(dv2); dv2.add("I2:I200")
dv3 = DataValidation(type="list", formula1='"Phone,Email,Visit,Web form"', allow_blank=True)
ws.add_data_validation(dv3); dv3.add("E2:E200")
ws.freeze_panes = "A2"

for w in wb.worksheets:
    w.sheet_view.zoomScale = 100
out = "/mnt/user-data/outputs/Chase-Lift Soaring Register.xlsx"
import os; os.makedirs("/mnt/user-data/outputs", exist_ok=True)
wb.save(out); print(out)
