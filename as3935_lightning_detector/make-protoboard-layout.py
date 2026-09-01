#!/usr/bin/env python3
"""
Generate as3935-protoboard-layout.pdf -- component placement and point-to-point
wiring plans for the rev 2 build (README section 16) on 0.1" perforated
protoboard with isolated pads.

Companion to make-wiring-diagram.py, which draws the schematic-level
interconnect. This one answers "where does each part physically go".

Regenerate with:   python3 make-protoboard-layout.py
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

PDF = "as3935-protoboard-layout.pdf"
W, H = letter
M = 0.6 * inch

RED    = HexColor("#b3261e")   # 5 V
ORANGE = HexColor("#b06000")   # 3.3 V
BLACK  = HexColor("#111111")   # ground
BLUE   = HexColor("#1b4f8f")   # SPI
GREEN  = HexColor("#2c6e49")   # IRQ
GREY   = HexColor("#8a8a8a")
LGREY  = HexColor("#d8d8d8")

P = 0.2 * inch          # 2:1 -- one 0.1" hole pitch drawn as 0.2"
COLS, ROWS = 27, 19     # a 5 x 7 cm perf board, landscape

COLOR = {"5v": RED, "3v3": ORANGE, "gnd": BLACK, "spi": BLUE, "irq": GREEN,
         "nc": GREY}

PAGES = 5


# ----------------------------------------------------------------- primitives

def gx(ox, c):
    return ox + (c - 1) * P


def gy(oy, r):
    return oy - (r - 1) * P


def title(c, y, text, sub=None):
    c.setFillColor(BLACK)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(M, y, text)
    if sub:
        c.setFont("Helvetica", 9)
        c.setFillColor(GREY)
        c.drawString(M, y - 13, sub)
    c.setStrokeColor(LGREY)
    c.setLineWidth(0.8)
    c.line(M, y - 20, W - M, y - 20)
    return y - 36


def board(c, ox, oy, cols=COLS, rows=ROWS, cap_dy=11):
    """Draw the perf board outline, the hole grid and the col/row rulers."""
    x0, y0 = gx(ox, 1) - P / 2, gy(oy, rows) - P / 2
    bw, bh = cols * P, rows * P

    c.setFillColor(HexColor("#fbf7ee"))
    c.setStrokeColor(GREY)
    c.setLineWidth(1.0)
    c.rect(x0, y0, bw, bh, fill=1, stroke=1)

    c.setFillColor(HexColor("#c9c2b4"))
    for cc in range(1, cols + 1):
        for rr in range(1, rows + 1):
            c.circle(gx(ox, cc), gy(oy, rr), 1.5, fill=1, stroke=0)

    c.setFont("Helvetica", 5)
    c.setFillColor(GREY)
    for cc in range(1, cols + 1):
        if cc % 2 == 1:
            c.drawCentredString(gx(ox, cc), y0 + bh + 3, str(cc))
    for rr in range(1, rows + 1):
        if rr % 2 == 1:
            c.drawRightString(x0 - 3, gy(oy, rr) - 1.8, str(rr))

    c.setFont("Helvetica-Oblique", 6)
    c.setFillColor(GREY)
    c.drawString(x0, y0 - cap_dy, "drawn 2:1 -- one grid step = 0.1 in (2.54 mm). "
                                  "Real board %.1f x %.1f mm." % (cols * 2.54, rows * 2.54))
    return x0, y0, bw, bh


def pad(c, ox, oy, cc, rr, col=BLACK, r=3.1):
    c.setFillColor(col)
    c.circle(gx(ox, cc), gy(oy, rr), r, fill=1, stroke=0)
    c.setFillColor(HexColor("#ffffff"))
    c.circle(gx(ox, cc), gy(oy, rr), 1.0, fill=1, stroke=0)


def lbl(c, x, y, text, size=5, col=BLACK, align="l"):
    c.setFont("Helvetica", size)
    c.setFillColor(col)
    if align == "l":
        c.drawString(x, y, text)
    elif align == "r":
        c.drawRightString(x, y, text)
    else:
        c.drawCentredString(x, y, text)


def vlbl(c, x, y, text, size=4.6, col=GREY):
    """Label rotated 90 degrees, reading bottom to top, anchored at (x, y)."""
    c.saveState()
    c.translate(x, y)
    c.rotate(90)
    c.setFont("Helvetica", size)
    c.setFillColor(col)
    c.drawString(0, -size / 2 + 0.5, text)
    c.restoreState()


def vrlbl(c, x, y, text, size=4.6, col=GREY):
    """Rotated label whose RIGHT-HAND end is at (x, y): it grows downward."""
    c.setFont("Helvetica", size)
    vlbl(c, x, y - c.stringWidth(text, "Helvetica", size), text, size, col)


def outline(c, ox, oy, c0, r0, c1, r1, name, note=None, dash=False, tpos="above"):
    """Translucent footprint box. tpos: above | below | center | none."""
    x0, y0 = gx(ox, c0), gy(oy, r1)
    x1, y1 = gx(ox, c1), gy(oy, r0)
    c.setStrokeColor(GREY)
    c.setLineWidth(0.9)
    if dash:
        c.setDash(2, 2)
    c.setFillColorRGB(0.35, 0.45, 0.60, alpha=0.10)
    c.rect(x0, y0, x1 - x0, y1 - y0, fill=1, stroke=1)
    c.setDash()
    if tpos == "none":
        return
    c.setFillColor(HexColor("#33425c"))
    c.setFont("Helvetica-Bold", 6.5)
    if tpos == "above":
        c.drawString(x0, y1 + 3, name)
        ny = y1 + 3 - 8
    elif tpos == "center":
        c.drawCentredString((x0 + x1) / 2, (y0 + y1) / 2 - 2.3, name)
        ny = y0 - 8
    else:
        c.drawString(x0, y0 - 8, name)
        ny = y0 - 16
    if note:
        c.setFont("Helvetica", 5.5)
        c.setFillColor(GREY)
        c.drawString(x0, ny, note)


def wire(c, ox, oy, a, b, col=BLUE, wd=1.3, alpha=0.85):
    c.setStrokeColor(col)
    c.setLineWidth(wd)
    c.setStrokeAlpha(alpha)
    c.line(gx(ox, a[0]), gy(oy, a[1]), gx(ox, b[0]), gy(oy, b[1]))
    c.setStrokeAlpha(1)


def bus(c, ox, oy, r, c0, c1, col=BLACK, horiz=True):
    c.setStrokeColor(col)
    c.setLineWidth(3.2)
    c.setStrokeAlpha(0.55)
    if horiz:
        c.line(gx(ox, c0), gy(oy, r), gx(ox, c1), gy(oy, r))
    else:
        c.line(gx(ox, r), gy(oy, c0), gx(ox, r), gy(oy, c1))
    c.setStrokeAlpha(1)


def tiepoint(c, ox, oy, cc, rr):
    """Mark the two holes a cable tie loops through."""
    c.setStrokeColor(GREY)
    c.setLineWidth(0.8)
    c.setDash(2, 2)
    c.rect(gx(ox, cc) - 4, gy(oy, rr) - 4, P + 8, 8, fill=0, stroke=1)
    c.setDash()


def table(c, x, y, cols, rows, widths, size=6.2, head=True):
    c.setFont("Helvetica-Bold", size)
    c.setFillColor(BLACK)
    if head:
        cx = x
        for i, h in enumerate(cols):
            c.drawString(cx, y, h)
            cx += widths[i]
        c.setStrokeColor(LGREY)
        c.setLineWidth(0.6)
        c.line(x, y - 3, x + sum(widths), y - 3)
        y -= 11
    c.setFont("Helvetica", size)
    for row in rows:
        cx = x
        for i, cell in enumerate(row):
            col = BLACK
            if isinstance(cell, tuple):
                cell, col = cell
            c.setFillColor(col)
            c.drawString(cx, y, str(cell))
            cx += widths[i]
        y -= 9
    return y


def rich(c, x, y, text, size):
    """Draw one line, honouring inline **bold** runs."""
    bold = False
    cx = x
    for part in text.split("**"):
        if part:
            font = "Helvetica-Bold" if bold else "Helvetica"
            c.setFont(font, size)
            c.setFillColor(BLACK if bold else HexColor("#333333"))
            c.drawString(cx, y, part)
            cx += c.stringWidth(part, font, size)
        bold = not bold


def notes(c, x, y, lines, size=7):
    for ln in lines:
        rich(c, x, y, ln, size)
        y -= size + 3.2
    return y


def legend(c, x, y):
    items = [("5 V", RED), ("3.3 V", ORANGE), ("GND", BLACK), ("SPI", BLUE),
             ("IRQ", GREEN), ("no connection", GREY)]
    c.setFont("Helvetica", 6)
    for name, col in items:
        c.setStrokeColor(col)
        c.setLineWidth(2.2)
        c.line(x, y + 2, x + 12, y + 2)
        c.setFillColor(BLACK)
        c.drawString(x + 15, y, name)
        x += 15 + c.stringWidth(name, "Helvetica", 6) + 12


def footer(c, page):
    c.setFont("Helvetica", 7)
    c.setFillColor(GREY)
    c.drawString(M, 0.42 * inch, "AS3935 lightning detector -- protoboard layout, hardware rev 2. "
                                 "Generated by make-protoboard-layout.py; see README section 7.5.")
    c.drawRightString(W - M, 0.42 * inch, "page %d of %d" % (page, PAGES))
    c.showPage()


# --------------------------------------------------------------- board data
#
# The RJ45 pigtail lands in one straight run of NINE holes on each board, in
# breakout-header order, so the ribbon from the panel jack never has to cross
# itself. Pin numbers are the numbers silkscreened on the breakout, which is
# the only labelling that is unambiguous -- see page 4 of as3935-node-wiring.pdf.

# --- sensor board --------------------------------------------------------
# Landing column 2, rows 5..13. SH at the top, pin 1 at the bottom, which puts
# 5 V (pin 1) on the same row as the power chain and costs zero crossings.
S_ENTRY = [
    ((2, 5),  "SH", "shell",   "shield", "nc"),
    ((2, 6),  "8",  "brown",   "IRQ",    "irq"),
    ((2, 7),  "7",  "wh/brn",  "CS",     "spi"),
    ((2, 8),  "6",  "green",   "GND",    "gnd"),
    ((2, 9),  "5",  "wh/blu",  "MISO",   "spi"),
    ((2, 10), "4",  "blue",    "MOSI",   "spi"),
    ((2, 11), "3",  "wh/grn",  "SCLK",   "spi"),
    ((2, 12), "2",  "orange",  "GND",    "gnd"),
    ((2, 13), "1",  "wh/org",  "5 V",    "5v"),
]

# SEN-39003 8-pin header, col 17, top to bottom. VERIFY against the silkscreen:
# the layout gives every pin its own landing, so a different order only changes
# which link goes where, not where anything sits.
S_HDR = [
    ((17, 3),  "IRQ",  "irq"),
    ((17, 4),  "SI",   "gnd"),
    ((17, 5),  "CS",   "spi"),
    ((17, 6),  "SCK",  "spi"),
    ((17, 7),  "MISO", "spi"),
    ((17, 8),  "MOSI", "spi"),
    ((17, 9),  "GND",  "gnd"),
    ((17, 10), "VCC",  "3v3"),
]

S_BUSES = [
    ("BUS-A", "5 V filtered", 13, 7, 9,  "5v",  "row 13, cols 7-9"),
    ("BUS-B", "3.3 V",        13, 11, 13, "3v3", "row 13, cols 11-13"),
    ("BUS-C", "PG  power ground", 15, 5, 14, "gnd", "row 15, cols 5-14"),
    ("BUS-D", "SG  sensor ground", 9, 13, 16, "gnd", "row 9, cols 13-16"),
]

S_WIRES = [
    ("W-S1",  "5 V in",     (2, 13),  (4, 13),  "5v",  "pin 1 into R1"),
    ("W-S2",  "GND pin 2",  (2, 12),  (5, 15),  "gnd", "onto PG"),
    ("W-S3",  "GND pin 6",  (2, 8),   (6, 15),  "gnd", "onto PG -- the SCLK return"),
    ("W-S4",  "LDO GND",    (10, 13), (10, 15), "gnd", "U1 pin 2 down to PG"),
    ("W-S5",  "3.3 V out",  (13, 13), (16, 10), "3v3", "BUS-B up to the C4 / VCC node"),
    ("W-S6",  "VCC link",   (16, 10), (17, 10), "3v3", "one hole -- do not lengthen"),
    ("W-S7",  "GND link",   (17, 9),  (15, 9),  "gnd", "sensor GND onto SG"),
    ("W-S8",  "SI strap",   (17, 4),  (13, 9),  "gnd", "grounds SI: selects SPI, not I2C"),
    ("W-S9",  "SG-PG tie",  (14, 9),  (14, 15), "gnd", "the ONLY tie between the grounds"),
    ("W-S10", "SCLK",       (2, 11),  (17, 6),  "spi", ""),
    ("W-S11", "MOSI",       (2, 10),  (17, 8),  "spi", ""),
    ("W-S12", "MISO",       (2, 9),   (17, 7),  "spi", ""),
    ("W-S13", "CS",         (2, 7),   (17, 5),  "spi", ""),
    ("W-S14", "IRQ",        (2, 6),   (17, 3),  "irq", ""),
]

S_PARTS = [
    ("R1", "100 ohm 1/4 W metal film",     "(4,13) - (7,13)"),
    ("C2", "47 uF 50 V, EEU-FR1H470",      "+ (8,13)   - (8,15)"),
    ("U1", "MCP1700-3302E, TO-92",         "VIN (9,13)  GND (10,13)  VOUT (11,13)"),
    ("C3", "1 uF X7R, C330C105K5R5TA",     "(12,13) - (12,15)"),
    ("C4", "100 nF X7R, C320C104K5R5TA",   "(16,10) - (16,9)"),
    ("M1", "SEN-39003 on an 8-pin header", "(17,3) .. (17,10), soldered direct"),
]

# extra pads to draw solid on the sensor board: (hole, net)
S_PADS = [((4, 13), "5v"), ((7, 13), "5v"), ((8, 13), "5v"), ((8, 15), "gnd"),
          ((9, 13), "5v"), ((10, 13), "gnd"), ((10, 15), "gnd"),
          ((11, 13), "3v3"), ((12, 13), "3v3"), ((12, 15), "gnd"),
          ((13, 13), "3v3"), ((16, 10), "3v3"), ((16, 9), "gnd"),
          ((13, 9), "gnd"), ((14, 9), "gnd"), ((15, 9), "gnd"),
          ((5, 15), "gnd"), ((6, 15), "gnd"), ((14, 15), "gnd")]

# --- main board ----------------------------------------------------------
# ESP32-DevKitC V4 / ESP32-WROOM-32D, 38 pin, 19 per row, rows 1.0 in (10 holes)
# apart. Laid on the perf LENGTHWISE with the USB end to the LEFT, which is a
# 90-degree clockwise rotation of the usual portrait pinout drawing: the
# portrait left-hand column becomes the top row, read bottom-to-top.
M_TOP = ["5V", "CMD", "D3", "D2", "13", "GND", "12", "14", "27", "26",
         "25", "33", "32", "35", "34", "VN", "VP", "EN", "3V3"]
M_BOT = ["CLK", "SD0", "SD1", "15", "2", "0", "4", "16", "17", "5",
         "18", "19", "GND", "21", "RX0", "TX0", "22", "23", "GND"]
M_COL0 = 2               # pin position 1 sits in this column
M_ROW_TOP, M_ROW_BOT = 4, 14

# the pins this design actually uses, as (row, col, net, function)
M_USED = [
    (M_ROW_TOP, 2,  "5v",  "5 V"),
    (M_ROW_TOP, 7,  "gnd", "GND"),
    (M_ROW_BOT, 8,  "irq", "IRQ"),
    (M_ROW_BOT, 11, "spi", "CS"),
    (M_ROW_BOT, 12, "spi", "SCLK"),
    (M_ROW_BOT, 13, "spi", "MISO"),
    (M_ROW_BOT, 14, "gnd", "GND"),
    (M_ROW_BOT, 19, "spi", "MOSI"),
    (M_ROW_BOT, 20, "gnd", "SHLD"),
]

# Landing row 19, cols 9..17, pin 1 leftmost -- keeps the two long power runs
# from C1 as short as the DevKitC pinout allows.
M_ENTRY = [
    ((9, 19),  "1",  "wh/org", "5 V",    "5v"),
    ((10, 19), "2",  "orange", "GND",    "gnd"),
    ((11, 19), "3",  "wh/grn", "SCLK",   "spi"),
    ((12, 19), "4",  "blue",   "MOSI",   "spi"),
    ((13, 19), "5",  "wh/blu", "MISO",   "spi"),
    ((14, 19), "6",  "green",  "GND",    "gnd"),
    ((15, 19), "7",  "wh/brn", "CS",     "spi"),
    ((16, 19), "8",  "brown",  "IRQ",    "irq"),
    ((17, 19), "SH", "shell",  "shield", "gnd"),
]

M_WIRES = [
    ("W-M1",  "C1+ to 5V",    (3, 3),   (2, 4),   "5v",  "as short as it will go"),
    ("W-M2",  "C1- to GND",   (5, 3),   (7, 4),   "gnd", "as short as it will go"),
    ("W-M3",  "5 V to cable", (3, 3),   (9, 19),  "5v",  "on the back, under the dev board"),
    ("W-M4",  "GND to cable", (5, 3),   (10, 19), "gnd", "twist with W-M3"),
    ("W-M5",  "SCLK to R2",   (12, 14), (11, 16), "spi", "GPIO18"),
    ("W-M6",  "MOSI to R3",   (19, 14), (12, 16), "spi", "GPIO23"),
    ("W-M7",  "CS to R4",     (11, 14), (15, 16), "spi", "GPIO5"),
    ("W-M8",  "MISO",         (13, 14), (13, 19), "spi", "GPIO19 -- no resistor, it is an input"),
    ("W-M9",  "IRQ",          (8, 14),  (16, 19), "irq", "GPIO4 -- no resistor"),
    ("W-M10", "SCLK return",  (14, 14), (14, 19), "gnd", "the GND beside GPIO18 -> pin 6"),
    ("W-M11", "shield bond",  (20, 14), (17, 19), "gnd", "SH grounded at THIS end only"),
]

M_PARTS = [
    ("A1", "ESP32-DevKitC V4 (WROOM-32D)", "female headers: row 4 c2-20, row 14 c2-20"),
    ("C1", "470-1000 uF 16-25 V 105 C",    "+ (3,3)   - (5,3)   stripe at (5,3)"),
    ("R2", "SCLK series -- wire link",     "(11,16) - (11,19)"),
    ("R3", "MOSI series -- wire link",     "(12,16) - (12,19)"),
    ("R4", "CS series -- wire link",       "(15,16) - (15,19)"),
]


# ------------------------------------------------------------------ pages

def _entry_labels(c, ox, oy, entries, x, align="r"):
    for hole, pin, wc, net, kind in entries:
        lbl(c, x, gy(oy, hole[1]) - 1.8, "%s  %s  %s" % (pin, net, wc), 5,
            COLOR[kind], align)


def page_sensor_placement(c):
    y = title(c, H - M, "1.  SENSOR BOARD -- component placement",
              "5 x 7 cm perf board, isolated pads, viewed from the component side. "
              "Everything here is SELV: 5 V and SPI only.")
    ox, oy = M + 1.05 * inch, y - 0.30 * inch
    x0, y0, bw, bh = board(c, ox, oy)

    outline(c, ox, oy, 16.6, 1.8, 26.6, 11.2, "M1  SEN-39003 (AS3935)",
            "about 25 x 24 mm; stands off the board on its 8-pin header",
            dash=True, tpos="below")
    c.setStrokeColor(RED)
    c.setLineWidth(0.9)
    c.setDash(3, 2)
    c.circle(gx(ox, 23.5), gy(oy, 6.5), 1.35 * P, fill=0, stroke=1)
    c.setDash()
    lbl(c, gx(ox, 23.5), gy(oy, 6.5) + 3, "ANTENNA", 5.5, RED, "c")
    lbl(c, gx(ox, 23.5), gy(oy, 6.5) - 5, "KEEP CLEAR", 5.5, RED, "c")

    outline(c, ox, oy, 4.3, 12.5, 6.7, 13.5, "R1", tpos="above")
    outline(c, ox, oy, 7.5, 12.5, 8.5, 15.5, "C2", tpos="center")
    outline(c, ox, oy, 8.6, 12.3, 11.4, 13.7, "U1", tpos="above")
    outline(c, ox, oy, 11.5, 12.5, 12.5, 15.5, "C3", tpos="center")
    outline(c, ox, oy, 15.6, 8.6, 16.4, 10.4, "C4", tpos="below")

    for hole, pin, wc, net, kind in S_ENTRY:
        pad(c, ox, oy, hole[0], hole[1], COLOR[kind])
    for hole, name, kind in S_HDR:
        pad(c, ox, oy, hole[0], hole[1], COLOR[kind], r=2.6)
        lbl(c, gx(ox, 17) + 6, gy(oy, hole[1]) - 1.8, name, 5, COLOR[kind])
    for h, k in S_PADS:
        pad(c, ox, oy, h[0], h[1], COLOR[k], r=2.6)

    lbl(c, x0 - 12, gy(oy, 3) - 1.8, "RJ45 pigtail", 5.5, GREY, "r")
    lbl(c, x0 - 12, gy(oy, 4) - 1.8, "from the panel jack", 5.5, GREY, "r")
    _entry_labels(c, ox, oy, S_ENTRY, x0 - 12)

    tiepoint(c, ox, oy, 1, 15)
    lbl(c, gx(ox, 2.6), gy(oy, 17) - 1.8,
        "cable tie through (1,15)/(2,15) -- pigtail strain relief", 5.5, GREY)

    lbl(c, gx(ox, 18), gy(oy, 15) - 1.8,
        "Nothing under the antenna:", 6, RED)
    lbl(c, gx(ox, 18), gy(oy, 16) - 1.8,
        "no wire, no bus, no standoff,", 5.5, RED)
    lbl(c, gx(ox, 18), gy(oy, 17) - 1.8,
        "and nylon hardware only.", 5.5, RED)

    legend(c, M, y0 - 26)

    ny = table(c, M, y0 - 46, ["Ref", "Part", "Holes"], S_PARTS, [34, 150, 190])

    ny -= 14
    notes(c, M, ny, [
        "**Placement rules that are not negotiable**",
        "C4 sits one hole from VCC and one from GND. That tiny loop is the",
        "     entire point of the part; do not move it to make room.",
        "U1 TO-92, flat face toward you and leads down, is 1 VIN, 2 GND,",
        "     3 VOUT. Splay the 0.05 in leads out to 0.1 in.",
        "Hole (10,13) between BUS-A and BUS-B is the LDO's ground pin and",
        "     is on neither bus. That gap is the input/output isolation.",
        "Confirm which end of the SEN-39003 carries the loop antenna before",
        "     you solder it, and point that end away from the power chain.",
    ])
    notes(c, M + 272, ny, [
        "**Soldered, not socketed**",
        "The SEN-39003 header goes straight into the perf. Solderless",
        "     contacts on this rail are the prime suspect for the step",
        "     change in README 11.3, and the board is calibrated per unit,",
        "     so it is not a part you swap casually anyway.",
        "",
        "**Verify the header order against the silkscreen**",
        "The eight pin names above are the order this drawing assumes. Each",
        "     pin gets its own landing, so if yours differs, only the",
        "     wire list changes -- nothing moves.",
    ])
    footer(c, 1)


def page_sensor_wiring(c):
    y = title(c, H - M, "2.  SENSOR BOARD -- point-to-point wiring",
              "X-ray view from the component side. All of this is on the BACK of the board, "
              "so it mirrors left-right when you flip it over.")
    ox, oy = M + 1.05 * inch, y - 0.30 * inch
    x0, y0, bw, bh = board(c, ox, oy)

    for ref, net, r, c0, c1, kind, where in S_BUSES:
        bus(c, ox, oy, r, c0, c1, COLOR[kind])

    for ref, net, a, b, kind, note in S_WIRES:
        wire(c, ox, oy, a, b, COLOR[kind])

    for hole, pin, wc, net, kind in S_ENTRY:
        pad(c, ox, oy, hole[0], hole[1], COLOR[kind])
    for hole, name, kind in S_HDR:
        pad(c, ox, oy, hole[0], hole[1], COLOR[kind], r=2.6)
        lbl(c, gx(ox, 17) + 6, gy(oy, hole[1]) - 1.8, name, 5, COLOR[kind])
    for h, k in S_PADS:
        pad(c, ox, oy, h[0], h[1], COLOR[k], r=2.6)

    _entry_labels(c, ox, oy, S_ENTRY, x0 - 12)
    lbl(c, gx(ox, 6.6), gy(oy, 13) + 9, "BUS-A  5 V filt", 5.5, RED)
    lbl(c, gx(ox, 11), gy(oy, 13) + 9, "BUS-B  3.3 V", 5.5, ORANGE)
    lbl(c, gx(ox, 5), gy(oy, 15) - 9, "BUS-C  PG", 5.5, BLACK)
    lbl(c, gx(ox, 13), gy(oy, 9) + 9, "BUS-D  SG", 5.5, BLACK)
    lbl(c, gx(ox, 15), gy(oy, 12) - 1.8, "W-S9", 6, BLACK)
    lbl(c, gx(ox, 15), gy(oy, 12) - 9, "the only tie", 5.5, BLACK)

    legend(c, M, y0 - 26)

    rows = [(ref, net, "(%d,%d)" % a, "(%d,%d)" % b, note)
            for ref, net, a, b, kind, note in S_WIRES]
    bl = [(ref, net, where.split(", ")[0], where.split(", ")[1],
           "bare 22 AWG laid across the back of the pads")
          for ref, net, r, c0, c1, kind, where in S_BUSES]
    ny = table(c, M, y0 - 46, ["Ref", "Net", "From", "To", "Wire / note"],
               bl + rows, [40, 78, 52, 52, 190])

    ny -= 12
    notes(c, M, ny, [
        "**Two grounds, one tie**",
        "PG carries the cable's ground return, the bulk cap and the LDO",
        "     reference. SG carries only the sensor's GND pin, its 100 nF",
        "     and the SI strap. They meet at exactly one place: W-S9.",
        "Bridge them anywhere else and you have wrapped a ground loop",
        "     around the LDO; the 100 nF stops being local and the whole",
        "     point of the split is gone.",
        "Where along PG you tie is not critical -- at 350 uA the drop along",
        "     the bus is nanovolts. That there is only ONE tie is critical.",
    ])
    notes(c, M + 272, ny, [
        "**C3 references PG, C4 references SG**",
        "C3 is the MCP1700's stability capacitor, so it belongs to the",
        "     regulator and lands on PG. C4 is the sensor's decoupling, so",
        "     it belongs to the sensor and lands on SG. Swapping them",
        "     defeats the split as surely as a second tie would.",
        "",
        "**Crossings are fine, except over a bus**",
        "Point-to-point links are insulated and run on the solder side;",
        "     they cross each other freely. The four buses are BARE. Keep",
        "     every wire clear of them or sleeve it where it passes.",
    ])
    footer(c, 2)


def _esp32(c, ox, oy):
    """The dev board, lying lengthwise with the USB end off the left edge."""
    outline(c, ox, oy, 0.55, M_ROW_TOP - 0.55, 21.0, M_ROW_BOT + 0.55, "",
            dash=True, tpos="none")
    for i, name in enumerate(M_TOP):
        vlbl(c, gx(ox, M_COL0 + i), gy(oy, M_ROW_TOP) - 24, name)
    for i, name in enumerate(M_BOT):
        vlbl(c, gx(ox, M_COL0 + i), gy(oy, M_ROW_BOT) + 6, name)
    for i in range(19):
        pad(c, ox, oy, M_COL0 + i, M_ROW_TOP, LGREY, r=2.4)
        pad(c, ox, oy, M_COL0 + i, M_ROW_BOT, LGREY, r=2.4)
    for r, cc, kind, what in M_USED:
        pad(c, ox, oy, cc, r, COLOR[kind], r=2.9)
        if r == M_ROW_TOP:
            vlbl(c, gx(ox, cc) + 4.5, gy(oy, r) + 6, what, 5.0, COLOR[kind])
        else:
            vrlbl(c, gx(ox, cc) + 4.5, gy(oy, r) - 6, what, 5.0, COLOR[kind])

    c.setStrokeColor(GREY)
    c.setLineWidth(0.9)
    c.setDash(2, 2)
    x0 = gx(ox, 1) - P / 2
    c.rect(x0 - 11, gy(oy, 10.6), 17, 3.2 * P, fill=0, stroke=1)
    c.setDash()

    lbl(c, gx(ox, 4), gy(oy, 7) - 1.8, "A1   ESP32-DevKitC V4  /  WROOM-32D", 7, BLACK)
    lbl(c, gx(ox, 4), gy(oy, 8) - 1.8,
        "38 pins, 19 per row, rows 1.0 in apart.  On female headers.", 5.5, GREY)
    lbl(c, gx(ox, 4), gy(oy, 9) - 1.8,
        "Pin names read as printed on the board, with USB to the LEFT.", 5.5, GREY)
    lbl(c, gx(ox, 4), gy(oy, 10) - 1.8,
        "The micro-USB socket overhangs the left edge of the perf.", 5.5, GREY)
    lbl(c, gx(ox, 4), gy(oy, 11) - 1.8,
        "Rows 5-13 under the board are unusable; wires pass on the back.", 5.5, GREY)
    lbl(c, gx(ox, 17), gy(oy, 12) - 1.8, "PCB antenna end", 5.5, GREY)


def _entry_below(c, ox, oy, entries):
    """Pigtail landing labels in the margin below the board, reading upward."""
    for hole, pin, wc, net, kind in entries:
        vrlbl(c, gx(ox, hole[0]) + 1.8, gy(oy, hole[1]) - P / 2 - 3,
              "%s  %s  %s" % (pin, net, wc), 5.0, COLOR[kind])


def page_main_placement(c):
    y = title(c, H - M, "3.  MAIN BOARD -- component placement",
              "5 x 7 cm perf board. Contents: the ESP32 dev board, the 5 V bulk cap at its "
              "pins, three series positions, and the cable pigtail.")
    ox, oy = M + 0.75 * inch, y - 0.30 * inch
    x0, y0, bw, bh = board(c, ox, oy, cap_dy=46)

    _esp32(c, ox, oy)
    outline(c, ox, oy, 2.4, 1.6, 5.6, 3.4, "C1", tpos="above")
    lbl(c, gx(ox, 8), gy(oy, 2) - 1.8, "body overhangs the top edge", 5.5, GREY)
    outline(c, ox, oy, 10.6, 15.6, 15.4, 19.4, "R2 / R3 / R4", dash=True, tpos="none")

    for h, k in (((3, 3), "5v"), ((5, 3), "gnd")):
        pad(c, ox, oy, h[0], h[1], COLOR[k])
    for cc, k in ((11, "spi"), (12, "spi"), (15, "spi")):
        pad(c, ox, oy, cc, 16, COLOR[k], r=2.6)
    for hole, pin, wc, net, kind in M_ENTRY:
        pad(c, ox, oy, hole[0], hole[1], COLOR[kind])
    _entry_below(c, ox, oy, M_ENTRY)

    lbl(c, gx(ox, 17), gy(oy, 16) - 1.8, "RJ45 pigtail from the panel jack:", 5.5, GREY)
    lbl(c, gx(ox, 17), gy(oy, 17) - 1.8, "nine holes, row 19, cols 9-17,", 5.5, GREY)
    lbl(c, gx(ox, 17), gy(oy, 18) - 1.8, "pin 1 at the left.", 5.5, GREY)
    tiepoint(c, ox, oy, 21, 19)
    lbl(c, gx(ox, 22.3), gy(oy, 19) - 1.8, "cable tie (21,19)/(22,19)", 5.5, GREY)

    legend(c, M, y0 - 60)

    ny = table(c, M, y0 - 80, ["Ref", "Part", "Holes"], M_PARTS, [30, 165, 195])

    ny -= 14
    notes(c, M, ny, [
        "**Socket this one, unlike the sensor board**",
        "Dev boards die, and this one sits metres from the antenna, so the",
        "     contact-resistance worry that governs the sensor board does",
        "     not apply. Female headers; keep BOOT and EN reachable.",
        "",
        "**Check the row spacing before you solder the headers**",
        "Drawn at 10 holes (1.0 in), measured off the DevKitC V4. If yours",
        "     is 0.9 in, ONLY the top header and C1 move: top row becomes",
        "     row 5, C1 becomes (3,4)/(5,4). Every signal is on the bottom",
        "     row, which does not move. Use the dev board as its own jig.",
    ])
    notes(c, M + 272, ny, [
        "**C1 cannot be as tight as you want it to be**",
        "The DevKitC has FIVE pins between 5V and its nearest ground, so",
        "     the bulk-cap loop is about 27 mm however you arrange it.",
        "     That is a property of the dev board, not of this layout.",
        "     Keep W-M1 and W-M2 short and stop optimising.",
        "",
        "**R2/R3/R4 are wire links on day one**",
        "Only the three lines the ESP32 drives get a position. MISO and",
        "     IRQ are driven from the far end, so damping them here would",
        "     do nothing. Fit 33-100 ohm only if the 3 m sweep misbehaves.",
    ])
    footer(c, 3)


def page_main_wiring(c):
    y = title(c, H - M, "4.  MAIN BOARD -- point-to-point wiring",
              "X-ray view from the component side. The back-side wires run under the dev "
              "board, so the two long power runs cost nothing.")
    ox, oy = M + 0.75 * inch, y - 0.30 * inch
    x0, y0, bw, bh = board(c, ox, oy, cap_dy=46)
    _esp32(c, ox, oy)

    for ref, net, a, b, kind, note in M_WIRES:
        wire(c, ox, oy, a, b, COLOR[kind])

    for h, k in (((3, 3), "5v"), ((5, 3), "gnd")):
        pad(c, ox, oy, h[0], h[1], COLOR[k])
    for cc, k in ((11, "spi"), (12, "spi"), (15, "spi")):
        pad(c, ox, oy, cc, 16, COLOR[k], r=2.6)
    for hole, pin, wc, net, kind in M_ENTRY:
        pad(c, ox, oy, hole[0], hole[1], COLOR[kind])
    _entry_below(c, ox, oy, M_ENTRY)

    lbl(c, gx(ox, 2.5), gy(oy, 2) - 1.8, "C1  +", 5.5, RED)
    lbl(c, gx(ox, 4.7), gy(oy, 2) - 1.8, "-", 5.5, BLACK)
    lbl(c, gx(ox, 10.4), gy(oy, 17.4) - 1.8, "R2 R3", 5.5, BLUE)
    lbl(c, gx(ox, 14.7), gy(oy, 17.4) - 1.8, "R4", 5.5, BLUE)

    legend(c, M, y0 - 60)

    rows = [(ref, net, "(%d,%d)" % a, "(%d,%d)" % b, note)
            for ref, net, a, b, kind, note in M_WIRES]
    ny = table(c, M, y0 - 80, ["Ref", "Net", "From", "To", "Note"], rows,
               [40, 76, 52, 52, 192])

    ny -= 12
    notes(c, M, ny, [
        "**C1 is the reason this board exists**",
        "470-1000 uF, 105 C, at the 5V and GND pins. It is the reservoir",
        "     the USB cable cannot supply fast enough during a WiFi burst",
        "     -- README 7.4. The stripe is the minus lead, at (5,3).",
        "",
        "**The pair discipline is deliberate**",
        "W-M3/W-M4 leave from C1 and land on cable pins 1 and 2, which are",
        "     a twisted pair. W-M10 takes the GND pin next to GPIO18 to",
        "     cable pin 6, the other half of the SCLK pair.",
    ])
    notes(c, M + 272, ny, [
        "**The shield is bonded here and nowhere else**",
        "W-M11 grounds the jack's SH pin at the main board. At the sensor",
        "     board SH lands in its hole and stops there. One end only:",
        "     bond both and a shielded patch cable becomes a ground loop",
        "     wrapped around the whole run.",
        "",
        "**Route the USB cable away from the Cat5.** Do not bundle them",
        "     parallel, in the box or outside it.",
    ])
    footer(c, 4)


def page_build(c):
    y = title(c, H - M, "5.  Build order, and the things that will bite",
              "Read this before you cut anything. Sections refer to the project README.")

    col1 = M
    col2 = M + 3.6 * inch
    yy = y

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(BLACK)
    c.drawString(col1, yy, "Sensor board")
    yy -= 14
    yy = notes(c, col1, yy, [
        "1.  Cut/snap the perf to 27 x 19 holes and de-burr. Mark hole (1,1)",
        "      in a corner with a pen; every coordinate counts from it.",
        "2.  Solder the four buses first, while the board is flat and empty:",
        "      BUS-C PG (row 15, c5-14), BUS-D SG (row 9, c13-16),",
        "      BUS-A 5 V (row 13, c7-9), BUS-B 3.3 V (row 13, c11-13).",
        "3.  R1, C2, U1, C3, C4 -- shortest parts first.",
        "4.  W-S9, the single SG-PG tie. Do it deliberately and mark it.",
        "5.  Solder the 8-pin header into the SEN-39003, then that assembly",
        "      into (17,3)..(17,10). Check the antenna end points right,",
        "      away from the power chain, before you commit.",
        "6.  W-S8, the SI strap. Without it the part talks I2C and nothing",
        "      works at all -- README 5.",
        "7.  The five signal links, then the pigtail. Tie at (1,15).",
        "8.  Before power: ohmmeter 3.3 V to either ground. Under a few",
        "      hundred ohms means a bridge -- find it now, not later.",
    ], size=7)

    yy -= 8
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(BLACK)
    c.drawString(col1, yy, "Main board")
    yy -= 14
    yy = notes(c, col1, yy, [
        "1.  Count your dev board's pins and measure its header row spacing",
        "      before anything else. Then solder the female headers using",
        "      the dev board itself as the jig, so the rows end up parallel.",
        "2.  C1, stripe at (5,3). Then W-M1 and W-M2, short.",
        "3.  R2/R3/R4 as plain wire links. Then the signal wires, then the",
        "      pigtail. Tie at (21,19).",
        "4.  Power it with NO ESP32 in the socket and confirm 5 V appears at",
        "      cable pin 1 and nowhere it should not.",
    ], size=7)

    yy2 = y
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(BLACK)
    c.drawString(col2, yy2, "Things that will bite")
    yy2 -= 14
    notes(c, col2, yy2, [
        "**The X-ray thing.**  Both wiring pages are drawn as if you could",
        "see through the board from the top, because that is how you place",
        "parts. Flip the board to solder and left/right swap. This is the",
        "single most common perf-board error.",
        "",
        "**Isolated pads, not strips.**  If what you have is stripboard,",
        "every row here is already a bus and the layout is wrong without",
        "track cuts. Check before you buy.",
        "",
        "**RJ45 on 0.1 in perf.**  It does not fit. Panel-mount breakout",
        "plus a nine-wire pigtail, both boards -- and wire to the numbers",
        "silkscreened on the breakout, never to a position in a photo.",
        "",
        "**This jack is not Ethernet.**  It carries 5 V and SPI. A live PoE",
        "port puts 48 V on those lines and destroys both ends. Label both",
        "boxes now, while you are holding them -- README 7.1.",
        "",
        "**Nylon standoffs, nylon screws** on the sensor board especially.",
        "A steel screw beside a 500 kHz loop antenna is a shorted turn.",
        "",
        "**Solid wire, not the silicone stranded.**  Buses have to be bare",
        "solid or they are not straight; links have to be solid or they",
        "will not enter a hole without tinning. README 7.6.",
        "",
        "**Rigidity is a measurement, not a feeling.**  README 11.3: the",
        "breadboard's noise floor fell by two thirds the moment the build",
        "was handled. Phase 2 in README 15 is survey, handle the box,",
        "survey again. If the rates move, the build is furniture and",
        "nothing measured on it means anything.",
        "",
        "**Then set data_rate: 200kHz** in lightning-detector.yaml before",
        "the first survey -- it defaults to 1 MHz, README 7.1.",
    ], size=7)

    # scale reference strip
    c.setStrokeColor(GREY)
    c.setLineWidth(0.8)
    yb = 1.05 * inch
    c.line(M, yb, M + 2 * inch, yb)
    for i in range(21):
        c.line(M + i * 0.1 * inch, yb, M + i * 0.1 * inch, yb + (5 if i % 5 else 8))
    lbl(c, M, yb - 9, "2.000 in / 50.8 mm -- 20 holes at 0.1 in pitch. "
                      "If this does not measure true, your printer scaled the page.", 6.5, GREY)
    footer(c, 5)


def main():
    c = canvas.Canvas(PDF, pagesize=letter)
    c.setTitle("AS3935 lightning detector -- protoboard layout (rev 2)")
    page_sensor_placement(c)
    page_sensor_wiring(c)
    page_main_placement(c)
    page_main_wiring(c)
    page_build(c)
    c.save()
    print("wrote %s" % PDF)


if __name__ == "__main__":
    main()
