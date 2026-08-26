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
PALE   = HexColor("#f2f2f2")

P = 0.2 * inch          # 2:1 -- one 0.1" hole pitch drawn as 0.2"
COLS, ROWS = 27, 19     # a 5 x 7 cm perf board, landscape

COLOR = {"5v": RED, "3v3": ORANGE, "gnd": BLACK, "spi": BLUE, "irq": GREEN}


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
    items = [("5 V", RED), ("3.3 V", ORANGE), ("GND", BLACK), ("SPI", BLUE), ("IRQ", GREEN)]
    c.setFont("Helvetica", 6)
    for name, col in items:
        c.setStrokeColor(col)
        c.setLineWidth(2.2)
        c.line(x, y + 2, x + 12, y + 2)
        c.setFillColor(BLACK)
        c.drawString(x + 15, y, name)
        x += 15 + c.stringWidth(name, "Helvetica", 6) + 12


def footer(c, page, of):
    c.setFont("Helvetica", 7)
    c.setFillColor(GREY)
    c.drawString(M, 0.42 * inch, "AS3935 lightning detector -- protoboard layout, hardware rev 2. "
                                 "Generated by make-protoboard-layout.py; see README section 7.5.")
    c.drawRightString(W - M, 0.42 * inch, "page %d of %d" % (page, of))
    c.showPage()


# --------------------------------------------------------------- board data

# --- sensor board --------------------------------------------------------
S_ENTRY = [                      # RJ45 pigtail landings: (hole, pin, colour, net)
    ((2, 3),  "1", "wh/org",  "5 V",   "5v"),
    ((2, 5),  "3", "wh/grn",  "SCLK",  "spi"),
    ((2, 6),  "4", "blue",    "MOSI",  "spi"),
    ((2, 7),  "5", "wh/blu",  "MISO",  "spi"),
    ((2, 8),  "7", "wh/brn",  "CS",    "spi"),
    ((2, 9),  "8", "brown",   "IRQ",   "irq"),
    ((2, 12), "2", "orange",  "GND",   "gnd"),
    ((3, 12), "6", "green",   "GND",   "gnd"),
]

S_HDR = [                        # SEN-39003 header, col 17, top to bottom
    ((17, 3),  "IRQ", "irq"),
    ((17, 4),  "SI",  "gnd"),
    ((17, 5),  "CS",  "spi"),
    ((17, 6),  "SCK", "spi"),
    ((17, 7),  "MISO", "spi"),
    ((17, 8),  "MOSI", "spi"),
    ((17, 9),  "GND", "gnd"),
    ((17, 10), "VCC", "3v3"),
]

S_WIRES = [
    ("W-S1", "5 V in",     (2, 3),  (4, 10),  "5v",  "red 24 AWG"),
    ("W-S2", "LDO GND",    (12, 10), (12, 12), "gnd", "black 24 AWG"),
    ("W-S3", "SG-PG tie",  (13, 9), (13, 12), "gnd", "black 22 AWG -- the ONLY tie"),
    ("W-S4", "SI strap",   (17, 4), (14, 9),  "gnd", "black 26 AWG"),
    ("W-S5", "SCLK",       (2, 5),  (17, 6),  "spi", "26 AWG"),
    ("W-S6", "MOSI",       (2, 6),  (17, 8),  "spi", "26 AWG"),
    ("W-S7", "MISO",       (2, 7),  (17, 7),  "spi", "26 AWG"),
    ("W-S8", "CS",         (2, 8),  (17, 5),  "spi", "26 AWG"),
    ("W-S9", "IRQ",        (2, 9),  (17, 3),  "irq", "26 AWG"),
]

# --- main board ----------------------------------------------------------
# DOIT ESP32 DevKit V1, 30 pin, USB at the bottom. Verify against your board.
M_LEFT = ["VIN", "GND", "D13", "D12", "D14", "D27", "D26", "D25",
          "D33", "D32", "D35", "D34", "VN", "VP", "EN"]
M_RIGHT = ["D23", "D22", "TX0", "RX0", "D21", "D19", "D18", "D5",
           "D17", "D16", "D4", "D2", "D15", "GND", "3V3"]

