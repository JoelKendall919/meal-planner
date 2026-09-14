import argparse
import datetime as dt
import pathlib

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference, Series
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

# The generated workbook holds personal measurements, so it is written to
# private/ which is excluded from version control.
ROOT = pathlib.Path(__file__).resolve().parents[1]
_ap = argparse.ArgumentParser(description="Generate the weight and training log workbook.")
_ap.add_argument(
    "--out", type=pathlib.Path, default=ROOT / "private" / "weight-and-training-log.xlsx"
)
OUT = str(_ap.parse_args().out)
pathlib.Path(OUT).parent.mkdir(parents=True, exist_ok=True)

START = dt.date(2026, 9, 14)  # Monday, week 1
WEEKS = 20
DAYS = WEEKS * 7
START_KG, TARGET_KG = 110.0, 95.0

# ---------- styling helpers ----------
NAVY = "1F3864"
BLUE = "2E75B6"
LIGHT = "D9E2F3"
GREY = "F2F2F2"
ACCENT = "C55A11"

hdr_font = Font(bold=True, color="FFFFFF", size=11)
hdr_fill = PatternFill("solid", fgColor=NAVY)
sub_fill = PatternFill("solid", fgColor=LIGHT)
title_font = Font(bold=True, size=16, color=NAVY)
note_font = Font(italic=True, size=10, color="595959")
thin = Side(style="thin", color="BFBFBF")
border = Border(left=thin, right=thin, top=thin, bottom=thin)


def style_header(ws, row, ncols, height=22):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
    ws.row_dimensions[row].height = height


def widths(ws, spec):
    for col, w in spec.items():
        ws.column_dimensions[col].width = w


wb = Workbook()

# =====================================================================
# 1. READ ME
# =====================================================================
ws = wb.active
ws.title = "Read Me"
widths(ws, {"A": 3, "B": 30, "C": 86})
ws["B2"] = "Weight & Training Log"
ws["B2"].font = title_font
ws["B3"] = (
    f"110 kg  →  95 kg   |   1750 kcal/day   |   {START:%d %b %Y} – {START + dt.timedelta(days=DAYS - 1):%d %b %Y}"
)
ws["B3"].font = Font(size=11, color="595959")

rows = [
    ("", ""),
    ("HOW TO USE", ""),
    (
        "Weight Log",
        "Weigh yourself every morning: after the toilet, before food or drink, no clothes. "
        "Type the number in column C. Everything else calculates itself.",
    ),
    (
        "Training Log",
        "Every session is pre-filled for 20 weeks. Mark column E as Y or N, then log actual minutes, "
        "distance, RPE and heart rate if you have it.",
    ),
    (
        "Strength Log",
        "One row per Monday. Record the heaviest working weight per dumbbell for each lift. "
        "This is your muscle-retention guardrail — see the warning below.",
    ),
    (
        "Weekly Summary",
        "Fully automatic. One row per week: average weight, change, sessions hit, total minutes.",
    ),
    ("Dashboard", "All the charts. Open this once a week on a Sunday and nothing else."),
    ("", ""),
    ("READING THE NUMBERS", ""),
    (
        "Ignore daily weight",
        "Day-to-day swings are water, food volume and salt — up to 2 kg of noise. "
        "The 7-day rolling average is the real signal. Judge progress on that line only.",
    ),
    (
        "#N/A is normal",
        "The rolling average needs 7 days of data before it can show anything, so the first week "
        "displays #N/A. That is expected, not a broken formula.",
    ),
    (
        "Expected rate",
        "0.7–0.9 kg per week. The grey target line on the weight chart shows the pace that lands "
        "you at 95 kg in 20 weeks. Tracking slightly above or below it is fine.",
    ),
    (
        "If you stall 2+ weeks",
        "Check portion accuracy first — weigh oils, rice and nuts. Then add 15 minutes of daily walking. "
        "Do not drop below 1750 kcal; it will wreck your training quality.",
    ),
    ("", ""),
    ("THE MUSCLE GUARDRAIL", ""),
    (
        "Why it matters",
        "You are lifting once a week in a deficit. That is enough to hold most of your muscle, but not all of it, "
        "and you will not notice the loss on the scale — the scale only says 'lighter'.",
    ),
    (
        "What to watch",
        "Goblet Squat, Floor Press and Single-Arm Row on the Strength Log. Those three tell the whole story.",
    ),
    (
        "The trigger",
        "If all three weights slide for three weeks running while you are eating and sleeping normally, "
        "that is muscle leaving, not fat. Add a second short lifting day on Thursday "
        "(squat, press, row, RDL — 3 sets each) and the slide will stop.",
    ),
    ("", ""),
    ("NON-NEGOTIABLES", ""),
    (
        "Protein",
        "175 g every day. This is your main defence against muscle loss. Spread it over 4 feedings of ~40 g.",
    ),
    ("Sleep", "7–9 hours. The single biggest lever on both hunger and recovery."),
    (
        "Effort",
        "Monday's working sets go to within 1–2 reps of failure. One session a week has to count.",
    ),
    ("Steps", "8,000–10,000 a day on top of training."),
]

