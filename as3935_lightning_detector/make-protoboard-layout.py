#!/usr/bin/env python3
"""
Generate as3935-protoboard-layout.pdf -- component placement and point-to-point
wiring plans for the rev 2 build (README section 16) on 0.1" perforated
protoboard with isolated pads.

Companion to make-wiring-diagram.py, which draws the schematic-level
interconnect. This one answers "where does each part physically go".

Regenerate with:   python3 make-protoboard-layout.py
"""

import math
from pathlib import Path

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
COLS, ROWS = 27, 17     # main board: unlettered perf, counted (col, row)

# The sensor board is a "1-18 x A-X" board: 24 columns lettered across the
# long side, 18 rows numbered down. Its coordinates are written the way the
# board prints them -- letter, then number -- so nothing has to be counted.
# This assumes all 24 letters A..X are used. If a board skips I (some do, to
# avoid confusion with 1), fix it here and every label follows.
S_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWX"
S_COLS, S_ROWS = len(S_LETTERS), 18


def sl(cc):
    """Sensor-board column number -> its printed letter."""
    return S_LETTERS[cc - 1]


def sh(cc, rr):
    """Sensor-board hole -> its printed name, e.g. (17, 10) -> 'Q10'."""
    return "%s%d" % (sl(cc), rr)

COLOR = {"5v": RED, "3v3": ORANGE, "gnd": BLACK, "spi": BLUE, "irq": GREEN,
         "nc": GREY}

PAGES = 5


def drawing_version():
    """The shared date stamp printed in both drawing sets' footers.

    Kept in a file rather than in either script so the wiring diagram and the
    protoboard layout cannot drift apart silently. A date, not a revision
    number -- every page already carries the HARDWARE revision. See
    DRAWING-VERSION.
    """
    path = Path(__file__).resolve().parent / "DRAWING-VERSION"
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    raise SystemExit("DRAWING-VERSION contains no version line")


VERSION = drawing_version()


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


def board(c, ox, oy, cols=COLS, rows=ROWS, cap_dy=11, letters=None, rows_up=False):
    """Draw the perf board outline, the hole grid and the col/row rulers.

    letters: the board's printed column letters, if it has them. Then every
    column and row is labelled, as printed, instead of every other number.
    rows_up: the board numbers its rows from the BOTTOM, so the drawing's top
    row carries the highest number.
    """
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
        if letters:
            c.drawCentredString(gx(ox, cc), y0 + bh + 3, letters[cc - 1])
        elif cc % 2 == 1:
            c.drawCentredString(gx(ox, cc), y0 + bh + 3, str(cc))
    for rr in range(1, rows + 1):
        if letters or rr % 2 == 1:
            c.drawRightString(x0 - 3, gy(oy, rr) - 1.8,
                              str(rows + 1 - rr if rows_up else rr))

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


def route(c, ox, oy, pts, col=BLUE, wd=1.3, alpha=0.85, dash=False):
    """A wire through two or more holes. dash=True marks the component side."""
    c.setStrokeColor(col)
    c.setLineWidth(wd)
    c.setStrokeAlpha(alpha)
    if dash:
        c.setDash(3, 2)
    p = c.beginPath()
    p.moveTo(gx(ox, pts[0][0]), gy(oy, pts[0][1]))
    for cc, rr in pts[1:]:
        p.lineTo(gx(ox, cc), gy(oy, rr))
    c.drawPath(p, stroke=1, fill=0)
    c.setDash()
    c.setStrokeAlpha(1)


def rbody(c, ox, oy, cc, r0, r1, col=BLUE, dash=False):
    """A resistor lying along column cc, leads to rows r0 and r1."""
    x = gx(ox, cc)
    ya, yb = gy(oy, r0 + 0.8), gy(oy, r1 - 0.8)
    c.setStrokeColor(col)
    c.setLineWidth(1.1)
    if dash:
        c.setDash(2, 1.5)
    c.line(x, gy(oy, r0), x, ya)
    c.line(x, yb, x, gy(oy, r1))
    c.setFillColor(HexColor("#ffffff"))
    c.rect(x - 2.6, yb, 5.2, ya - yb, fill=1, stroke=1)
    c.setDash()