M_ENTRY = [
    ((21, 6),  "1", "wh/org", "5 V",  "5v"),
    ((21, 10), "3", "wh/grn", "SCLK", "spi"),
    ((21, 4),  "4", "blue",   "MOSI", "spi"),
    ((21, 9),  "5", "wh/blu", "MISO", "spi"),
    ((21, 11), "7", "wh/brn", "CS",   "spi"),
    ((21, 14), "8", "brown",  "IRQ",  "irq"),
    ((17, 17), "2", "orange", "GND",  "gnd"),
    ((17, 16), "6", "green",  "GND",  "gnd"),
]

M_WIRES = [
    ("W-M1",  "C1+ to VIN",    (3, 4),   (6, 4),   "5v",  "red 22 AWG, keep under 10 mm"),
    ("W-M2",  "C1- to GND",    (3, 6),   (6, 5),   "gnd", "black 22 AWG, keep under 10 mm"),
    ("W-M3",  "MOSI stub",     (16, 4),  (17, 4),  "spi", "26 AWG"),
    ("W-M4",  "MISO stub",     (16, 9),  (17, 9),  "spi", "26 AWG"),
    ("W-M5",  "SCLK stub",     (16, 10), (17, 10), "spi", "26 AWG"),
    ("W-M6",  "CS stub",       (16, 11), (17, 11), "spi", "26 AWG"),
    ("W-M7",  "IRQ stub",      (16, 14), (17, 14), "irq", "26 AWG"),
    ("W-M8",  "IRQ to cable",  (17, 14), (21, 14), "irq", "wire link, no resistor"),
    ("W-M9",  "MISO to cable", (17, 9),  (21, 9),  "spi", "wire link, no resistor"),
    ("W-M10", "5 V to cable",  (6, 4),   (21, 6),  "5v",  "red 22 AWG, long run is fine at 1 mA"),
    ("W-M11", "GND to ESP32",  (17, 17), (16, 17), "gnd", "black 22 AWG"),
    ("W-M12", "GND link",      (17, 16), (17, 17), "gnd", "black 22 AWG"),
]


# ------------------------------------------------------------------ pages

