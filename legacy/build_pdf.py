import sys; sys.path.insert(0, "/home/claude/soar")
from data import OPS, FLIGHTS, RENTAL_LABEL, ACCESS_LABEL
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=20, leading=24, alignment=0, textColor=colors.HexColor("#1F3A4D"))
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=13, textColor=colors.HexColor("#1F3A4D"), spaceBefore=12)
H3 = ParagraphStyle("h3", parent=ss["Heading3"], fontName="Helvetica-Bold", fontSize=10.5, spaceBefore=8)
B = ParagraphStyle("b", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13)
SM = ParagraphStyle("sm", parent=B, fontSize=8, leading=10)
SMB = ParagraphStyle("smb", parent=SM, fontName="Helvetica-Bold", textColor=colors.white)
BUL = ParagraphStyle("bul", parent=B, leftIndent=12, bulletIndent=2)

W = letter[0] - 1.3*inch

def table(data, widths, zebra=True):
    rows = [[Paragraph(str(c), SMB) for c in data[0]]] + [[Paragraph(str(c), SM) for c in r] for r in data[1:]]
    t = Table(rows, colWidths=[w*W for w in widths], repeatRows=1)
    st = [("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1F3A4D")),("VALIGN",(0,0),(-1,-1),"TOP"),
          ("LINEBELOW",(0,0),(-1,-1),0.25,colors.HexColor("#C9D3DA")),("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3)]
    if zebra:
        for i in range(1,len(rows)):
            if i%2==0: st.append(("BACKGROUND",(0,i),(-1,i),colors.HexColor("#F4F7F9")))
    t.setStyle(TableStyle(st)); return t

def bullets(items):
    return [Paragraph(x, BUL, bulletText="•") for x in items]

story = []
story += [Paragraph("Chasing Lift from Boston", H1),
          Paragraph("Weekend soaring destinations, operators, fleets and rental paths. Compiled 2026-09-22 for Martin (GBSC student pilot). Companion files: <b>Chase-Lift Soaring Register.xlsx</b> (full data, fleet register, contact log) and <b>Chase-Lift Map.html</b> (interactive weather + site map).", B),
          Spacer(1,8)]

story.append(Paragraph("Bottom line", H2))
story += bullets([
 "<b>Default to the van.</b> Seven active sites sit inside roughly 4 hours on a Friday evening: Sugarbush, Franconia, Post Mills, NESA Springfield, Mohawk North Adams, Adirondack Saratoga and Wurtsboro. Late September through November is Northeast ridge and wave season (northwest flow behind cold fronts).",
 "<b>Walk-in rental to a visiting licensed pilot is rare.</b> Most US soaring is club-based: you join, check out, and pull duty. Operators that publish non-member rental: Sugarbush (VT), Wurtsboro (NY), Van Sant (PA), Chilhowee (TN), Seminole-Lake (FL), Miami Gliders (FL), Arizona Soaring (AZ), and Mile High Gliding (CO, terms unpublished).",
 "<b>So yes, you need relationships first.</b> Every operator, commercial included, expects a checkout on the first visit. The plan is: one good-weather checkout trip per site, then short-notice trips by phone.",
 "<b>Best fly-away bets:</b> Orlando for Seminole-Lake (cheap routes, year-round), Atlanta for Chilhowee (ridge in fall-spring), Phoenix for Arizona Soaring (Oct-Apr, but fares rarely under $300 last-minute), Denver for Boulder.",
 "<b>Tall-pilot filter:</b> many fleets are ASK-21 heavy. Roomy types to look for: Schweizer 2-33 and 2-32, LET L-23 Super Blanik and L-13, Grob 103 (depends on proportions), Grob 102, DG-505, PW-6 front seat.",
])

story.append(Paragraph("1. Travel radius", H2))
story.append(Paragraph("Drive times are OSRM (Open Source Routing Machine) distances with typical times calibrated against published trips, plus 30-60 min for the Friday 4:30-7:00 pm Boston outbound peak. Treat as plus or minus 15 min.", B))
drive = [["Site","Airport","Miles","Typical","Fri 5:30 pm","Within 4 h?"],
 ["GBSC, Sterling MA","3B3","45","0:50","1:15-1:30","Yes"],
 ["Connecticut Soaring, Windham CT","IJD","84","1:30","2:00","Yes"],
 ["NESA, Springfield VT","VSF","123","2:15","2:45","Yes"],
 ["Mohawk, North Adams MA","AQW","~135","2:40","3:10","Yes"],
 ["Franconia NH","1B5","151","2:30","3:00-3:30","Yes"],
 ["Post Mills VT","2B9","155","2:40","3:10","Yes"],
 ["Mt Washington wave camp, Gorham NH","2G8","183","3:15","3:45-4:15","Edge"],
 ["Sugarbush, Warren VT","0B7","191","3:15","3:45-4:00","Edge"],
 ["Adirondack, Saratoga NY","5B2","193","3:15","3:45","Yes"],
 ["Valley Soaring, Middletown NY","06N","~210","3:30","~4:00","Edge"],
 ["Wurtsboro NY","N82","216","3:30","4:00-4:15","Edge"],
 ["Blairstown NJ (Jersey Ridge, ACA)","1N7","266","4:15","4:45-5:00","No"],
 ["Van Sant PA","9N1","276","4:30","5:00+","No (fly PHL)"],
 ["Harris Hill, Elmira NY","4NY8","360","5:30","6:00+","No (fly SYR)"],
]
story.append(table(drive, [.36,.09,.09,.1,.16,.2]))
story.append(Spacer(1,6))
story.append(Paragraph("Flight radius: nonstop from BOS (PVD and MHT add options but are 60-75 min from Newton at rush hour). Earliest realistic BOS departure is about 7:00-7:15 pm. Tier A = plausibly under $300 booked 2-3 days out; B = sometimes; C = rarely. Fares are KAYAK route-page ranges, Sept 2026; last-minute premiums run 10-100%. Spirit ceased operations 2 May 2026.", B))
fl = [["Tier","Dest.","Carriers","Friday timing","Fare (RT)","Soaring"]] + [list(f) for f in FLIGHTS]
story.append(table(fl, [.06,.1,.14,.22,.2,.28]))

story.append(PageBreak())
story.append(Paragraph("2. Operators by region", H2))
story.append(Paragraph("Rank = ease of short-notice rental for a visiting licensed pilot within that region (1 easiest). Full procedures, costs, sources and fleets are in the workbook.", B))
regions = ["New England","NY/NJ/PA","Mid-Atlantic","Southeast","Midwest","Florida","Texas","Mountain West","Southwest"]
for reg in regions:
    ops = sorted([o for o in OPS if o["region"]==reg], key=lambda o: o["rank"] or 99)
    data = [["#","Operator","Airport","Access","Soaring","Rental path","Phone"]]
    for o in ops:
        data.append([o["rank"] or "", f"{o['name']}<br/><font color='#555555'>{o['city']}</font>", o["airport"], o["travel"], o["lift"], RENTAL_LABEL[o["rental"]], o["phone"]])
    story.append(KeepTogether([Paragraph(reg, H3), table(data, [.04,.24,.14,.17,.14,.13,.14])]))

story.append(PageBreak())
story.append(Paragraph("3. How renting works for a visitor", H2))
story.append(Paragraph("Across the operators researched, the path to flying a glider solo at a site that is not your home club falls into four patterns:", B))
story += bullets([
 "<b>Commercial rental</b> (Sugarbush, Wurtsboro, Van Sant, Chilhowee, Seminole-Lake, Miami, Arizona Soaring, Mile High). Pay per hour plus tow. Expect a dual checkout flight with their CFIG (Certificated Flight Instructor, Glider) on the first visit, a logbook review, and increasingly your own renter insurance. Arizona Soaring requires hull cover of $15k (1-26, 2-33) up to $60k (G103) and $100k (ASK-21); Seminole-Lake requires $40k hull.",
 "<b>Guest or short-term membership</b> (Harris Hill board-approved guest, Skyline Visiting Member $10/day for SSA club members, Pittsburgh temporary membership, Sandhill short-term guest, Mohawk 30-day limited, Texas Soaring visiting-pilot membership, Blue Ridge monthly guest, SVS 3-month intro). Needs an email ahead with SSA number and logbook, then a checkout.",
 "<b>Long-distance membership</b> (Adirondack $650 + $15/mo for members 120+ mi away; Finger Lakes $550 + $15/mo; Brandywine non-resident $500 + $35/mo). Pay once, then book like a local. This is the cheapest way to make a second home field.",
 "<b>Full membership only</b> (most other clubs). Worth it only for one second club you will visit often.",
])
story.append(Paragraph("Standing prerequisites", H3))
story += bullets([
 "Current SSA (Soaring Society of America) membership.",
 "Non-owner glider renter policy (Costello, AVEMCO or AOPA) with hull limits sized to the most expensive glider you would rent; about $60k-100k covers every operator here.",
 "Current logbook, flight review, and a record of each site checkout (the workbook has a column for this).",
 "Oxygen and wave-window briefing for wave sites (Mt Washington, Petersburg WV, Boulder).",
 "Mountain and density-altitude checkout for western sites (Boulder at 5,288 ft, Heber at 5,637 ft, Moriarty at 6,204 ft).",
])

story.append(Paragraph("4. Relationship plan", H2))
story.append(Paragraph("Now, while pre-solo:", H3))
story += bullets([
 "Keep training at GBSC; sit-test the 1-34, L-23 and ASW-19 so you know your single-seat options at home.",
 "Use one weekend to take a dual lesson at Sugarbush (ridge and wave, 3:15 away). It gets you in the PW-6 and 2-33 and on their radar.",
 "Optionally a lesson at Wurtsboro to sit in their Grob 103 and ask for written rental and checkout rules.",
])
story.append(Paragraph("After the Private Pilot Glider certificate:", H3))
story += bullets([
 "Buy a renter policy and keep SSA current.",
 "Van tier: rental checkouts at Sugarbush and Wurtsboro; join Adirondack as a long-distance member (tows only after that); email Mohawk about a limited membership for Greylock ridge days.",
 "Fly tier: checkout weekends at Chilhowee (set up a $1,000 block account), Arizona Soaring (G103), and Seminole-Lake. Email Harris Hill, Skyline and Sandhill for guest status.",
 "Log every call and visit in the workbook's Contact Log so fleet and policy notes stay current.",
])

story.append(Paragraph("5. The weekly decision (Wednesday/Thursday)", H2))
story += bullets([
 "Open the map file. Pick Saturday or Sunday and the midday hour, and switch layers: boundary layer height (thermal depth), estimated cloud base, CAPE (Convective Available Potential Energy, thunderstorm risk), low cloud, rain chance, and 850 hPa wind (about 5,000 ft MSL, the ridge and wave driver).",
 "Ridge days: 850 hPa wind 15-30 kt roughly perpendicular to the ridge (northwest for the Green Mountains, Greylock and Shawangunks). Wave: strong northwest flow with a stable layer above the ridges, typically after a cold front.",
 "Thermal days: boundary layer over about 5,000 ft AGL, cloud base high, low CAPE, little low cloud and rain.",
 "Cross-check with the soaring-specific forecasts linked from each site popup (SkySight, XC Skies, Windy, NWS area forecast discussion), then call the operator Thursday.",
])

story.append(Paragraph("6. Gaps and caveats", H2))
story += bullets([
 "Many clubs publish nothing about visitors; 'Unknown, call' in the workbook means exactly that.",
 "Closed or not operating: Stowe Soaring (dissolved 2019), Ridge Soaring Gliderport, Julian PA (closed 2022), Turf Soaring AZ (closed), Southwest Soaring TX, Kutztown PA; Eastern Soaring Center WV is closed for 2026; Bermuda High is not scheduling new instruction; Skyline's home field FRR is closed for repaving until about mid-November 2026.",
 "Seminole-Lake Gliderport has been listed for sale since 2022 (relisted May 2025).",
 "Coordinates marked approximate in the workbook are within about a mile.",
 "Tall-pilot notes are general type reputation except where an operator stated a limit (CSA 6'1\", SVS under 6'5\", TSA ride limit 6'4\").",
])

def on_page(c, d):
    c.saveState(); c.setFont("Helvetica", 7.5); c.setFillColor(colors.grey)
    c.drawString(0.65*inch, 0.45*inch, "Chasing Lift from Boston  |  compiled 2026-09-22")
    c.drawRightString(letter[0]-0.65*inch, 0.45*inch, f"Page {d.page}"); c.restoreState()

doc = SimpleDocTemplate("/mnt/user-data/outputs/Chasing Lift from Boston.pdf", pagesize=letter,
                        leftMargin=.65*inch, rightMargin=.65*inch, topMargin=.6*inch, bottomMargin=.7*inch,
                        title="Chasing Lift from Boston", author="Claude for Martin Colwell")
doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
print("ok")