def to92(c, ox, oy, cc, rr, name, pins):
    """A TO-92 seen from above: a round body with one side cut flat.

    Leads down column cc, middle lead at drawing row rr, flat face toward +x.
    Body radius 2.4 mm with the flat 1.4 mm off centre, which is the real
    shape. pins: names top to bottom, labelled just past the flat face.
    """
    R, d = 0.945 * P, 0.55 * P
    cx, cy = gx(ox, cc), gy(oy, rr)
    h = math.sqrt(R * R - d * d)
    th = math.degrees(math.atan2(h, d))
    c.setStrokeColor(GREY)
    c.setLineWidth(0.9)
    c.setFillColorRGB(0.35, 0.45, 0.60, alpha=0.14)
    p = c.beginPath()
    p.moveTo(cx + d, cy - h)
    p.lineTo(cx + d, cy + h)
    p.arcTo(cx - R, cy - R, cx + R, cy + R, startAng=th, extent=360 - 2 * th)
    p.close()
    c.drawPath(p, fill=1, stroke=1)
    c.setFillColor(HexColor("#33425c"))
    c.setFont("Helvetica-Bold", 6.5)
    c.drawCentredString(cx - 0.55 * P, cy + 3.5, name)
    for i, pn in enumerate(pins):
        lbl(c, cx + d + 1.6, gy(oy, rr - 1 + i) - 1.5, pn, 4.2, GREY)


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
    c.drawString(M, 0.42 * inch, "Protoboard layout, hardware rev 2 -- README 7.5.")
    c.drawRightString(W - M, 0.42 * inch, "page %d of %d" % (page, PAGES))
    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(BLACK)
    c.drawCentredString(W / 2, 0.42 * inch, "DRAWING SET DATED " + VERSION)
    c.showPage()


# --------------------------------------------------------------- board data
#
# On both boards the RJ45 breakout's own right-angle header solders straight
# into one run of NINE holes, so the breakout stands on edge with the jack
# facing off the board. Pin numbers are the numbers silkscreened on the
# breakout, the only labelling that is unambiguous -- see page 4 of
# as3935-node-wiring.pdf.

# --- sensor board --------------------------------------------------------
# Printed coordinates. Seen from the component side the board reads A1 at the
# BOTTOM left and X18 at the top right, so row 18 is the drawing's top row.
# Everything below is in the board's own terms; V() turns a hole into drawing
# rows at the last moment.
#
# J2, the RJ45 breakout, solders its right-angle header into column A and
# stands on edge, the jack facing off the A edge. Header down, looking into the
# jack, the pins read SH 8 7 ... 1 left to right -- and seen from the west,
# left is up the board, so SH is the top pin. Columns B-D behind it cannot be
# reached from the top once it is in, so nothing is placed there.
S_ENTRY = [
    ((1, 16), "SH", "", "shield", "nc"),
    ((1, 15), "8",  "", "IRQ",    "irq"),
    ((1, 14), "7",  "", "CS",     "spi"),
    ((1, 13), "6",  "", "GND",    "gnd"),
    ((1, 12), "5",  "", "MISO",   "spi"),
    ((1, 11), "4",  "", "MOSI",   "spi"),
    ((1, 10), "3",  "", "SCLK",   "spi"),
    ((1, 9),  "2",  "", "GND",    "gnd"),
    ((1, 8),  "1",  "", "5 V",    "5v"),
]
S_OBSCURED = (2, 4)      # columns B-D, behind J2

# M1, the SEN-39003, on its 8-pin header in column S: the nearest column that
# puts the loop antenna past the X edge, clear of every pad. Pin order as
# confirmed on the part -- antenna right, header left, top to bottom.
S_HDR = [
    ((19, 17), "VDD",  "3v3"),
    ((19, 16), "GND",  "gnd"),
    ((19, 15), "CS",   "spi"),
    ((19, 14), "SI",   "gnd"),
    ((19, 13), "IRQ",  "irq"),
    ((19, 12), "SCK",  "spi"),
    ((19, 11), "MISO", "spi"),
    ((19, 10), "MOSI", "spi"),
]

# U1, the MCP1700, is a TO-92: flat front, round back. Flat face toward you,
# leads down, its pins read GND, VIN, VOUT left to right -- NOT the 78xx
# order, and VIN is the MIDDLE pin, so a bus along a row cannot reach it past
# GND. It therefore stands with its leads down column M and its flat face
# toward C3 (east): GND drops straight into PG at M16, VOUT sits on BUS-B at
# M18, and only VIN needs a wire -- W-S4, from the end of BUS-A. L18 stays
# empty: the gap that isolates the input bus from the output bus.
U1_COL, U1_ROWS = 13, {"GND": 16, "VIN": 17, "VOUT": 18}

S_BUSES = [(ref, net, r, c0, c1, kind, "row %d, %s-%s" % (r, sl(c0), sl(c1)))
           for ref, net, r, c0, c1, kind in (
    ("BUS-A", "5 V filtered",      18, 8, 11,  "5v"),
    ("BUS-B", "3.3 V",             18, 13, 18, "3v3"),
    ("BUS-C", "PG  power ground",  16, 6, 15,  "gnd"),
    ("BUS-D", "SG  sensor ground", 16, 17, 18, "gnd"),
)]