def page_sensor_placement(c):
    y = title(c, H - M, "1.  SENSOR BOARD -- component placement",
              "5 x 7 cm perf board, isolated pads, viewed from the component side. "
              "Everything here is SELV: 5 V and SPI only.")
    ox, oy = M + 0.75 * inch, y - 0.30 * inch
    x0, y0, bw, bh = board(c, ox, oy)

    outline(c, ox, oy, 16.6, 2.0, 26.4, 11.0, "M1  SEN-39003 (AS3935)",
            "25 x 23 mm, stands ~11 mm off the board on its header",
            dash=True, tpos="below")
    c.setStrokeColor(RED)
    c.setLineWidth(0.9)
    c.setDash(3, 2)
    c.circle(gx(ox, 23.5), gy(oy, 6.5), 1.35 * P, fill=0, stroke=1)
    c.setDash()
    lbl(c, gx(ox, 23.5), gy(oy, 6.5) + 3, "ANTENNA", 5.5, RED, "c")
    lbl(c, gx(ox, 23.5), gy(oy, 6.5) - 5, "KEEP CLEAR", 5.5, RED, "c")

    outline(c, ox, oy, 4.3, 9.5, 7.7, 10.5, "R1", tpos="above")
    outline(c, ox, oy, 8.5, 9.5, 9.5, 12.5, "C2", tpos="center")
    outline(c, ox, oy, 10.5, 9.3, 13.5, 10.7, "U1", tpos="above")
    outline(c, ox, oy, 14.5, 9.5, 15.5, 12.5, "C3", tpos="center")
    outline(c, ox, oy, 15.6, 8.6, 16.4, 10.4, "C4", tpos="below")

    for hole, pin, wc, net, kind in S_ENTRY:
        pad(c, ox, oy, hole[0], hole[1], COLOR[kind])
    for hole, name, kind in S_HDR:
        pad(c, ox, oy, hole[0], hole[1], COLOR[kind], r=2.6)
        lbl(c, gx(ox, 17) + 6, gy(oy, hole[1]) - 1.8, name, 5, COLOR[kind])
    for h, k in (((4, 10), "5v"), ((8, 10), "5v"), ((9, 10), "5v"), ((9, 12), "gnd"),
                 ((11, 10), "5v"), ((12, 10), "gnd"), ((13, 10), "3v3"),
                 ((15, 10), "3v3"), ((15, 12), "gnd"), ((16, 10), "3v3"), ((16, 9), "gnd")):
        pad(c, ox, oy, h[0], h[1], COLOR[k], r=2.6)

    lbl(c, x0 - 16, gy(oy, 1) - 1.8, "RJ45 pigtail", 5, GREY, "r")
    lbl(c, x0 - 16, gy(oy, 2) - 1.8, "(panel jack)", 5, GREY, "r")
    for hole, pin, wc, net, kind in S_ENTRY:
        if hole == (3, 12):
            continue
        text = "2+6 GND" if hole == (2, 12) else "%s %s" % (pin, net)
        lbl(c, x0 - 16, gy(oy, hole[1]) - 1.8, text, 5, COLOR[kind], "r")

    lbl(c, gx(ox, 2), gy(oy, 14) - 1.8,
        "BUSES -- bare 22 AWG laid across the back of the pads:", 6, BLACK)
    lbl(c, gx(ox, 3), gy(oy, 15) - 1.8, "row 10, cols 8-11    5 V filtered", 5.5, RED)
    lbl(c, gx(ox, 3), gy(oy, 16) - 1.8, "row 10, cols 13-17   3.3 V", 5.5, ORANGE)
    lbl(c, gx(ox, 14), gy(oy, 15) - 1.8, "row 12, cols 2-15    PG  power ground", 5.5, BLACK)
    lbl(c, gx(ox, 14), gy(oy, 16) - 1.8, "row 9,  cols 13-17   SG  sensor ground", 5.5, BLACK)

    c.setStrokeColor(GREY); c.setLineWidth(0.8); c.setDash(2, 2)
    c.rect(gx(ox, 1) - 4, gy(oy, 18) - 4, P + 8, 8, fill=0, stroke=1)
    c.setDash()
    lbl(c, gx(ox, 3), gy(oy, 18) - 1.8,
        "cable tie through (1,18)/(2,18) -- pigtail strain relief", 5.5, GREY)

    legend(c, M, y0 - 26)

    ty = y0 - 46
    parts = [
        ("R1",  "100 ohm 1/4 W metal film",     "(4,10) - (8,10)"),
        ("C2",  "47 uF 50 V, EEU-FR1H470",      "+ (9,10)    - (9,12)"),
        ("U1",  "MCP1700-3302E, TO-92",         "VIN (11,10)  GND (12,10)  VOUT (13,10)"),
        ("C3",  "1 uF X7R, C330C105K5R5TA",     "(15,10) - (15,12)"),
        ("C4",  "100 nF X7R, C320C104K5R5TA",   "(16,10) - (16,9)"),
        ("M1",  "SEN-39003 on an 8-pin header", "(17,3) .. (17,10), soldered direct"),
    ]
    ny = table(c, M, ty, ["Ref", "Part", "Holes"], parts, [34, 150, 190])

    ny -= 14
    notes(c, M, ny, [
        "**Placement rules that are not negotiable**",
        "C4 sits one hole from VCC and one from GND. That tiny loop is the",
        "     entire point of the part; do not move it to make room.",
        "U1 TO-92, flat face toward you and leads down, is 1 VIN, 2 GND,",
        "     3 VOUT. Splay the 0.05 in leads out to 0.1 in.",
        "Nothing at all under the antenna -- no wire, no bus, no standoff --",
        "     and nylon hardware only.",
        "Confirm which end of the SEN-39003 carries the loop antenna before",
        "     you solder it, and point that end away from the power section.",
    ])
    notes(c, M + 272, ny, [
        "**Soldered, not socketed**",
        "The SEN-39003 header goes straight into the perf. Solderless",
        "     contacts on this rail are the prime suspect for the step",
        "     change in README 11.3, and the board is calibrated per unit,",
        "     so it is not a part you swap casually anyway.",
        "",
        "**No board-mount RJ45**",
        "Its pins are not on a 0.1 in grid and will not fit. Panel jack",
        "     plus a pigtail, tied down at (1,18).",
    ])
    footer(c, 1, 5)