r = 5
for label, text in rows:
    if label and not text:
        ws.cell(row=r, column=2, value=label).font = Font(bold=True, size=12, color=BLUE)
        r += 1
        continue
    if not label and not text:
        r += 1
        continue
    c1 = ws.cell(row=r, column=2, value=label)
    c1.font = Font(bold=True, size=10)
    c1.alignment = Alignment(vertical="top", wrap_text=True)
    c2 = ws.cell(row=r, column=3, value=text)
    c2.alignment = Alignment(vertical="top", wrap_text=True)
    ws.row_dimensions[r].height = max(15, 13 * (len(text) // 90 + 1))
    r += 1

ws.sheet_view.showGridLines = False

# =====================================================================
# 2. WEIGHT LOG
# =====================================================================
wl = wb.create_sheet("Weight Log")
headers = [
    "Date",
    "Day",
    "Weight (kg)",
    "7-Day Avg",
    "Weekly Change",
    "Total Lost",
    "Target Pace",
    "vs Target",
    "Notes (sleep, salt, alcohol…)",
]
wl.append(headers)
style_header(wl, 1, len(headers))
widths(wl, {"A": 12, "B": 6, "C": 12, "D": 11, "E": 14, "F": 11, "G": 12, "H": 10, "I": 38})
wl.freeze_panes = "C2"

for i in range(DAYS):
    d = START + dt.timedelta(days=i)
    r = i + 2
    target = START_KG - (START_KG - TARGET_KG) * i / (DAYS - 1)

    wl.cell(row=r, column=1, value=d).number_format = "ddd dd mmm"
    wl.cell(row=r, column=2, value=(i // 7) + 1)
    wl.cell(row=r, column=3).number_format = "0.0"

    # 7-day trailing average
    if i >= 6:
        f = f"=IF(COUNT(C{r - 6}:C{r})<7,NA(),AVERAGE(C{r - 6}:C{r}))"
    else:
        f = "=NA()"
    wl.cell(row=r, column=4, value=f).number_format = "0.00"

    # week-on-week change in the rolling average
    if i >= 13:
        f = f"=IF(OR(ISNA(D{r}),ISNA(D{r - 7})),NA(),D{r}-D{r - 7})"
    else:
        f = "=NA()"
    wl.cell(row=r, column=5, value=f).number_format = "+0.00;-0.00;0.00"

    wl.cell(row=r, column=6, value=f"=IF(ISNA(D{r}),NA(),{START_KG}-D{r})").number_format = "0.00"
    wl.cell(row=r, column=7, value=round(target, 2)).number_format = "0.00"
    wl.cell(
        row=r, column=8, value=f"=IF(ISNA(D{r}),NA(),D{r}-G{r})"
    ).number_format = "+0.00;-0.00;0.00"

    fill = GREY if d.weekday() >= 5 else None
    for c in range(1, len(headers) + 1):
        cell = wl.cell(row=r, column=c)
        cell.border = border
        if c in (2, 3, 4, 5, 6, 7, 8):
            cell.alignment = Alignment(horizontal="center")
        if fill:
            cell.fill = PatternFill("solid", fgColor=fill)

last = DAYS + 1
# losing weight = good (green), gaining = red
wl.conditional_formatting.add(
    f"E2:E{last}",
    CellIsRule(operator="lessThan", formula=["0"], font=Font(color="006100", bold=True)),
)
wl.conditional_formatting.add(
    f"E2:E{last}",
    CellIsRule(operator="greaterThan", formula=["0"], font=Font(color="9C0006", bold=True)),
)
wl.conditional_formatting.add(
    f"H2:H{last}", CellIsRule(operator="lessThanOrEqual", formula=["0"], font=Font(color="006100"))
)
wl.conditional_formatting.add(
    f"H2:H{last}", CellIsRule(operator="greaterThan", formula=["0"], font=Font(color="9C0006"))
)

# =====================================================================
# 3. TRAINING LOG
# =====================================================================
tl = wb.create_sheet("Training Log")
headers = [
    "Date",
    "Wk",
    "Day",
    "Planned Session",
    "Done?",
    "Actual Min",
    "Distance (km)",
    "RPE 1-10",
    "Avg HR",
    "Notes",
]
tl.append(headers)
style_header(tl, 1, len(headers))
widths(tl, {"A": 12, "B": 5, "C": 6, "D": 42, "E": 8, "F": 11, "G": 13, "H": 10, "I": 9, "J": 34})
tl.freeze_panes = "E2"

PLAN = {
    0: (
        "Full Body Dumbbells — 9 exercises, 1-2 reps from failure",
        "Full Body Dumbbells — 9 exercises, 1-2 reps from failure",
    ),
    1: ("Easy Run (Zone 2) — 35 min conversational", "Easy Run (Zone 2) — 35 min conversational"),
    2: (
        "Cycling Intervals — 6 x 2 min hard / 2 min easy",
        "Cycling Intervals — 6 x 2 min hard / 2 min easy",
    ),
    3: ("Recovery — 25 min walk + 10 min mobility", "Recovery — 25 min walk + 10 min mobility"),
    4: (
        "Tempo Run — 10 easy / 15 comfortably hard / 10 easy",
        "Run Intervals — 8 x 1 min hard / 90 s easy",
    ),
    5: ("Long Ride — 75-90 min moderate", "Long Run — 60 min steady"),
    6: ("Rest — full rest or gentle 30 min walk", "Rest — full rest or gentle 30 min walk"),
}
SESSION_FILL = {
    0: "FCE4D6",
    1: "E2EFDA",
    2: "DDEBF7",
    3: "F2F2F2",
    4: "E2EFDA",
    5: "DDEBF7",
    6: "F2F2F2",
}

for i in range(DAYS):
    d = START + dt.timedelta(days=i)
    r = i + 2
    week = (i // 7) + 1
    variant = 0 if week % 2 == 1 else 1  # Week A / Week B alternation
    wd = d.weekday()

    tl.cell(row=r, column=1, value=d).number_format = "ddd dd mmm"
    tl.cell(row=r, column=2, value=week)
    tl.cell(row=r, column=3, value=d.strftime("%a"))
    tl.cell(row=r, column=4, value=PLAN[wd][variant])

    for c in range(1, len(headers) + 1):
        cell = tl.cell(row=r, column=c)
        cell.border = border
        cell.fill = PatternFill("solid", fgColor=SESSION_FILL[wd])
        if c in (2, 3, 5, 6, 7, 8, 9):
            cell.alignment = Alignment(horizontal="center")

dv = DataValidation(type="list", formula1='"Y,N"', allow_blank=True)
dv.error = "Enter Y or N"
tl.add_data_validation(dv)
dv.add(f"E2:E{DAYS + 1}")

dv_rpe = DataValidation(type="whole", operator="between", formula1=1, formula2=10, allow_blank=True)
dv_rpe.error = "RPE must be 1-10"
tl.add_data_validation(dv_rpe)
dv_rpe.add(f"H2:H{DAYS + 1}")

tl.conditional_formatting.add(
    f"E2:E{DAYS + 1}",
    CellIsRule(
        operator="equal",
        formula=['"Y"'],
        fill=PatternFill("solid", fgColor="C6EFCE"),
        font=Font(color="006100", bold=True),
    ),
)
tl.conditional_formatting.add(
    f"E2:E{DAYS + 1}",
    CellIsRule(
        operator="equal",
        formula=['"N"'],
        fill=PatternFill("solid", fgColor="FFC7CE"),
        font=Font(color="9C0006", bold=True),
    ),
)

# =====================================================================
# 4. STRENGTH LOG
# =====================================================================
sl = wb.create_sheet("Strength Log")
LIFTS = [
    "Goblet Squat",
    "DB Romanian Deadlift",
    "DB Floor Press",
    "Single-Arm Row",
    "Shoulder Press",
    "Reverse Lunge",
    "Lateral Raise",
    "Hammer Curl",
]

sl["A1"] = "Strength Log — Monday sessions"
sl["A1"].font = title_font
sl["A2"] = (
    "Record the heaviest working weight PER DUMBBELL in kg. Add 2–2.5 kg only once you hit the top "
    "of the rep range with clean form. The three KEY lifts are your muscle-retention guardrail."
)
sl["A2"].font = note_font
sl.merge_cells("A2:M2")

hrow = 4
headers = ["Date", "Wk"] + LIFTS + ["Session RPE", "Notes"]
for c, h in enumerate(headers, start=1):
    sl.cell(row=hrow, column=c, value=h)
style_header(sl, hrow, len(headers), height=34)

# mark the three guardrail lifts
for c in (3, 5, 6):
    sl.cell(row=hrow, column=c).fill = PatternFill("solid", fgColor=ACCENT)

widths(sl, {"A": 12, "B": 5, "K": 12, "L": 12})
for c in range(3, 11):
    sl.column_dimensions[get_column_letter(c)].width = 13
sl.column_dimensions["L"].width = 34
sl.freeze_panes = "C5"

for w in range(WEEKS):
    d = START + dt.timedelta(days=w * 7)
    r = hrow + 1 + w
    sl.cell(row=r, column=1, value=d).number_format = "ddd dd mmm"
    sl.cell(row=r, column=2, value=w + 1)
    for c in range(1, len(headers) + 1):
        cell = sl.cell(row=r, column=c)
        cell.border = border
        if c <= 11:
            cell.alignment = Alignment(horizontal="center")
        if 3 <= c <= 10:
            cell.number_format = "0.0"
    if w % 2 == 1:
        for c in range(1, len(headers) + 1):
            sl.cell(row=r, column=c).fill = PatternFill("solid", fgColor=GREY)

warn_r = hrow + WEEKS + 3
sl.cell(row=warn_r, column=1, value="⚠  GUARDRAIL")
sl.cell(row=warn_r, column=1).font = Font(bold=True, size=12, color="9C0006")
sl.cell(
    row=warn_r + 1,
    column=1,
    value=(
        "If Goblet Squat, Floor Press AND Single-Arm Row all decline for three weeks running while you are "
        "eating and sleeping normally, you are losing muscle rather than fat. Add a second lifting day on "
        "Thursday — Goblet Squat, Floor Press, Single-Arm Row, RDL, 3 sets of 10 each — and the slide will stop."
    ),
)
sl.cell(row=warn_r + 1, column=1).font = Font(size=10)
sl.merge_cells(start_row=warn_r + 1, start_column=1, end_row=warn_r + 2, end_column=12)
sl.cell(row=warn_r + 1, column=1).alignment = Alignment(vertical="top", wrap_text=True)

# =====================================================================
# 5. WEEKLY SUMMARY
# =====================================================================
sm = wb.create_sheet("Weekly Summary")
headers = [
    "Wk",
    "Week Start",
    "Avg Weight",
    "Change",
    "Total Lost",
    "Target",
    "Sessions Done",
    "Total Min",
    "Avg RPE",
    "Notes",
]
sm.append(headers)
style_header(sm, 1, len(headers), height=30)
widths(
    sm, {"A": 5, "B": 13, "C": 12, "D": 10, "E": 11, "F": 10, "G": 13, "H": 11, "I": 10, "J": 40}
)
sm.freeze_panes = "C2"

for w in range(WEEKS):
    r = w + 2
    d = START + dt.timedelta(days=w * 7)
    d_end = d + dt.timedelta(days=6)
    target = START_KG - (START_KG - TARGET_KG) * ((w + 1) * 7 - 1) / (DAYS - 1)

    sm.cell(row=r, column=1, value=w + 1)
    sm.cell(row=r, column=2, value=d).number_format = "dd mmm yyyy"
    sm.cell(
        row=r,
        column=3,
        value=(
            f"=IF(COUNTIFS('Weight Log'!$B$2:$B${DAYS + 1},{w + 1},'Weight Log'!$C$2:$C${DAYS + 1},\">0\")=0,NA(),"
            f"AVERAGEIFS('Weight Log'!$C$2:$C${DAYS + 1},'Weight Log'!$B$2:$B${DAYS + 1},{w + 1},"
            f"'Weight Log'!$C$2:$C${DAYS + 1},\">0\"))"
        ),
    ).number_format = "0.00"
    if w == 0:
        sm.cell(row=r, column=4, value=f"=IF(ISNA(C{r}),NA(),C{r}-{START_KG})")
    else:
        sm.cell(row=r, column=4, value=f"=IF(OR(ISNA(C{r}),ISNA(C{r - 1})),NA(),C{r}-C{r - 1})")
    sm.cell(row=r, column=4).number_format = "+0.00;-0.00;0.00"
    sm.cell(row=r, column=5, value=f"=IF(ISNA(C{r}),NA(),{START_KG}-C{r})").number_format = "0.00"
    sm.cell(row=r, column=6, value=round(target, 2)).number_format = "0.00"
    sm.cell(
        row=r,
        column=7,
        value=(
            f"=COUNTIFS('Training Log'!$B$2:$B${DAYS + 1},{w + 1},'Training Log'!$E$2:$E${DAYS + 1},\"Y\")"
        ),
    )
    sm.cell(
        row=r,
        column=8,
        value=(
            f"=SUMIFS('Training Log'!$F$2:$F${DAYS + 1},'Training Log'!$B$2:$B${DAYS + 1},{w + 1})"
        ),
    )
    sm.cell(
        row=r,
        column=9,
        value=(
            f"=IFERROR(AVERAGEIFS('Training Log'!$H$2:$H${DAYS + 1},'Training Log'!$B$2:$B${DAYS + 1},{w + 1},"
            f'\'Training Log\'!$H$2:$H${DAYS + 1},">0"),"")'
        ),
    ).number_format = "0.0"

    for c in range(1, len(headers) + 1):
        cell = sm.cell(row=r, column=c)
        cell.border = border
        if c != 10:
            cell.alignment = Alignment(horizontal="center")
    if w % 2 == 1:
        for c in range(1, len(headers) + 1):
            sm.cell(row=r, column=c).fill = PatternFill("solid", fgColor=GREY)

sm.conditional_formatting.add(
    f"D2:D{WEEKS + 1}",
    CellIsRule(operator="lessThan", formula=["0"], font=Font(color="006100", bold=True)),
)
sm.conditional_formatting.add(
    f"D2:D{WEEKS + 1}",
    CellIsRule(operator="greaterThan", formula=["0"], font=Font(color="9C0006", bold=True)),
)
sm.conditional_formatting.add(
    f"G2:G{WEEKS + 1}",
    ColorScaleRule(
        start_type="num",
        start_value=0,
        start_color="FFC7CE",
        mid_type="num",
        mid_value=3,
        mid_color="FFEB9C",
        end_type="num",
        end_value=5,
        end_color="C6EFCE",
    ),
)

# =====================================================================
# 6. DASHBOARD
# =====================================================================
db = wb.create_sheet("Dashboard")
db.sheet_view.showGridLines = False
db["A1"] = "Dashboard"
db["A1"].font = title_font
db["A2"] = "Check this once a week. Judge progress on the rolling average, never a single morning."
db["A2"].font = note_font

# --- headline stat cells ---
stats = [
    (
        "A4",
        "Latest 7-Day Avg",
        f"=IFERROR(LOOKUP(2,1/(ISNUMBER('Weight Log'!D2:D{DAYS + 1})),'Weight Log'!D2:D{DAYS + 1}),\"—\")",
        '0.00" kg"',
    ),
    (
        "C4",
        "Total Lost",
        f"=IFERROR({START_KG}-LOOKUP(2,1/(ISNUMBER('Weight Log'!D2:D{DAYS + 1})),'Weight Log'!D2:D{DAYS + 1}),\"—\")",
        '0.00" kg"',
    ),
    (
        "E4",
        "Left to Go",
        f"=IFERROR(LOOKUP(2,1/(ISNUMBER('Weight Log'!D2:D{DAYS + 1})),'Weight Log'!D2:D{DAYS + 1})-{TARGET_KG},\"—\")",
        '0.00" kg"',
    ),
    ("G4", "Sessions Logged", f"=COUNTIF('Training Log'!E2:E{DAYS + 1},\"Y\")", "0"),
    ("I4", "Total Minutes", f"=SUM('Training Log'!F2:F{DAYS + 1})", "0"),
]
for anchor, label, formula, fmt in stats:
    col = anchor[0]
    row = int(anchor[1:])
    lc = db[f"{col}{row}"]
    lc.value = label
    lc.font = Font(bold=True, size=9, color="FFFFFF")
    lc.fill = PatternFill("solid", fgColor=BLUE)
    lc.alignment = Alignment(horizontal="center")
    vc = db[f"{col}{row + 1}"]
    vc.value = formula
    vc.number_format = fmt
    vc.font = Font(bold=True, size=16, color=NAVY)
    vc.alignment = Alignment(horizontal="center")
    vc.fill = PatternFill("solid", fgColor=LIGHT)
    nxt = get_column_letter(db[f"{col}1"].column + 1)
    db.merge_cells(f"{col}{row}:{nxt}{row}")
    db.merge_cells(f"{col}{row + 1}:{nxt}{row + 1}")
    db.column_dimensions[col].width = 13
    db.column_dimensions[nxt].width = 13
db.row_dimensions[5].height = 28

# --- Chart 1: daily weight vs rolling average vs target ---
c1 = LineChart()
c1.title = "Weight — Daily vs 7-Day Rolling Average vs Target Pace"
c1.style = 2
c1.height, c1.width = 10, 32
c1.y_axis.title = "kg"
c1.x_axis.title = "Date"
c1.dispBlanksAs = "gap"

dates = Reference(wl, min_col=1, min_row=2, max_row=DAYS + 1)
for col, name, colour, w_, dash in [
    (3, "Daily weight", "BDD7EE", 12500, "sysDot"),
    (4, "7-day average", "1F3864", 28000, None),
    (7, "Target pace", "C55A11", 19000, "dash"),
]:
    ref = Reference(wl, min_col=col, min_row=1, max_row=DAYS + 1)
    s = Series(ref, title_from_data=True)
    s.graphicalProperties.line.solidFill = colour
    s.graphicalProperties.line.width = w_
    if dash:
        s.graphicalProperties.line.dashStyle = dash
    s.smooth = False
    s.marker.symbol = "none"
    c1.series.append(s)
c1.set_categories(dates)
c1.y_axis.scaling.min = TARGET_KG - 3
c1.y_axis.scaling.max = START_KG + 3
c1.x_axis.tickLblSkip = 14
c1.x_axis.tickMarkSkip = 14
db.add_chart(c1, "A8")

# --- Chart 2: weekly average weight ---
c2 = LineChart()
c2.title = "Weekly Average Weight vs Target"
c2.style = 2
c2.height, c2.width = 9, 15.5
c2.y_axis.title = "kg"
c2.x_axis.title = "Week"
c2.dispBlanksAs = "gap"
for col, colour, w_, dash in [(3, "1F3864", 28000, None), (6, "C55A11", 19000, "dash")]:
    ref = Reference(sm, min_col=col, min_row=1, max_row=WEEKS + 1)
    s = Series(ref, title_from_data=True)
    s.graphicalProperties.line.solidFill = colour
    s.graphicalProperties.line.width = w_
    if dash:
        s.graphicalProperties.line.dashStyle = dash
    s.marker.symbol = "circle" if col == 3 else "none"
    s.marker.size = 6
    s.smooth = False
    c2.series.append(s)
c2.set_categories(Reference(sm, min_col=1, min_row=2, max_row=WEEKS + 1))
c2.y_axis.scaling.min = TARGET_KG - 3
c2.y_axis.scaling.max = START_KG + 3
db.add_chart(c2, "A29")

# --- Chart 3: weekly change ---
c3 = BarChart()
c3.type = "col"
c3.title = "Weekly Change (kg) — target −0.7 to −0.9"
c3.style = 2
c3.height, c3.width = 9, 15.5
c3.y_axis.title = "kg change"
c3.x_axis.title = "Week"
c3.append(Series(Reference(sm, min_col=4, min_row=1, max_row=WEEKS + 1), title_from_data=True))
c3.set_categories(Reference(sm, min_col=1, min_row=2, max_row=WEEKS + 1))
c3.series[0].graphicalProperties.solidFill = BLUE
db.add_chart(c3, "J29")

# --- Chart 4: sessions completed ---
c4 = BarChart()
c4.type = "col"
c4.title = "Sessions Completed per Week (target 5)"
c4.style = 2
c4.height, c4.width = 9, 15.5
c4.y_axis.title = "sessions"
c4.x_axis.title = "Week"
c4.y_axis.scaling.max = 7
c4.append(Series(Reference(sm, min_col=7, min_row=1, max_row=WEEKS + 1), title_from_data=True))
c4.set_categories(Reference(sm, min_col=1, min_row=2, max_row=WEEKS + 1))
c4.series[0].graphicalProperties.solidFill = "70AD47"
db.add_chart(c4, "A48")

# --- Chart 5: training minutes ---
c5 = BarChart()
c5.type = "col"
c5.title = "Training Minutes per Week"
c5.style = 2
c5.height, c5.width = 9, 15.5
c5.y_axis.title = "minutes"
c5.x_axis.title = "Week"
c5.append(Series(Reference(sm, min_col=8, min_row=1, max_row=WEEKS + 1), title_from_data=True))
c5.set_categories(Reference(sm, min_col=1, min_row=2, max_row=WEEKS + 1))
c5.series[0].graphicalProperties.solidFill = "7030A0"
db.add_chart(c5, "J48")

# --- Chart 6: strength guardrail ---
c6 = LineChart()
c6.title = "Strength Guardrail — key lifts must not decline"
c6.style = 2
c6.height, c6.width = 10, 32
c6.y_axis.title = "kg per dumbbell"
c6.x_axis.title = "Week"
c6.dispBlanksAs = "gap"
for col, colour in [(3, "C55A11"), (5, "1F3864"), (6, "70AD47"), (4, "BDD7EE"), (7, "A6A6A6")]:
    ref = Reference(sl, min_col=col, min_row=hrow, max_row=hrow + WEEKS)
    s = Series(ref, title_from_data=True)
    s.graphicalProperties.line.solidFill = colour
    s.graphicalProperties.line.width = 26000 if col in (3, 5, 6) else 14000
    s.marker.symbol = "circle"
    s.marker.size = 6
    s.smooth = False
    c6.series.append(s)
c6.set_categories(Reference(sl, min_col=2, min_row=hrow + 1, max_row=hrow + WEEKS))
db.add_chart(c6, "A67")

wb.save(OUT)
print("saved", OUT)