S_WIRES = [
    ("W-S1",  "5 V in",     (1, 8),   (5, 18),  "5v",  "J2 pin 1 into R1"),
    ("W-S2",  "GND pin 2",  (1, 9),   (7, 16),  "gnd", "onto PG"),
    ("W-S3",  "GND pin 6",  (1, 13),  (6, 16),  "gnd", "onto PG -- the SCLK return"),
    ("W-S4",  "LDO VIN",    (11, 18), (13, 17), "5v",  "BUS-A into U1 VIN, past L17-L18"),
    ("W-S5",  "3.3 V",      (18, 18), (18, 17), "3v3", "BUS-B down to the C4 / VDD node"),
    ("W-S6",  "VDD link",   (18, 17), (19, 17), "3v3", "one hole -- do not lengthen"),
    ("W-S7",  "GND link",   (19, 16), (18, 16), "gnd", "sensor GND onto SG"),
    ("W-S8",  "SI strap",   (19, 14), (17, 16), "gnd", "grounds SI: selects SPI, not I2C"),
    ("W-S9",  "SG-PG tie",  (15, 16), (17, 16), "gnd", "the ONLY tie -- over P16"),
    ("W-S10", "SCLK",       (1, 10),  (19, 12), "spi", ""),
    ("W-S11", "MOSI",       (1, 11),  (19, 10), "spi", ""),
    ("W-S12", "MISO",       (1, 12),  (19, 11), "spi", ""),
    ("W-S13", "CS",         (1, 14),  (19, 15), "spi", ""),
    ("W-S14", "IRQ",        (1, 15),  (19, 13), "irq", ""),
]

S_PARTS = [
    ("J2", "RJ45 breakout, 9-way header",  "%s .. %s, SH at %s, jack off the A edge"
                                           % (sh(1, 8), sh(1, 16), sh(1, 16))),
    ("R1", "100 ohm 1/4 W metal film",     "%s - %s" % (sh(5, 18), sh(8, 18))),
    ("C2", "47 uF 50 V, EEU-FR1H470",      "+ %s   - %s" % (sh(10, 18), sh(10, 16))),
    ("U1", "MCP1700-3302E, TO-92",         "GND %s  VIN %s  VOUT %s"
                                           % (sh(13, 16), sh(13, 17), sh(13, 18))),
    ("C3", "1 uF X7R, C330C105K5R5TA",     "+ %s   - %s" % (sh(15, 18), sh(15, 16))),
    ("C4", "100 nF X7R, C320C104K5R5TA",   "+ %s   - %s" % (sh(18, 17), sh(18, 16))),
    ("M1", "SEN-39003 on an 8-pin header", "%s .. %s, soldered direct"
                                           % (sh(19, 10), sh(19, 17))),
]

# every other hole in use, drawn solid: (hole, net)
S_PADS = [((5, 18), "5v"), ((8, 18), "5v"), ((10, 18), "5v"), ((11, 18), "5v"),
          ((13, 17), "5v"), ((13, 18), "3v3"), ((15, 18), "3v3"), ((18, 18), "3v3"),
          ((18, 17), "3v3"), ((6, 16), "gnd"), ((7, 16), "gnd"), ((10, 16), "gnd"),
          ((13, 16), "gnd"), ((15, 16), "gnd"), ((17, 16), "gnd"), ((18, 16), "gnd")]


def V(h):
    """Sensor hole (col, printed row) -> drawing (col, row)."""
    return (h[0], S_ROWS + 1 - h[1])


def vr(r):
    """Printed sensor row -> drawing row. Fractions allowed, for outlines."""
    return S_ROWS + 1 - r

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
M_ROW_JACK = 17          # J1's header, on the board's bottom edge

# J1, the RJ45 breakout, solders its right-angle header straight into the
# bottom row, so it stands on edge and the jack faces off the board. That
# fixes the pin order: header down, looking into the jack, the pins read
# SH 8 7 6 5 4 3 2 1 left to right -- so SH sits at the USB end.
#
# With 17 rows there is no room for a resistor footprint between the two
# headers, so each series resistor is soldered pin to pin on the back between
# an ESP32 pin and the jack pin directly below it. Neither pin order can move,
# so the GPIOs are chosen to fit the jack. At cols 7-15 all three resistor
# lines AND both unresistored signals fall straight down, and cable pin 2
# lands under an ESP32 ground; no other position does as well.
M_ENTRY = [
    ((7, 17),  "SH", "", "shield", "gnd"),
    ((8, 17),  "8",  "", "IRQ",    "irq"),
    ((9, 17),  "7",  "", "CS",     "spi"),
    ((10, 17), "6",  "", "GND",    "gnd"),
    ((11, 17), "5",  "", "MISO",   "spi"),
    ((12, 17), "4",  "", "MOSI",   "spi"),
    ((13, 17), "3",  "", "SCLK",   "spi"),
    ((14, 17), "2",  "", "GND",    "gnd"),
    ((15, 17), "1",  "", "5 V",    "5v"),
]

# the pins this design actually uses: (row, col, net, function)
M_USED = [
    (M_ROW_TOP, 2,  "5v",  "5 V"),
    (M_ROW_TOP, 7,  "gnd", "GND"),
    (M_ROW_BOT, 8,  "irq", "IRQ"),
    (M_ROW_BOT, 9,  "spi", "CS"),
    (M_ROW_BOT, 11, "spi", "MISO"),
    (M_ROW_BOT, 12, "spi", "MOSI"),
    (M_ROW_BOT, 13, "spi", "SCLK"),
    (M_ROW_BOT, 14, "gnd", "GND"),
]