def page_sensor_wiring(c):
    y = title(c, H - M, "2.  SENSOR BOARD -- point-to-point wiring",
              "X-ray view from the component side. All of this is on the BACK of the board, "
              "so it mirrors left-right when you flip it over.")
    ox, oy = M + 0.75 * inch, y - 0.30 * inch
    x0, y0, bw, bh = board(c, ox, oy)

    bus(c, ox, oy, 12, 2, 15, BLACK)          # PG
    bus(c, ox, oy, 9, 13, 17, BLACK)          # SG
    bus(c, ox, oy, 10, 8, 11, RED)            # 5 V filtered
    bus(c, ox, oy, 10, 13, 17, ORANGE)        # 3.3 V

    for ref, net, a, b, kind, note in S_WIRES:
        wire(c, ox, oy, a, b, COLOR[kind])

    for hole, pin, wc, net, kind in S_ENTRY:
        pad(c, ox, oy, hole[0], hole[1], COLOR[kind])
    for hole, name, kind in S_HDR:
        pad(c, ox, oy, hole[0], hole[1], COLOR[kind], r=2.6)
        lbl(c, gx(ox, 17) + 6, gy(oy, hole[1]) - 1.8, name, 5, COLOR[kind])
    for h, k in (((4, 10), "5v"), ((8, 10), "5v"), ((9, 10), "5v"), ((9, 12), "gnd"),
                 ((11, 10), "5v"), ((12, 10), "gnd"), ((13, 10), "3v3"),
                 ((15, 10), "3v3"), ((15, 12), "gnd"), ((16, 10), "3v3"),
                 ((16, 9), "gnd"), ((13, 12), "gnd"), ((12, 12), "gnd"), ((14, 9), "gnd")):
        pad(c, ox, oy, h[0], h[1], COLOR[k], r=2.6)

    lbl(c, gx(ox, 2), gy(oy, 12) + 9, "PG bus", 5.5, BLACK)
    lbl(c, gx(ox, 13), gy(oy, 9) + 11, "SG bus", 5.5, BLACK)
    lbl(c, gx(ox, 8), gy(oy, 10) + 9, "5 V filtered", 5.5, RED)
    lbl(c, gx(ox, 15.2), gy(oy, 10) - 11, "3.3 V", 5.5, ORANGE)
    lbl(c, gx(ox, 2), gy(oy, 15) - 1.8,
        "W-S3 is the single tie between the two grounds. Nowhere else.", 6, BLACK)

    legend(c, M, y0 - 26)

    ty = y0 - 46
    rows = [(ref, net, "(%d,%d)" % a, "(%d,%d)" % b, note)
            for ref, net, a, b, kind, note in S_WIRES]
    bl = [("BUS-A", "5 V filtered", "(8,10)", "(11,10)", "bare 22 AWG across pads 8-11"),
          ("BUS-B", "3.3 V",        "(13,10)", "(17,10)", "bare 22 AWG across pads 13-17"),
          ("BUS-C", "PG ground",    "(2,12)", "(15,12)", "bare 22 AWG across pads 2-15"),
          ("BUS-D", "SG ground",    "(13,9)", "(17,9)",  "bare 22 AWG across pads 13-17")]
    ny = table(c, M, ty, ["Ref", "Net", "From", "To", "Wire"], bl + rows,
               [40, 66, 48, 48, 200])

    ny -= 14
    notes(c, M, ny, [
        "**Two grounds, one tie**",
        "PG carries the cable's ground return, the bulk cap and the LDO",
        "     reference. SG carries only the sensor's GND pin, its 100 nF",
        "     and the SI strap. They meet at exactly one place: W-S3.",
        "Bridge them anywhere else and you have wrapped a ground loop",
        "     around the LDO; the 100 nF stops being local and the whole",
        "     point of the split is gone.",
    ])
    notes(c, M + 272, ny, [
        "**How a bus is made on isolated pads**",
        "A length of bare 22 AWG laid across the back of the row and",
        "     soldered to each pad. It does not thread through the holes,",
        "     which leaves every hole free for a component lead too.",
        "",
        "**Wire**",
        "Kynar 26 AWG wire-wrap for signals: stiff, stays put, strips",
        "     clean. 22 AWG solid for the buses and power.",
    ])
    footer(c, 2, 5)