# series terminators, pin to pin on the back: (ref, net, col)
M_RES = [("R2", "SCLK", 13), ("R3", "MOSI", 12), ("R4", "CS", 9)]

# (ref, net, route, kind, note, side). A route is two or more holes; side is
# "back" (the solder side) or "top" (the component side).
M_WIRES = [
    ("W-M1", "C1+ to 5V",    [(3, 3), (2, 4)],     "5v",  "as short as it will go", "back"),
    ("W-M2", "C1- to GND",   [(5, 3), (7, 4)],     "gnd", "as short as it will go", "back"),
    ("W-M3", "IRQ",          [(8, 14), (8, 17)],   "irq", "GPIO4, pin to pin, no resistor", "back"),
    ("W-M4", "MISO",         [(11, 14), (11, 17)], "spi", "GPIO5, pin to pin, no resistor", "back"),
    ("W-M5", "GND, pin 2",   [(14, 14), (14, 17)], "gnd", "solder to (14,15) on the way", "back"),
    ("W-M6", "GND, pin 6",   [(10, 17), (10, 15)], "gnd", "stub to the W-M8 tap", "back"),
    ("W-M7", "shield",       [(7, 17), (7, 15)],   "gnd", "stub to the W-M8 tap", "back"),
    ("W-M8", "ground hop",   [(7, 15), (10, 15), (14, 15)], "gnd",
     "COMPONENT SIDE; tap at (10,15)", "top"),
    ("W-M9", "5 V to cable", [(3, 3), (21, 3), (21, 17), (15, 17)], "5v",
     "via (21,3), (21,17): round the header", "back"),
]

M_PARTS = [
    ("A1", "ESP32-DevKitC V4 (WROOM-32D)", "female headers: row 4 c2-20, row 14 c2-20"),
    ("C1", "470-1000 uF 16-25 V 105 C",    "+ (3,3)   - (5,3)   stripe at (5,3)"),
    ("J1", "RJ45 breakout, 9-way header",  "row 17 c7-15, SH at c7, jack off the edge"),
    ("R2", "SCLK series, 68 ohm 1/4 W",    "(13,14) - (13,17), pin to pin, back"),
    ("R3", "MOSI series, 68 ohm 1/4 W",    "(12,14) - (12,17), pin to pin, back"),
    ("R4", "CS series, 68 ohm 1/4 W",      "(9,14) - (9,17), pin to pin, back"),
]


# ------------------------------------------------------------------ pages

def _sensor_frame(c, ox, oy, x0, placement):
    """What both sensor pages share: the unreachable band behind J2, M1 and
    its overhanging antenna, and the pin labels on both headers."""
    ink = HexColor("#33425c")
    b0, b1 = S_OBSCURED
    xa, xb = gx(ox, b0 - 0.45), gx(ox, b1 + 0.45)
    ya, yb = gy(oy, vr(18.2)), gy(oy, vr(4.9))
    c.setStrokeColor(GREY)
    c.setLineWidth(0.8)
    c.setDash(2, 2)
    c.setFillColorRGB(0.45, 0.45, 0.45, alpha=0.16)
    c.rect(xa, yb, xb - xa, ya - yb, fill=1, stroke=1)
    c.setDash()
    lbl(c, gx(ox, 1.6), gy(oy, vr(4.3)) - 1.8,
        "B-D: behind J2 -- no access from the top", 5.2, GREY)

    outline(c, ox, oy, 18.5, vr(18.2), 28.3, vr(8.8), "M1  SEN-39003 (AS3935)",
            "about 25 x 24 mm on its 8-pin header" if placement else None,
            dash=True, tpos="below")
    c.setStrokeColor(RED)
    c.setLineWidth(0.9)
    c.setDash(3, 2)
    c.circle(gx(ox, 26.4), gy(oy, vr(13.5)), 1.35 * P, fill=0, stroke=1)
    c.setDash()
    lbl(c, gx(ox, 26.4), gy(oy, vr(13.5)) + 3, "ANTENNA", 5.5, RED, "c")
    lbl(c, gx(ox, 26.4), gy(oy, vr(13.5)) - 5, "off the board", 5.5, RED, "c")

    lbl(c, x0 - 12, gy(oy, vr(17.7)) - 1.8, "J2  RJ45 breakout", 5.5, ink, "r")
    lbl(c, x0 - 12, gy(oy, vr(17.1)) - 1.8, "standing on edge", 5.5, GREY, "r")
    for hole, pin, wc, net, kind in S_ENTRY:
        lbl(c, x0 - 12, gy(oy, V(hole)[1]) - 1.8, "%s  %s" % (pin, net), 5,
            COLOR[kind], "r")
    for hole, name, kind in S_HDR:
        cc, rr = V(hole)
        lbl(c, gx(ox, cc) + 6, gy(oy, rr) - 1.8, name, 5, COLOR[kind])


def _sensor_pads(c, ox, oy):
    for hole, pin, wc, net, kind in S_ENTRY:
        pad(c, ox, oy, *V(hole), col=COLOR[kind])
    for hole, name, kind in S_HDR:
        pad(c, ox, oy, *V(hole), col=COLOR[kind], r=2.6)
    for h, k in S_PADS:
        pad(c, ox, oy, *V(h), col=COLOR[k], r=2.6)