def _esp32(c, ox, oy):
    outline(c, ox, oy, 5.5, 0.85, 16.5, 21.15, "", dash=True, tpos="none")
    for i, name in enumerate(M_LEFT):
        lbl(c, gx(ox, 6) + 6, gy(oy, 4 + i) - 1.8, name, 4.6, GREY)
    for i, name in enumerate(M_RIGHT):
        lbl(c, gx(ox, 16) - 6, gy(oy, 4 + i) - 1.8, name, 4.6, GREY, "r")
    for i in range(15):
        pad(c, ox, oy, 6, 4 + i, LGREY, r=2.4)
        pad(c, ox, oy, 16, 4 + i, LGREY, r=2.4)
    lbl(c, gx(ox, 11), gy(oy, 20.3), "USB  ->  enclosure grommet", 5.5, BLACK, "c")
    lbl(c, gx(ox, 11), gy(oy, 1.9), "PCB antenna end", 5.5, GREY, "c")
    for txt, r, sz, col in (("A1", 8, 7, BLACK), ("ESP32 DevKit", 9, 5.5, GREY),
                            ("30-pin DOIT", 10, 5.5, GREY),
                            ("female headers", 11.6, 5.5, GREY),
                            ("cols 6 and 16,", 12.6, 5.5, GREY),
                            ("rows 4 - 18", 13.6, 5.5, GREY)):
        lbl(c, gx(ox, 1), gy(oy, r) - 1.8, txt, sz, col)


def page_main_placement(c):
    y = title(c, H - M, "3.  MAIN BOARD -- component placement",
              "5 x 7 cm perf board. Contents: the ESP32 dev board, the 5 V bulk cap at its "
              "pins, and the cable pigtail. Nothing else.")
    ox, oy = M + 0.75 * inch, y - 0.30 * inch
    x0, y0, bw, bh = board(c, ox, oy, cap_dy=34)

    _esp32(c, ox, oy)
    outline(c, ox, oy, 2.4, 3.5, 3.6, 6.5, "C1", tpos="above")
    outline(c, ox, oy, 16.6, 3.5, 21.4, 11.5, "R2 / R3 / R4",
            "0.4 in positions: wire link now, 33-100 ohm only if needed",
            dash=True, tpos="below")

    for h, k in (((3, 4), "5v"), ((3, 6), "gnd")):
        pad(c, ox, oy, h[0], h[1], COLOR[k])
    for r, k in ((4, "spi"), (9, "spi"), (10, "spi"), (11, "spi"), (14, "irq")):
        pad(c, ox, oy, 17, r, COLOR[k], r=2.6)
    for hole, pin, wc, net, kind in M_ENTRY:
        pad(c, ox, oy, hole[0], hole[1], COLOR[kind])
    pad(c, ox, oy, 6, 4, RED, r=2.6)
    pad(c, ox, oy, 6, 5, BLACK, r=2.6)
    pad(c, ox, oy, 16, 17, BLACK, r=2.6)

    for hole, pin, wc, net, kind in M_ENTRY:
        x = gx(ox, hole[0]) + 9
        lbl(c, x, gy(oy, hole[1]) - 1.8, "%s %s" % (pin, net), 5.2, COLOR[kind])
    lbl(c, gx(ox, 22), gy(oy, 1) - 1.8, "RJ45 pigtail", 5, GREY)
    lbl(c, gx(ox, 22), gy(oy, 2) - 1.8, "(panel jack)", 5, GREY)

    c.setStrokeColor(GREY); c.setLineWidth(0.8); c.setDash(2, 2)
    c.rect(gx(ox, 25) - 4, gy(oy, 17) - 4, P + 8, 8, fill=0, stroke=1)
    c.setDash()
    lbl(c, gx(ox, 22), gy(oy, 18.6) - 1.8, "cable tie (25,17)/(26,17)", 5.5, GREY)

    legend(c, M, y0 - 52)

    ty = y0 - 72
    parts = [
        ("A1", "ESP32 DevKit, 30-pin DOIT", "female headers: col 6 r4-18, col 16 r4-18"),
        ("C1", "470-1000 uF 16-25 V 105 C", "+ (3,4)    - (3,6)   stripe at (3,6)"),
        ("R2", "SCLK series -- wire link",  "(17,10) - (21,10)"),
        ("R3", "MOSI series -- wire link",  "(17,4) - (21,4)"),
        ("R4", "CS series -- wire link",    "(17,11) - (21,11)"),
    ]
    ny = table(c, M, ty, ["Ref", "Part", "Holes"], parts, [30, 160, 200])

    ny -= 14
    notes(c, M, ny, [
        "**Socket this one, unlike the sensor board**",
        "Dev boards die, and this one sits metres from the antenna, so the",
        "     contact-resistance worry that governs the sensor board does",
        "     not apply. Female headers, and keep BOOT and EN reachable.",
        "",
        "**Verify your dev board before soldering the headers**",
        "The pin names above are a 30-pin DOIT V1 with USB at the bottom.",
        "     A 36-pin board, or a 0.9 in row pitch, changes everything.",
        "     Count the pins and measure the row spacing first, then use",
        "     the dev board itself as the jig so the rows end up parallel.",
    ])
    notes(c, M + 272, ny, [
        "**R2/R3/R4 are wire links on day one**",
        "Only the three lines the ESP32 drives get a position. MISO and",
        "     IRQ are driven from the far end, so series damping here",
        "     would do nothing. Fit 33-100 ohm only if the 3 m sweep in",
        "     README 16 misbehaves.",
        "",
        "**The overhang goes at the USB end**",
        "The dev board is about 3 mm longer than the perf. Hang that off",
        "     the USB end so the plug clears the board edge.",
    ])
    footer(c, 3, 5)