def page_sensor_placement(c):
    y = title(c, H - M, "1.  SENSOR BOARD -- component placement",
              "1-18 x A-X perf board, A1 at the bottom left, seen from the component side. "
              "SELV only: 5 V and SPI.")
    ox, oy = M + 1.05 * inch, y - 0.30 * inch
    x0, y0, bw, bh = board(c, ox, oy, S_COLS, S_ROWS, letters=S_LETTERS, rows_up=True)
    ink = HexColor("#33425c")
    _sensor_frame(c, ox, oy, x0, placement=True)

    outline(c, ox, oy, 5.26, vr(18.45), 7.74, vr(17.55), "R1", tpos="below")
    cx, cy = gx(ox, 10), gy(oy, vr(17))          # C2 is a can: round from above
    c.setStrokeColor(GREY)
    c.setLineWidth(0.9)
    c.setDash(2, 2)
    c.setFillColorRGB(0.35, 0.45, 0.60, alpha=0.10)
    c.circle(cx, cy, 1.575 * P, fill=1, stroke=1)
    c.setDash()
    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawCentredString(cx, cy - 2.3, "C2")
    to92(c, ox, oy, U1_COL, vr(U1_ROWS["VIN"]), "U1", ["VOUT", "VIN", "GND"])
    outline(c, ox, oy, 14.35, vr(18), 15.65, vr(16), "C3", tpos="center")
    outline(c, ox, oy, 17.5, vr(17.25), 18.5, vr(15.75), "C4", tpos="below")
    _sensor_pads(c, ox, oy)

    ay = gy(oy, vr(2.8))
    c.setStrokeColor(ink)
    c.setLineWidth(1.1)
    c.line(gx(ox, 1.4), ay, x0 - 10, ay)
    p = c.beginPath()
    p.moveTo(x0 - 6, ay + 3)
    p.lineTo(x0 - 10, ay)
    p.lineTo(x0 - 6, ay - 3)
    c.drawPath(p, stroke=1, fill=0)
    lbl(c, gx(ox, 1.8), ay - 1.8,
        "J2's jack faces off the A edge, out through the box wall", 5.5, ink)
    lbl(c, gx(ox, 6), gy(oy, vr(6.2)) - 1.8,
        "Rows 1-7 are free: room for the nylon standoffs.", 5.5, GREY)
    lbl(c, gx(ox, 19.6), gy(oy, vr(9.4)) - 1.8, "keep T-X under M1 empty", 5.2, RED)

    legend(c, M, y0 - 26)

    ny = table(c, M, y0 - 46, ["Ref", "Part", "Holes"], S_PARTS, [34, 150, 190])

    ny -= 14
    notes(c, M, ny, [
        "**The antenna overhangs the X edge, on purpose**",
        "With M1's header in column S its loop antenna sits past the X",
        "     edge, clear of every pad on the board. Keep T-X under M1",
        "     empty, and keep the box wall and its screws clear of it.",
        "",
        "**C4 sits one hole from VDD and one from GND**",
        "     That tiny loop is the entire point of the part; do not move",
        "     it to make room. It is right at M1's edge: keep it low.",
        "",
        "**U1, TO-92: GND, VIN, VOUT** left to right, flat face toward",
        "     you and leads down -- not the 78xx order. It stands in column",
        "     M, flat face toward C3: GND M16 (on PG), VIN M17, VOUT M18",
        "     (on BUS-B). L18 stays empty: the isolation gap.",
    ])
    notes(c, M + 272, ny, [
        "**J2 stands on edge in column A**",
        "Its right-angle header goes straight into A8-A16, the jack",
        "     facing off the A edge. Header down, the pins read SH at the",
        "     top to pin 1 at the bottom. B-D behind it are out of reach",
        "     from the top, so nothing is placed there -- wires cross",
        "     them on the back. The wall, not the header, takes plug force.",
        "",
        "**M1 header order, confirmed on the part**",
        "Antenna right, header left, top to bottom: VDD, GND, CS, SI,",
        "     IRQ, SCK, MISO, MOSI. Soldered straight in, no socket:",
        "     solderless contacts here are the README 11.3 suspect.",
    ])
    footer(c, 1)