def page_main_wiring(c):
    y = title(c, H - M, "4.  MAIN BOARD -- point-to-point wiring",
              "X-ray view from the component side. Back-side wires pass under the perf board, "
              "not under the ESP32, so a long run costs nothing.")
    ox, oy = M + 0.75 * inch, y - 0.30 * inch
    x0, y0, bw, bh = board(c, ox, oy, cap_dy=34)
    _esp32(c, ox, oy)

    for ref, net, a, b, kind, note in M_WIRES:
        wire(c, ox, oy, a, b, COLOR[kind])

    for h, k in (((3, 4), "5v"), ((3, 6), "gnd"), ((6, 4), "5v"), ((6, 5), "gnd"),
                 ((16, 17), "gnd")):
        pad(c, ox, oy, h[0], h[1], COLOR[k])
    for r, k in ((4, "spi"), (9, "spi"), (10, "spi"), (11, "spi"), (14, "irq")):
        pad(c, ox, oy, 17, r, COLOR[k], r=2.6)
    for hole, pin, wc, net, kind in M_ENTRY:
        pad(c, ox, oy, hole[0], hole[1], COLOR[kind])
        x = gx(ox, hole[0]) + 9
        lbl(c, x, gy(oy, hole[1]) - 1.8, "%s %s" % (pin, net), 5.2, COLOR[kind])

    legend(c, M, y0 - 52)

    ty = y0 - 72
    rows = [(ref, net, "(%d,%d)" % a, "(%d,%d)" % b, note)
            for ref, net, a, b, kind, note in M_WIRES]
    ny = table(c, M, ty, ["Ref", "Net", "From", "To", "Wire"], rows,
               [40, 72, 48, 48, 210])

    ny -= 14
    notes(c, M, ny, [
        "**C1 is the reason this board exists**",
        "470-1000 uF, 105 C, on the VIN and GND pins with under 10 mm of",
        "     wire either side. It is the reservoir the USB cable cannot",
        "     supply fast enough during a WiFi burst -- README 7.4.",
        "     Watch the polarity: the stripe is the minus lead, at (3,6).",
    ])
    notes(c, M + 272, ny, [
        "**Cable pigtail**",
        "Same T568B assignment as README 7.1. Only the two grounds move:",
        "     they land at (17,16) and (17,17) so they reach the ESP32's",
        "     right-hand GND pin in one hop.",
        "The 5 V wire is the one long run, VIN (6,4) across to (21,6). It",
        "     feeds well under a milliamp, so its length costs nothing.",
        "**Route the USB cable away from the Cat5.** Do not bundle them.",
    ])
    footer(c, 4, 5)