def page_sensor_wiring(c):
    y = title(c, H - M, "2.  SENSOR BOARD -- point-to-point wiring",
              "X-ray view from the component side. All of this is on the BACK of the board, "
              "so it mirrors left-right when you flip it over.")
    ox, oy = M + 1.05 * inch, y - 0.30 * inch
    x0, y0, bw, bh = board(c, ox, oy, S_COLS, S_ROWS, letters=S_LETTERS, rows_up=True)
    _sensor_frame(c, ox, oy, x0, placement=False)

    for ref, net, r, c0, c1, kind, where in S_BUSES:
        bus(c, ox, oy, vr(r), c0, c1, COLOR[kind])
    for ref, net, a, b, kind, note in S_WIRES:
        wire(c, ox, oy, V(a), V(b), COLOR[kind])
    _sensor_pads(c, ox, oy)

    lbl(c, gx(ox, 8.2), gy(oy, vr(17.3)) - 1.8, "BUS-A  5 V", 5.2, RED)
    lbl(c, gx(ox, 14.2), gy(oy, vr(17.3)) - 1.8, "BUS-B  3.3 V", 5.2, ORANGE)
    lbl(c, gx(ox, 8.2), gy(oy, vr(15.3)) - 1.8, "BUS-C  PG", 5.2, BLACK)
    lbl(c, gx(ox, 16.8), gy(oy, vr(16.45)) - 1.8, "SG", 5.2, BLACK)
    lbl(c, gx(ox, 15.0), gy(oy, vr(15.45)) - 1.8, "W-S9", 5.2, BLACK)

    legend(c, M, y0 - 26)

    rows = [(ref, net, sh(*a), sh(*b), note)
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
        "     and the SI strap. They meet at exactly one place: W-S9,",
        "     over the empty P16.",
        "Bridge them anywhere else and you have wrapped a ground loop",
        "     around the LDO; the 100 nF stops being local and the whole",
        "     point of the split is gone.",
    ])
    notes(c, M + 272, ny, [
        "**C3 references PG, C4 references SG**",
        "C3 is the MCP1700's stability capacitor, so it belongs to the",
        "     regulator and lands on PG. C4 is the sensor's decoupling, so",
        "     it belongs to the sensor and lands on SG.",
        "",
        "**Crossings are fine, except over a bus**",
        "Point-to-point links are insulated and run on the solder side;",
        "     they cross each other freely -- the SPI links all run in",
        "     rows 10-15, below every bus. The four buses are BARE.",
    ])
    footer(c, 2)


def _esp32(c, ox, oy):
    """The dev board, lying lengthwise with the USB end off the left edge."""
    outline(c, ox, oy, 0.55, M_ROW_TOP - 0.55, 21.0, M_ROW_BOT + 0.55, "",
            dash=True, tpos="none")
    used = {(r, cc): (kind, what) for r, cc, kind, what in M_USED}
    for row, names, dy in ((M_ROW_TOP, M_TOP, -24), (M_ROW_BOT, M_BOT, 6)):
        for i, name in enumerate(names):
            cc = M_COL0 + i
            u = used.get((row, cc))
            if u:
                pad(c, ox, oy, cc, row, COLOR[u[0]], r=2.9)
                text = name if row == M_ROW_TOP or name == u[1] else "%s %s" % (name, u[1])
                vlbl(c, gx(ox, cc), gy(oy, row) + dy, text, 4.8, COLOR[u[0]])
            else:
                pad(c, ox, oy, cc, row, LGREY, r=2.4)
                vlbl(c, gx(ox, cc), gy(oy, row) + dy, name)

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
    lbl(c, gx(ox, 17), gy(oy, 11.8) - 1.8, "PCB antenna end", 5.5, GREY)


def _entry_below(c, ox, oy, entries):
    """J1's pin labels in the margin below the board, reading upward."""
    for hole, pin, wc, net, kind in entries:
        vrlbl(c, gx(ox, hole[0]) + 1.8, gy(oy, hole[1]) - P / 2 - 3,
              "%s  %s" % (pin, net), 5.0, COLOR[kind])


def _breakout(c, ox, oy, label=True):
    """J1 standing on edge: where its PCB stands, and which way the jack faces.

    The PCB stands about one hole inboard of its pins. Its ends are taken off
    the vendor drawing -- 5.6 mm past SH, 8.0 mm past pin 1 -- so treat them
    as approximate.
    """
    ink = HexColor("#33425c")
    x0, x1 = gx(ox, 4.8), gx(ox, 18.1)
    ya, yb = gy(oy, 15.8), gy(oy, 16.2)
    c.setStrokeColor(GREY)
    c.setLineWidth(0.9)
    c.setDash(2, 2)
    c.setFillColorRGB(0.35, 0.45, 0.60, alpha=0.22)
    c.rect(x0, yb, x1 - x0, ya - yb, fill=1, stroke=1)
    c.setDash()
    ax, a0, a1 = gx(ox, 19.6), gy(oy, 17.0), gy(oy, 18.9)
    c.setStrokeColor(ink)
    c.setLineWidth(1.1)
    c.line(ax, a0, ax, a1)
    p = c.beginPath()
    p.moveTo(ax - 3, a1 + 4)
    p.lineTo(ax, a1)
    p.lineTo(ax + 3, a1 + 4)
    c.drawPath(p, stroke=1, fill=0)
    lbl(c, ax + 5, a1 + 1, "the jack faces off this edge", 5.5, ink)
    if label:
        lbl(c, gx(ox, 18.4), gy(oy, 16) - 1.8, "J1 stands here, on edge", 5.2, ink)