def page_build(c):
    y = title(c, H - M, "5.  Build order, and the things that will bite",
              "Read this before you cut anything. Sections refer to the project README.")

    col1 = M
    col2 = M + 3.6 * inch
    yy = y

    c.setFont("Helvetica-Bold", 9); c.setFillColor(BLACK)
    c.drawString(col1, yy, "Sensor board")
    yy -= 14
    yy = notes(c, col1, yy, [
        "1.  Cut/snap the perf to 27 x 19 holes and de-burr. Mark hole (1,1)",
        "      in the corner with a pen; every coordinate here counts from it.",
        "2.  Solder the four bus wires first, while the board is still flat and",
        "      empty: PG (row 12, cols 2-15), SG (row 9, cols 13-17),",
        "      5 V filt (row 10, cols 8-11), 3.3 V (row 10, cols 13-17).",
        "3.  R1, then C2, then U1, then C3, then C4. Shortest parts first.",
        "4.  W-S3, the single SG-PG tie. Do it deliberately and mark it.",
        "5.  Solder the 8-pin header to the SEN-39003, then solder that",
        "      assembly into (17,3)..(17,10). Check the antenna end points",
        "      right, away from the power section, before you commit.",
        "6.  W-S4, the SI strap. Without it the part talks I2C and nothing",
        "      works -- README 5.",
        "7.  The five signal wires and the pigtail. Cable tie at (1,18).",
        "8.  Before power: ohmmeter from 3.3 V to either ground. Anything",
        "      under a few hundred ohms means a bridge; find it now.",
    ], size=7)

    yy -= 8
    c.setFont("Helvetica-Bold", 9); c.setFillColor(BLACK)
    c.drawString(col1, yy, "Main board")
    yy -= 14
    yy = notes(c, col1, yy, [
        "1.  Count your dev board's pins and measure its header row spacing.",
        "      Only then solder the female headers, using the dev board",
        "      itself as the jig so the rows end up parallel.",
        "2.  C1 with the stripe at (3,6), then W-M1 and W-M2. Short.",
        "3.  Stubs, links and the pigtail. Cable tie at (25,17).",
        "4.  Power it with no ESP32 fitted and confirm 5 V appears at the",
        "      cable's pin 1 and nowhere it should not.",
    ], size=7)

    yy2 = y
    c.setFont("Helvetica-Bold", 9); c.setFillColor(BLACK)
    c.drawString(col2, yy2, "Things that will bite")
    yy2 -= 14
    yy2 = notes(c, col2, yy2, [
        "**The X-ray thing.**  Both wiring pages are drawn as if you could",
        "see through the board from the top, because that is how you place",
        "parts. When you flip the board to solder, left and right swap.",
        "Getting this wrong is the single most common perf-board error.",
        "",
        "**Isolated pads, not strips.**  If what you actually have is",
        "stripboard, every one of these rows is already a bus and the",
        "layout is wrong -- you would need track cuts. Check before you buy.",
        "",
        "**RJ45 on 0.1 in perf.**  It does not fit; the pins are staggered",
        "off-grid. Panel jack and pigtail, both boards.",
        "",
        "**This jack is not Ethernet.**  It carries 5 V and SPI. A live PoE",
        "port puts 48 V on those lines and destroys both ends. Label both",
        "boxes now, while you are holding them -- README 7.1.",
        "",
        "**Nylon standoffs, nylon screws**, on the sensor board especially.",
        "A steel screw near a 500 kHz loop antenna is a shorted turn.",
        "",
        "**Rigidity is a measurement, not a feeling.**  README 11.3: the",
        "breadboard's noise floor fell by two thirds the moment the build",
        "was handled. The Phase 2 test in README 15 is survey, handle the",
        "box, survey again. If the rates move, the build is furniture and",
        "nothing measured on it means anything.",
        "",
        "**Then set data_rate: 200kHz** in lightning-detector.yaml before",
        "the first survey -- it defaults to 1 MHz, README 7.1.",
    ], size=7)

    # scale reference strip
    c.setStrokeColor(GREY); c.setLineWidth(0.8)
    yb = 1.05 * inch
    c.line(M, yb, M + 2 * inch, yb)
    for i in range(21):
        c.line(M + i * 0.1 * inch, yb, M + i * 0.1 * inch, yb + (5 if i % 5 else 8))
    lbl(c, M, yb - 9, "2.000 in / 50.8 mm -- 20 holes at 0.1 in pitch. "
                      "If this does not measure true, your printer scaled the page.", 6.5, GREY)
    footer(c, 5, 5)


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