def page_main_placement(c):
    y = title(c, H - M, "3.  MAIN BOARD -- component placement",
              "Contents: the ESP32 dev board, the 5 V bulk cap at its pins, three series "
              "terminators, and J1, the RJ45 breakout.")
    ox, oy = M + 0.75 * inch, y - 0.30 * inch
    x0, y0, bw, bh = board(c, ox, oy, cap_dy=46)

    _esp32(c, ox, oy)
    outline(c, ox, oy, 2.4, 1.6, 5.6, 3.4, "C1", tpos="above")
    lbl(c, gx(ox, 8), gy(oy, 2) - 1.8, "body overhangs the top edge", 5.5, GREY)
    _breakout(c, ox, oy)
    for ref, net, cc in M_RES:
        rbody(c, ox, oy, cc, M_ROW_BOT, M_ROW_JACK, BLUE, dash=True)
    for h, k in (((3, 3), "5v"), ((5, 3), "gnd")):
        pad(c, ox, oy, h[0], h[1], COLOR[k])
    for hole, pin, wc, net, kind in M_ENTRY:
        pad(c, ox, oy, hole[0], hole[1], COLOR[kind])
    _entry_below(c, ox, oy, M_ENTRY)
    lbl(c, gx(ox, 15.6), gy(oy, 15) - 1.8, "R4 c9, R3 c12, R2 c13 -- on the back", 5.2, BLUE)

    legend(c, M, y0 - 60)

    ny = table(c, M, y0 - 80, ["Ref", "Part", "Holes"], M_PARTS, [30, 165, 195])

    ny -= 14
    notes(c, M, ny, [
        "**The jack faces off the bottom edge -- that fixes the order**",
        "J1's right-angle header goes straight into row 17, so the",
        "     breakout stands on edge. Header down, looking into the jack,",
        "     the pins read SH 8 7 6 5 4 3 2 1 -- so SH sits at col 7, the",
        "     USB end. Before soldering, check the jack overhangs the edge.",
        "",
        "**The header is the electrical joint, not the mechanical one**",
        "Nine pins in isolated pads will lift under a cable being plugged",
        "     in. The enclosure wall, or a bracket on J1's own mounting",
        "     holes, must take that force. J1 stands about 30 mm tall.",
        "",
        "**Socket the ESP32**, unlike the sensor. Check its row spacing",
        "     (drawn at 10 holes, 1.0 in) and use it as its own jig.",
    ])
    notes(c, M + 272, ny, [
        "**These are not the default SPI pins, on purpose**",
        "Each resistor sits pin to pin between an ESP32 pin and the jack",
        "     pin directly below it, and neither pin order can move. So",
        "     the GPIOs were chosen to line up with the jack:",
        "     SCLK 19, MOSI 18, MISO 5, CS 16, IRQ 4. The ESP32 routes",
        "     SPI to any pin; at these speeds the GPIO matrix costs",
        "     nothing. lightning-detector.yaml matches -- do not 'fix' it.",
        "",
        "**C1 is as tight as the DevKitC allows**",
        "Five pins between 5V and its nearest ground: ~27 mm of loop",
        "     however you arrange it. Keep W-M1 and W-M2 short.",
    ])
    footer(c, 3)


def page_main_wiring(c):
    y = title(c, H - M, "4.  MAIN BOARD -- point-to-point wiring",
              "X-ray view from the component side. Solid lines are on the BACK; the one "
              "dashed line, W-M8, is on the component side.")
    ox, oy = M + 0.75 * inch, y - 0.30 * inch
    x0, y0, bw, bh = board(c, ox, oy, cap_dy=46)
    _esp32(c, ox, oy)
    _breakout(c, ox, oy, label=False)

    for ref, net, pts, kind, note, side in M_WIRES:
        route(c, ox, oy, pts, COLOR[kind], dash=(side == "top"))
    for ref, net, cc in M_RES:
        rbody(c, ox, oy, cc, M_ROW_BOT, M_ROW_JACK, BLUE)
    for h, k in (((3, 3), "5v"), ((5, 3), "gnd"), ((7, 15), "gnd"),
                 ((10, 15), "gnd"), ((14, 15), "gnd")):
        pad(c, ox, oy, h[0], h[1], COLOR[k], r=2.6)
    for hole, pin, wc, net, kind in M_ENTRY:
        pad(c, ox, oy, hole[0], hole[1], COLOR[kind])
    _entry_below(c, ox, oy, M_ENTRY)

    lbl(c, gx(ox, 2.5), gy(oy, 2) - 1.8, "C1  +", 5.5, RED)
    lbl(c, gx(ox, 4.7), gy(oy, 2) - 1.8, "-", 5.5, BLACK)
    lbl(c, gx(ox, 21.4), gy(oy, 10) - 1.8, "W-M9  5 V", 5.5, RED)
    lbl(c, gx(ox, 6.7), gy(oy, 15) - 1.8, "W-M8", 5.2, BLACK, "r")
    lbl(c, gx(ox, 15.6), gy(oy, 15) - 1.8, "R4 c9, R3 c12, R2 c13", 5.2, BLUE)

    legend(c, M, y0 - 60)

    rows = [(ref, net, "(%d,%d)" % pts[0], "(%d,%d)" % pts[-1], note)
            for ref, net, pts, kind, note, side in M_WIRES]
    rows += [(ref, "%s, 68 ohm" % net, "(%d,%d)" % (cc, M_ROW_BOT),
              "(%d,%d)" % (cc, M_ROW_JACK), "pin to pin on the back")
             for ref, net, cc in M_RES]
    ny = table(c, M, y0 - 80, ["Ref", "Net", "From", "To", "Note"], rows,
               [40, 76, 52, 52, 192])

    ny -= 12
    notes(c, M, ny, [
        "**Everything between the headers is on the back**",
        "Rows 15-16 have no room for a footprint, so the three resistors",
        "     and three straight links solder pin to pin, lying flat on",
        "     the back between the ESP32 joint and the jack joint below.",
        "     Cols 11-14 are four parallel runs 2.54 mm apart: insulated",
        "     wire for the links, short straight leads on the resistors.",
        "",
        "**Why one wire is on the component side**",
        "Those six runs wall off the back of rows 15-16, so pin 6 (col 10)",
        "     and SH (col 7) cannot reach ground at col 14 without crossing",
        "     them. W-M8 hops over the top instead. Fit it BEFORE J1:",
        "     afterwards the breakout stands over row 16 and it is buried.",
    ])
    notes(c, M + 272, ny, [
        "**5 V goes round the end of the header**",
        "W-M9 leaves C1 along row 3, down col 21 and back along row 17.",
        "     Every other way to row 17 passes between two header pins",
        "     whose solder joints are a millimetre apart. It is long; at",
        "     ~1 mA that costs nothing.",
        "",
        "**Three cable grounds, one ESP32 pin**",
        "Pins 2, 6 and SH all meet at the GND beside GPIO19 -- the pin",
        "     next to SCLK, so the SCLK pair (3,6) returns where it should.",
        "     C1 keeps the top-row GND to itself. SH is bonded here and",
        "     nowhere else; at the sensor board it stays floating.",
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
        "1.  The 1-18 x A-X board, A1 at the bottom left as printed. Every",
        "      coordinate is letter then number, as on the board.",
        "2.  Buses first, while the board is flat and empty: PG (row 16,",
        "      F-O), SG (row 16, Q-R), 5 V (row 18, H-L), 3.3 V (row 18, N-R).",
        "3.  R1, C2, U1 (flat face toward C3), C3, C4. Then W-S9, the",
        "      single SG-PG tie: do it deliberately and mark it.",
        "4.  Solder the 8-pin header into the SEN-39003, then that assembly",
        "      into S10..S17, antenna out past the X edge.",
        "5.  J2: header into A8..A16, SH at the top, jack off the A edge.",
        "      Nothing goes in B-D behind it.",
        "6.  On the back: W-S8, the SI strap -- without it the part talks",
        "      I2C and nothing works -- then the power and signal links.",
        "7.  Before power: ohmmeter 3.3 V to either ground. Under a few",
        "      hundred ohms means a bridge -- find it now, not later.",
    ], size=7)

    yy -= 8
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(BLACK)
    c.drawString(col1, yy, "Main board")
    yy -= 14
    yy = notes(c, col1, yy, [
        "1.  Cut the perf to 27 x 17 and mark hole (1,1) with a pen: this",
        "      board is counted, not lettered. Measure the dev board's row",
        "      spacing, then solder the female headers using it as the jig.",
        "2.  C1, stripe at (5,3). Then W-M1 and W-M2, short.",
        "3.  W-M8 on the COMPONENT side, now, while row 15 is reachable:",
        "      insulated, stripped at (7,15), (10,15) and (14,15).",
        "4.  J1: SH at col 7, jack overhanging the bottom edge. Check the",
        "      orientation twice, then solder its header into row 17.",
        "5.  On the back: R2/R3/R4 and W-M3/4/5 pin to pin, then the",
        "      W-M6 and W-M7 stubs up to the W-M8 taps.",
        "6.  W-M9, the 5 V run, round the end of the header via col 21.",
        "7.  Power it with NO ESP32 in the socket: 5 V at J1 pin 1, and",
        "      nowhere it should not be.",
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
        "**Place by the printed label.**  The sensor board reads A1 at",
        "the bottom left and is drawn that way up, but the label printed",
        "beside each hole is still the thing to trust.",
        "",
        "**Isolated pads, not strips.**  If what you have is stripboard,",
        "every row here is already a bus and the layout is wrong without",
        "track cuts. Check before you buy.",
        "",
        "**RJ45 on 0.1 in perf.**  A bare RJ45 jack does not fit; the",
        "breakout's 9-way header does, on both boards, standing on edge",
        "with the jack off the edge. The 3 rows or columns behind it are",
        "then out of reach from the top: fit anything there first.",
        "Wire to the printed numbers, never to a position in a photo.",
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
        "**Keep data_rate: 200kHz** in lightning-detector.yaml. It is",
        "set; the ESPHome default is 1 MHz. README 7.1.",
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
