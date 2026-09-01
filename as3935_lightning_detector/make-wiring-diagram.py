#!/usr/bin/env python3
"""Regenerate as3935-node-wiring.pdf -- the point-to-point wiring set for the
revision 2 hardware (README section 16).

    python3 make-wiring-diagram.py          # needs reportlab

The rev 1 drawing was produced ad hoc with no generator committed, so it could
not be revised when the design changed. This script is the source of truth for
the drawing; edit it, re-run it, commit both.

Every line on the drawings is one physical wire, labelled W-M<n> (main board)
or W-S<n> (sensor board); the wire numbers match the schedule on page 5 and
the hole coordinates in as3935-protoboard-layout.pdf.
"""
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

OUT = "as3935-node-wiring.pdf"
W, H = letter
M = 0.6 * inch

INK      = HexColor("#1a1a1a")
MUTED    = HexColor("#6b6b6b")
RULE     = HexColor("#c8c8c8")
BOXFILL  = HexColor("#f4f4f2")
RED      = HexColor("#b3261e")   # 5 V
ORANGE   = HexColor("#b06000")   # 3.3 V
BLACK_W  = HexColor("#333333")   # ground
BLUE     = HexColor("#1a5fb4")   # SPI
GREEN    = HexColor("#2c6e49")   # IRQ / misc
AMBER    = HexColor("#8a5a00")   # warnings

PAGES = 6
TITLE = "AS3935 lightning detector node - revision 2"

# T568B, and the numbers silkscreened on the RJ45 breakout. SH is the metal
# shell; it is a ninth pin on this breakout and is NOT part of T568B.
PINS = [
    ("1",  "white/orange", "5 V"),
    ("2",  "orange",       "GND"),
    ("3",  "white/green",  "SCLK"),
    ("4",  "blue",         "MOSI"),
    ("5",  "white/blue",   "MISO"),
    ("6",  "green",        "GND"),
    ("7",  "white/brown",  "CS"),
    ("8",  "brown",        "IRQ"),
    ("SH", "(jack shell)", "shield"),
]

# ESP32-DevKitC V4 / ESP32-WROOM-32D, held portrait with the USB at the bottom.
ESP_LEFT = ["3V3", "EN", "VP", "VN", "34", "35", "32", "33", "25", "26",
            "27", "14", "12", "GND", "13", "D2", "D3", "CMD", "5V"]
ESP_RIGHT = ["GND", "23", "22", "TX0", "RX0", "21", "GND", "19", "18", "5",
             "17", "16", "4", "0", "2", "15", "SD1", "SD0", "CLK"]
ESP_USE = {("L", "5V"): ("5 V in / out", RED),
           ("L", "GND"): ("C1 -, cable pin 2", BLACK_W),
           ("R", "23"): ("MOSI", BLUE),
           ("R", "19"): ("MISO", BLUE),
           ("R", "18"): ("SCLK", BLUE),
           ("R", "5"): ("CS", BLUE),
           ("R", "4"): ("IRQ", GREEN)}


# ------------------------------------------------------------------ chrome

def header(c, subtitle, blurb):
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(M, H - M, subtitle)
    c.setFont("Helvetica", 9.5)
    c.setFillColor(MUTED)
    c.drawString(M, H - M - 15, blurb)
    c.drawRightString(W - M, H - M, TITLE)
    c.setStrokeColor(RULE)
    c.setLineWidth(0.7)
    c.line(M, H - M - 24, W - M, H - M - 24)


def footer(c, page):
    c.setStrokeColor(RULE)
    c.setLineWidth(0.7)
    c.line(M, M + 22, W - M, M + 22)
    c.setFont("Helvetica", 7.6)
    c.setFillColor(MUTED)
    c.drawString(M, M + 11,
                 "Print at 100% / actual size. Wire colours are named as well as drawn, "
                 "so the sheet still reads correctly in greyscale.")
    c.drawRightString(W - M, M + 11, "Page %d of %d" % (page, PAGES))


def box(c, x, y, w, h, title, lines=(), fill=BOXFILL, titlesize=10):
    c.setFillColor(fill)
    c.setStrokeColor(INK)
    c.setLineWidth(1.1)
    c.roundRect(x, y, w, h, 5, stroke=1, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", titlesize)
    c.drawString(x + 8, y + h - 15, title)
    c.setFont("Helvetica", 8.3)
    ty = y + h - 28
    for ln in lines:
        c.setFillColor(MUTED if ln.startswith("  ") else INK)
        c.drawString(x + 8, ty, ln.strip() if ln.startswith("  ") else ln)
        ty -= 10.5
    return x, y, w, h


def pinbox(c, x, ytop, w, title, pins, rowh=13, pad=24, right=False, sub=None):
    """Box whose pin labels sit on a fixed grid. Returns [y per row] so wires
    can be drawn perfectly horizontal between two boxes."""
    h = pad + len(pins) * rowh + 8
    y = ytop - h
    c.setFillColor(BOXFILL)
    c.setStrokeColor(INK)
    c.setLineWidth(1.1)
    c.roundRect(x, y, w, h, 5, stroke=1, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + 8, ytop - 16, title)
    if sub:
        c.setFont("Helvetica", 6.6)
        c.setFillColor(MUTED)
        c.drawRightString(x + w - 8, ytop - 16, sub)
    rows = []
    ry = ytop - pad - 8
    for label, colour in pins:
        c.setFillColor(colour)
        c.setFont("Helvetica", 8.3)
        if right:
            c.drawRightString(x + w - 8, ry - 3, label)
        else:
            c.drawString(x + 8, ry - 3, label)
        rows.append(ry)
        ry -= rowh
    return rows, (x, y, w, h)


def dot(c, x, y, colour=INK, r=1.9):
    c.setFillColor(colour)
    c.circle(x, y, r, stroke=0, fill=1)


def opencirc(c, x, y, colour=MUTED, r=2.4):
    c.setStrokeColor(colour)
    c.setLineWidth(1.1)
    c.setFillColor(HexColor("#ffffff"))
    c.circle(x, y, r, stroke=1, fill=1)


def hwire(c, x1, x2, y, label, colour=INK, ends=True):
    c.setStrokeColor(colour)
    c.setLineWidth(1.3)
    c.line(x1, y, x2, y)
    if ends:
        dot(c, x1, y, colour)
        dot(c, x2, y, colour)
    c.setFillColor(colour)
    c.setFont("Helvetica-Bold", 7.2)
    c.drawCentredString((x1 + x2) / 2, y + 3.5, label)


def poly(c, pts, colour=INK, wd=1.4, label=None, lpos=None):
    c.setStrokeColor(colour)
    c.setLineWidth(wd)
    for a, b in zip(pts, pts[1:]):
        c.line(a[0], a[1], b[0], b[1])
    dot(c, pts[0][0], pts[0][1], colour)
    dot(c, pts[-1][0], pts[-1][1], colour)
    if label:
        c.setFillColor(colour)
        c.setFont("Helvetica-Bold", 7.2)
        lx, ly = lpos if lpos else ((pts[0][0] + pts[-1][0]) / 2,
                                    (pts[0][1] + pts[-1][1]) / 2)
        c.drawString(lx, ly, label)


def rail(c, x1, x2, y, colour=BLACK_W, wd=2.6, label=None, sub=None):
    c.setStrokeColor(colour)
    c.setLineWidth(wd)
    c.line(x1, y, x2, y)
    if label:
        c.setFillColor(colour)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x1, y - 11, label)
        if sub:
            c.setFont("Helvetica", 6.8)
            c.setFillColor(MUTED)
            c.drawString(x1 + c.stringWidth(label, "Helvetica-Bold", 8) + 5, y - 11, sub)


def resistor(c, x, y, w=32, h=9, label="", sub="", colour=INK):
    """Series resistor lying on a horizontal wire; x is its left lead end."""
    c.setStrokeColor(colour)
    c.setLineWidth(1.3)
    c.setFillColor(HexColor("#ffffff"))
    c.rect(x, y - h / 2, w, h, stroke=1, fill=1)
    c.setFillColor(colour)
    c.setFont("Helvetica-Bold", 6.6)
    c.drawCentredString(x + w / 2, y - 2.2, label)
    if sub:
        c.setFont("Helvetica", 6.4)
        c.setFillColor(MUTED)
        c.drawCentredString(x + w / 2, y - h / 2 - 9, sub)
    return x + w


def vcap(c, x, ytop, ybot, label="", sub="", polar=False, colour=INK,
         lx=0, ly=0, align="c"):
    """Capacitor hanging from a rail at ytop down to a rail at ybot."""
    mid = (ytop + ybot) / 2
    c.setStrokeColor(colour)
    c.setLineWidth(1.3)
    c.line(x, ytop, x, mid + 3)
    c.line(x, ybot, x, mid - 3)
    c.setLineWidth(1.6)
    c.line(x - 7, mid + 3, x + 7, mid + 3)
    if polar:
        c.setLineWidth(1.6)
        c.arc(x - 7, mid - 9, x + 7, mid - 1, startAng=0, extent=180)
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(colour)
        c.drawString(x + 9, mid + 3, "+")
    else:
        c.line(x - 7, mid - 3, x + 7, mid - 3)
    dot(c, x, ytop, colour)
    dot(c, x, ybot, colour)
    put = {"c": c.drawCentredString, "l": c.drawString, "r": c.drawRightString}[align]
    c.setFillColor(colour)
    c.setFont("Helvetica-Bold", 7.2)
    put(lx or x, ly or (ybot - 12), label)
    if sub:
        c.setFont("Helvetica", 6.4)
        c.setFillColor(MUTED)
        put(lx or x, (ly or (ybot - 12)) - 8.5, sub)


def note(c, x, y, title, lines, accent=INK, size=8.3):
    c.setStrokeColor(accent)
    c.setLineWidth(2)
    c.line(x, y, x, y - (len(lines) * 10.5 + 14))
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 7, y - 9, title)
    c.setFillColor(INK)
    c.setFont("Helvetica", size)
    ty = y - 22
    for ln in lines:
        c.drawString(x + 7, ty, ln)
        ty -= 10.5
    return ty


def table(c, x, y, heads, rows, widths, size=7.6, headsize=8):
    c.setFont("Helvetica-Bold", headsize)
    c.setFillColor(INK)
    cx = x
    for i, h in enumerate(heads):
        c.drawString(cx, y, h)
        cx += widths[i]
    c.setStrokeColor(RULE)
    c.setLineWidth(0.7)
    c.line(x, y - 4, x + sum(widths), y - 4)
    y -= 14
    for row in rows:
        cx = x
        for i, cell in enumerate(row):
            colour = INK
            if isinstance(cell, tuple):
                cell, colour = cell
            c.setFillColor(colour)
            c.setFont("Helvetica", size)
            c.drawString(cx, y, str(cell))
            cx += widths[i]
        y -= size + 3.2
    return y


# ----------------------------------------------------------------- page 1
def page1(c):
    header(c, "1. System overview",
           "Two enclosures. The patch cable length is a variable to be measured, "
           "not a fixed design choice - see README section 16.")
    y = H - M - 58
    bw = 2.55 * inch
    box(c, M, y - 162, bw, 162, "MAIN ENCLOSURE  (vented)", [
        "USB brick, 2-3 A",
        "  <=1 m cable, 20-24 AWG power",
        "  plugs into the dev board's micro-USB",
        "",
        "ESP32-DevKitC V4 (WROOM-32D)",
        "  C1 bulk cap at the 5V / GND pins",
        "  R2 / R3 / R4 series positions",
        "",
        "RJ45 panel jack - shield bonded HERE",
        "",
        "No mains. No fuse. No MOV.",
    ])
    sx = W - M - bw
    box(c, sx, y - 162, bw, 162, "SENSOR ENCLOSURE  (sealed)", [
        "RJ45 panel jack - shield left floating",
        "",
        "R1 100 ohm  +  C2 47 uF",
        "U1 MCP1700-3302E/TO  ->  3.3 V",
        "C3 1 uF  (on PG)",
        "C4 100 nF  (on SG, at the pin)",
        "",
        "SEN-39003 (AS3935)",
        "  SI strapped to SG locally",
        "",
        "SELV only - no mains anywhere",
    ])
    midy, gx1, gx2 = y - 82, M + bw, sx
    c.setStrokeColor(BLUE)
    c.setLineWidth(2.2)
    c.line(gx1, midy, gx2, midy)
    c.setFillColor(BLUE)
    c.setFont("Helvetica-Bold", 8.4)
    c.drawCentredString((gx1 + gx2) / 2, midy + 8, "Cat5 patch, T568B")
    c.setFont("Helvetica", 8)
    c.setFillColor(MUTED)
    c.drawCentredString((gx1 + gx2) / 2, midy - 14, "0.3 / 1 / 2 / 3 m")
    c.drawCentredString((gx1 + gx2) / 2, midy - 25, "swappable")

    ny = y - 190
    ny = note(c, M, ny, "Why two boxes", [
        "Near-field magnetic coupling falls as 1/r^3, so 5 cm -> 50 cm is roughly a 1000x reduction.",
        "Distance is the strongest lever available and nothing else is close.",
        "The interference source was never identified (README 11.3), so the separation is left",
        "adjustable on purpose: survey at each cable length and read the curve. A flat curve",
        "eliminates the ESP32 and the supply properly for the first time.",
    ])
    ny = note(c, M, ny - 10, "Do not plug this into a network switch", [
        "The RJ45 carries 5 V and SPI, not Ethernet. A live PoE port puts 48 V on those lines",
        "and destroys the ESP32 and the sensor. Label both ends.",
    ], accent=AMBER)
    ny = note(c, M, ny - 10, "Signal assignment", [
        "T568B at both ends. Pairs are (1,2) (3,6) (4,5) (7,8). Seven signals plus one spare,",
        "and the spare is spent on a second ground paired with SCLK so the fastest edge gets",
        "its own return. SI is not carried - it straps to ground inside the sensor box.",
    ], accent=GREEN)
    note(c, M, ny - 10, "The jack has a ninth pin", [
        "The panel breakouts are shielded jacks on a 9-way 0.1 in header: 1-8 plus SH, the",
        "metal shell. SH is bonded to ground at the MAIN board only and left floating at the",
        "sensor. One end only - bonding both would wrap a ground loop around the whole run",
        "if a shielded patch cable were ever fitted. Pinout and orientation: page 4.",
    ], accent=GREEN)
    footer(c, 1)


# ----------------------------------------------------------------- page 2
def page2(c):
    header(c, "2. Main enclosure",
           "USB supply, ESP32, series positions and the RJ45 jack. "
           "Every line is one physical wire.")
    y = H - M - 56

    box(c, M, y - 44, 2.15 * inch, 44, "USB brick  2-3 A, 5 V", [
        "quality unit, treated as a consumable",
    ])
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Bold", 7.2)
    c.drawString(M + 2.30 * inch, y - 12, "micro-USB plug through a grommet")
    c.setFont("Helvetica", 6.8)
    c.drawString(M + 2.30 * inch, y - 22, "- the brick's own cable, not a soldered wire.")
    c.drawString(M + 2.30 * inch, y - 32, "Strain-relieve it at the wall; do not bundle")
    c.drawString(M + 2.30 * inch, y - 42, "it alongside the Cat5 run.")

    etop = y - 74
    ex, ew = M + 92, 158
    epins = [("5V", RED), ("GND   top row", BLACK_W), ("GND   next to 18", BLACK_W),
             ("GPIO18   SCLK", BLUE), ("GPIO23   MOSI", BLUE), ("GPIO19   MISO", BLUE),
             ("GPIO5   CS", BLUE), ("GPIO4   IRQ", GREEN), ("GND   far end", BLACK_W)]
    erows, (ex, ey, ew, eh) = pinbox(c, ex, etop, ew, "A1  ESP32-DevKitC V4", epins,
                                     rowh=16, sub="page 4")

    jw = 1.30 * inch
    jx = W - M - jw
    jpins = [("1   5 V", RED), ("2   GND", BLACK_W), ("6   GND", BLACK_W),
             ("3   SCLK", BLUE), ("4   MOSI", BLUE), ("5   MISO", BLUE),
             ("7   CS", BLUE), ("8   IRQ", GREEN), ("SH  shell", BLACK_W)]
    jrows, _ = pinbox(c, jx, etop, jw, "RJ45 jack", jpins, rowh=16, sub="page 4")

    # the USB cable goes into the dev board's own socket -- no wire here
    c.setStrokeColor(MUTED)
    c.setLineWidth(1.3)
    c.setDash(3, 2)
    c.line(M + 46, y - 44, M + 46, etop - 12)
    c.line(M + 46, etop - 12, ex, etop - 12)
    c.setDash()

    # C1 across 5V and the top-row GND
    cx = ex - 44
    mid = (erows[0] + erows[1]) / 2
    c.setStrokeColor(RED)
    c.setLineWidth(1.4)
    c.line(cx, erows[0], ex, erows[0])
    c.setStrokeColor(BLACK_W)
    c.line(cx, erows[1], ex, erows[1])
    c.setStrokeColor(INK)
    c.setLineWidth(1.4)
    c.line(cx, erows[0], cx, mid + 2)
    c.line(cx, erows[1], cx, mid - 6)
    c.setLineWidth(1.7)
    c.line(cx - 9, mid + 2, cx + 9, mid + 2)
    c.arc(cx - 9, mid - 10, cx + 9, mid - 2, startAng=0, extent=180)
    dot(c, ex, erows[0], RED)
    dot(c, ex, erows[1], BLACK_W)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 7.6)
    c.drawRightString(cx - 12, erows[0] - 3, "C1")
    c.setFont("Helvetica", 6.6)
    c.setFillColor(MUTED)
    c.drawRightString(cx - 12, erows[0] - 13, "470-1000 uF")
    c.drawRightString(cx - 12, erows[0] - 22, "16-25 V, 105 C")
    c.drawRightString(cx - 12, erows[0] - 31, "AT the pins")
    c.drawRightString(cx - 12, erows[0] - 40, "stripe lead to GND")

    # ESP32 -> jack
    plan = [
        (0, "W-M3  5 V", RED, None),
        (1, "W-M4  GND", BLACK_W, None),
        (2, "W-M10  GND", BLACK_W, None),
        (3, "W-M5  SCLK", BLUE, "R2"),
        (4, "W-M6  MOSI", BLUE, "R3"),
        (5, "W-M8  MISO", BLUE, None),
        (6, "W-M7  CS", BLUE, "R4"),
        (7, "W-M9  IRQ", GREEN, None),
        (8, "W-M11  shield", BLACK_W, None),
    ]
    for i, lbl, col, res in plan:
        yy = erows[i]
        if res:
            rx = jx - 74
            c.setStrokeColor(col)
            c.setLineWidth(1.3)
            c.line(ex + ew, yy, rx, yy)
            c.line(rx + 32, yy, jx, yy)
            dot(c, ex + ew, yy, col)
            dot(c, jx, yy, col)
            resistor(c, rx, yy, label=res, colour=col)
            c.setFillColor(col)
            c.setFont("Helvetica-Bold", 7.2)
            c.drawString(ex + ew + 6, yy + 4, lbl)
        else:
            hwire(c, ex + ew, jx, yy, lbl, col)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 6.6)
    c.drawCentredString(jx - 58, ey - 12,
                        "R2 / R3 / R4:  33-100 ohm positions, wire links on day one")

    ny = ey - 34
    ny = note(c, M, ny, "R2 / R3 / R4 - series positions, wire links on day one", [
        "Only the three lines the ESP32 DRIVES get a position: SCLK, MOSI, CS. MISO and IRQ are",
        "driven from the far end, so damping them at this end would do nothing at all.",
        "Fit plain wire links first. Set data_rate: 200kHz (README 7.1) and only fit real",
        "resistors if the 3 m point of the distance sweep misbehaves.",
    ], accent=GREEN)
    ny = note(c, M, ny - 10, "C1 is the reason this board exists", [
        "It is the reservoir for the 300-500 mA WiFi bursts the USB cable's resistance cannot",
        "supply fast enough. It must sit AT the 5V and GND pins. The DevKitC has five pins",
        "between 5V and its nearest ground, so the loop is about 27 mm however you arrange it -",
        "that is a property of the dev board, not of the layout. Watch the polarity.",
    ])
    note(c, M, ny - 10, "The USB cable is a circuit element, not an accessory", [
        "28 AWG conductors are ~0.21 ohm/m. Over 2 m, counting the ground return, that is ~0.84 ohm:",
        "a 500 mA burst drops ~0.42 V, so 5.0 V arrives as 4.58 V. The onboard AMS1117 needs over a",
        "volt of headroom, so a thin or long cable browns the board out - the same failure the",
        "undersized IRM-02-5 produced, by a different route.",
        "Use <=1 m with 20-24 AWG power conductors, and MEASURE at the 5V pin under WiFi load.",
        "Keep the USB cable away from the Cat5 run; do not bundle them parallel.",
    ], accent=AMBER)
    footer(c, 2)


# ----------------------------------------------------------------- page 3
def page3(c):
    header(c, "3. Sensor enclosure",
           "Every part of the local rail, drawn. 5 V arrives on the cable; 3.3 V is made "
           "here, centimetres from the pins.")

    y_rail, y_pg, y_sg, boxtop = 702, 628, 578, 540

    jw = 100
    jpins = [("1   5 V", RED), ("2   GND", BLACK_W), ("6   GND", BLACK_W),
             ("3   SCLK", BLUE), ("4   MOSI", BLUE), ("5   MISO", BLUE),
             ("7   CS", BLUE), ("8   IRQ", GREEN), ("SH  shell", MUTED)]
    jrows, (jx, jy, _, jh) = pinbox(c, M, boxtop, jw, "RJ45 jack", jpins, sub="page 4")
    jr = jx + jw

    sw = 140
    sx = W - M - sw
    spins = [("GND", BLACK_W), ("SI", BLACK_W), ("VCC   3.3 V", ORANGE),
             ("SCK", BLUE), ("MOSI", BLUE), ("MISO", BLUE), ("CS", BLUE), ("IRQ", GREEN)]
    srows, _ = pinbox(c, sx, boxtop, sw, "M1  SEN-39003", spins, right=True,
                      sub="verify order")

    # ---- power chain along y_rail
    poly(c, [(jr, jrows[0]), (158, jrows[0]), (158, y_rail), (192, y_rail)], RED)
    x = resistor(c, 192, y_rail, w=34, label="R1", sub="100 ohm 1/4 W", colour=RED)
    c.setStrokeColor(RED)
    c.setLineWidth(1.4)
    c.line(x, y_rail, 272, y_rail)
    vcap(c, 244, y_rail, y_pg, "C2", "47 uF 50 V", polar=True, colour=RED,
         lx=232, ly=616, align="r")

    ux, uw, uh = 272, 70, 36
    c.setFillColor(HexColor("#ffffff"))
    c.setStrokeColor(INK)
    c.setLineWidth(1.2)
    c.rect(ux, y_rail - uh / 2, uw, uh, stroke=1, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(ux + uw / 2, y_rail + 5, "U1  MCP1700")
    c.setFont("Helvetica", 6.6)
    c.setFillColor(MUTED)
    c.drawCentredString(ux + uw / 2, y_rail - 4, "-3302E/TO")
    c.setFont("Helvetica", 6.2)
    c.drawString(ux + 2, y_rail - uh / 2 + 3, "IN")
    c.drawRightString(ux + uw - 2, y_rail - uh / 2 + 3, "OUT")
    dot(c, ux, y_rail, RED)
    c.setStrokeColor(BLACK_W)
    c.setLineWidth(1.3)
    c.line(ux + uw / 2, y_rail - uh / 2, ux + uw / 2, y_pg)
    dot(c, ux + uw / 2, y_pg, BLACK_W)
    c.setFillColor(BLACK_W)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(ux + uw / 2 + 4, y_pg + 16, "W-S4")
    c.setFont("Helvetica", 6.2)
    c.setFillColor(MUTED)
    c.drawString(ux + uw / 2 + 4, y_pg + 8, "GND")

    c.setStrokeColor(ORANGE)
    c.setLineWidth(1.4)
    c.line(ux + uw, y_rail, 428, y_rail)
    dot(c, ux + uw, y_rail, ORANGE)
    vcap(c, 358, y_rail, y_pg, "C3", "1 uF X7R", colour=ORANGE,
         lx=346, ly=616, align="r")
    vcap(c, 396, y_rail, y_sg, "C4", "100 nF X7R", colour=ORANGE,
         lx=372, ly=560, align="r")
    poly(c, [(428, y_rail), (428, srows[2]), (sx, srows[2])], ORANGE)
    c.setFillColor(ORANGE)
    c.setFont("Helvetica-Bold", 7.2)
    c.drawRightString(sx - 5, srows[2] + 5, "W-S5 / W-S6")

    # ---- ground rails
    rail(c, 168, 366, y_pg, BLACK_W)
    rail(c, 380, 414, y_sg, BLACK_W)
    c.setFillColor(BLACK_W)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(168, y_pg + 6, "PG")
    c.drawString(380, y_sg + 6, "SG")
    poly(c, [(jr, jrows[1]), (176, jrows[1]), (176, y_pg)], BLACK_W)
    poly(c, [(jr, jrows[2]), (196, jrows[2]), (196, y_pg)], BLACK_W)
    poly(c, [(sx, srows[0]), (408, srows[0]), (408, y_sg)], BLACK_W)
    poly(c, [(sx, srows[1]), (386, srows[1]), (386, y_sg)], BLACK_W)
    for i, lab in ((0, "W-S1"), (1, "W-S2"), (2, "W-S3")):
        c.setFillColor(RED if i == 0 else BLACK_W)
        c.setFont("Helvetica-Bold", 7.2)
        c.drawString(jr + 5, jrows[i] + 5, lab)
    for i, lab in ((0, "W-S7"), (1, "W-S8  SI strap")):
        c.setFillColor(BLACK_W)
        c.setFont("Helvetica-Bold", 7.2)
        c.drawRightString(sx - 5, srows[i] + 5, lab)

    # the single tie
    c.setStrokeColor(AMBER)
    c.setLineWidth(2.6)
    c.line(366, y_pg, 380, y_sg)
    dot(c, 366, y_pg, AMBER)
    dot(c, 380, y_sg, AMBER)
    c.setFillColor(AMBER)
    c.setFont("Helvetica-Bold", 7.6)
    c.drawRightString(358, 600, "W-S9")
    c.setFont("Helvetica-Bold", 6.8)
    c.drawRightString(358, 591, "the ONLY tie")

    # ---- SPI
    for i, (lbl, col) in enumerate([("W-S10  SCLK", BLUE), ("W-S11  MOSI", BLUE),
                                    ("W-S12  MISO", BLUE), ("W-S13  CS", BLUE),
                                    ("W-S14  IRQ", GREEN)], start=3):
        hwire(c, jr, sx, jrows[i], lbl, col)

    # ---- shield, dead-ended
    c.setStrokeColor(MUTED)
    c.setLineWidth(1.2)
    c.setDash(2, 2)
    c.line(jr, jrows[8], jr + 34, jrows[8])
    c.setDash()
    opencirc(c, jr + 34, jrows[8])
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7)
    c.drawString(jr + 42, jrows[8] - 3, "no connection at this end - the shield is bonded")
    c.drawString(jr + 42, jrows[8] - 12, "at the main board only")

    ny = jy - 24
    ny = note(c, M, ny, "Two grounds, and exactly one tie between them", [
        "PG carries the cable's ground return, C2, and the regulator's own reference. SG carries",
        "only the sensor's GND pin, C4 and the SI strap. They meet at W-S9 and nowhere else.",
        "C3 belongs to the regulator (stability) so it lands on PG; C4 belongs to the sensor",
        "(decoupling) so it lands on SG. Swapping them defeats the split as surely as a second tie.",
        "A second bridge wraps a ground loop around the LDO and C4 stops being local.",
    ], accent=AMBER)
    ny = note(c, M, ny - 10, "Why a linear regulator, and why out here", [
        "A switching regulator would put a 100 kHz - 1 MHz noise source centimetres from a 500 kHz",
        "magnetic antenna: the worst possible place for one. A linear regulator has no switching",
        "node, and at under 1 mA the wasted heat is nothing. The E suffix is the -40/+125 C grade,",
        "required for a ~52 C attic. C3 is REQUIRED for MCP1700 stability, not optional.",
        "LDO rejection is largely gone by 500 kHz, so R1/C2 and C3/C4 are complementary to it,",
        "not redundant with it. Neither the regulator nor the passives suffices alone.",
    ])
    note(c, M, ny - 10, "Headroom check", [
        "5 V leaves the main board from the dev board's 5V pin, which on some DevKitC boards sits",
        "behind a Schottky and reads ~0.3 V low. R1 drops another ~0.1 V at the sensor's sub-1 mA",
        "draw. Worst case the MCP1700 still sees ~4.5 V for a 3.3 V output - enormous headroom.",
        "Measure it anyway at bring-up: 3.3 V at the sensor VCC pin, at the far end (README 12).",
    ], accent=GREEN)
    footer(c, 3)


# ----------------------------------------------------------------- page 4
def _rj45(c, x, y, w, h, order, caption, sub):
    """One view of the RJ45 breakout: PCB, jack, and the 9-way header."""
    c.setFillColor(HexColor("#eef3ee"))
    c.setStrokeColor(INK)
    c.setLineWidth(1.1)
    c.rect(x, y, w, h, stroke=1, fill=1)
    # jack body
    jw2, jh2 = w * 0.48, h * 0.46
    jx2, jy2 = x + (w - jw2) / 2, y + 10
    c.setFillColor(HexColor("#dcdcdc"))
    c.setStrokeColor(INK)
    c.rect(jx2, jy2, jw2, jh2, stroke=1, fill=1)
    c.setFillColor(HexColor("#333333"))
    c.rect(jx2 + 5, jy2 + 9, jw2 - 10, jh2 - 14, stroke=0, fill=1)
    c.setFillColor(HexColor("#333333"))
    c.rect(jx2 + jw2 / 2 - 7, jy2 + 1, 14, 9, stroke=0, fill=1)
    c.setFont("Helvetica", 5.6)
    c.setFillColor(HexColor("#ffffff"))
    c.drawCentredString(jx2 + jw2 / 2, jy2 + jh2 / 2, "latch slot at the bottom")
    # mounting holes
    for hx in (x + 7, x + w - 7):
        for hy in (y + 9, y + h - 12):
            opencirc(c, hx, hy, MUTED, 3.2)
    # header
    pitch = 13
    hx0 = x + (w - pitch * 8) / 2
    hy0 = y + h - 20
    for i, name in enumerate(order):
        px = hx0 + i * pitch
        c.setStrokeColor(INK)
        c.setLineWidth(1.2)
        c.line(px, hy0, px, hy0 + 12)
        colour = MUTED if name == "SH" else INK
        c.setFillColor(colour)
        c.circle(px, hy0, 2.1, stroke=0, fill=1)
        c.setFont("Helvetica-Bold", 6.6)
        c.setFillColor(colour)
        c.drawCentredString(px, hy0 - 10, name)
    c.setFont("Helvetica-Bold", 8.4)
    c.setFillColor(INK)
    c.drawCentredString(x + w / 2, y - 13, caption)
    c.setFont("Helvetica", 7.2)
    c.setFillColor(MUTED)
    c.drawCentredString(x + w / 2, y - 23, sub)


def page4(c):
    header(c, "4. Connector and board pinouts",
           "The two parts this design is most likely to be wired backwards to. "
           "Wire to the printed numbers, never to a position in a photograph.")
    y = H - M - 50

    bw, bh = 2.0 * inch, 1.35 * inch
    _rj45(c, M + 20, y - bh, bw, bh, ["1", "2", "3", "4", "5", "6", "7", "8", "SH"],
          "From INSIDE the box", "the silkscreen side, where you solder")
    _rj45(c, M + 60 + bw, y - bh, bw, bh, ["SH", "8", "7", "6", "5", "4", "3", "2", "1"],
          "From OUTSIDE the box", "looking into the jack, ready to plug in")

    c.setFont("Helvetica", 7.6)
    c.setFillColor(INK)
    tx = M + 100 + 2 * bw
    for i, ln in enumerate([
            "Both drawings are the same part.",
            "You solder from the inside, so the",
            "silkscreen order 1..8, SH is the one",
            "that matters; the mirrored order is",
            "only what you see when you plug a",
            "cable in from outside.",
            "9-way 0.1 in header, 2.54 mm pitch.",
            "PCB 33.86 x 27.96 mm, 1.4 mm thick.",
            "Mounting holes 3.00 mm in from each",
            "side, 28.00 mm apart - use the",
            "breakout itself as the drill template",
            "rather than trusting a dimension.",
            "",
    ]):
        c.drawString(tx, y - 6 - i * 10, ln)

    ny = y - bh - 46
    rows = [(p, sig, col, ("bonded to GND at the main board only" if p == "SH" else ""))
            for p, col, sig in PINS]
    ny = table(c, M, ny, ["Pin", "Signal", "T568B colour", "Note"], rows,
               [40, 80, 110, 240])

    ny -= 6
    c.setFont("Helvetica", 7.6)
    c.setFillColor(INK)
    c.drawString(M, ny, "The jack is top-entry: the cable goes in PERPENDICULAR to the "
                        "breakout PCB, so the board lies flat against the inside of the box")
    c.drawString(M, ny - 10, "wall behind a ~17 x 16.5 mm cutout and the right-angle header "
                             "exits sideways. Solder the pigtail to the header pins, or pull")
    c.drawString(M, ny - 20, "the header and solder into its holes - lower profile and "
                             "mechanically better. Cable-tie the bundle to the perf board.")
    ny -= 42
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(INK)
    c.drawString(M, ny, "A1   ESP32-DevKitC V4  /  ESP32-WROOM-32D  -  38 pins, USB at the bottom")
    ny -= 8

    # two columns of 19, drawn portrait
    rowh = 11.5
    top = ny - 14
    lx, rx = M + 120, M + 250
    c.setStrokeColor(INK)
    c.setLineWidth(1.1)
    c.setFillColor(BOXFILL)
    c.rect(lx - 6, top - 19 * rowh - 4, rx - lx + 12, 19 * rowh + 8, stroke=1, fill=1)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7)
    c.drawCentredString((lx + rx) / 2, top - 19 * rowh - 15, "micro-USB")
    for i in range(19):
        yy = top - i * rowh - 8
        for side, names, ax, align in (("L", ESP_LEFT, lx, "l"), ("R", ESP_RIGHT, rx, "r")):
            name = names[i]
            use = ESP_USE.get((side, name))
            colour = use[1] if use else MUTED
            c.setFillColor(colour)
            c.setFont("Helvetica-Bold" if use else "Helvetica", 7.4)
            if align == "l":
                c.drawString(ax, yy, name)
                if use:
                    c.setFont("Helvetica", 7)
                    c.drawRightString(ax - 8, yy, use[0])
            else:
                c.drawRightString(ax, yy, name)
                if use:
                    c.setFont("Helvetica", 7)
                    c.drawString(ax + 8, yy, use[0])

    c.setFont("Helvetica", 7.6)
    c.setFillColor(INK)
    tx = M + 340
    for i, ln in enumerate([
            "Measured off the board in the vendor pinout:",
            "19 pins per row, rows 1.0 in (25.4 mm) apart -",
            "exactly 10 holes on 0.1 in perf. Confirm yours",
            "before soldering the female headers, and use",
            "the dev board itself as the jig.",
            "",
            "Note the vendor's own diagram mislabels left",
            "pin 10: the silkscreen reads 26, not 23. GPIO23",
            "is on the RIGHT row. If you wire MOSI to the",
            "left row you will get nothing and see nothing",
            "wrong.",
            "",
            "GPIO 4, 5, 18, 19 and 23 are ALL on the right",
            "row, so the whole cable pigtail lands on one",
            "side and only the 5 V feed crosses the board.",
            "",
            "5V is the bottom-left pin, beside the USB. Its",
            "nearest ground is five pins away - see page 2.",
    ]):
        c.drawString(tx, ny - 20 - i * 10, ln)

    footer(c, 4)


# ----------------------------------------------------------------- page 5
WIRES = [
    ("W-M1",  "C1 +",                  "ESP32 5V pin",        "22 solid", "red",
     "as short as physically possible"),
    ("W-M2",  "C1 -",                  "ESP32 GND, top row",  "22 solid", "black",
     "with W-M1; stripe lead is minus"),
    ("W-M3",  "C1 +",                  "RJ45 pin 1",          "24 solid", "wh/orange",
     "twist with W-M4"),
    ("W-M4",  "C1 -",                  "RJ45 pin 2",          "24 solid", "orange",
     "the pin-1 pair's return"),
    ("W-M5",  "ESP32 GPIO18 SCLK",     "R2, then RJ45 pin 3", "24 solid", "wh/green",
     "series position"),
    ("W-M6",  "ESP32 GPIO23 MOSI",     "R3, then RJ45 pin 4", "24 solid", "blue",
     "series position"),
    ("W-M7",  "ESP32 GPIO5 CS",        "R4, then RJ45 pin 7", "24 solid", "wh/brown",
     "series position"),
    ("W-M8",  "ESP32 GPIO19 MISO",     "RJ45 pin 5",          "24 solid", "wh/blue",
     "no resistor - MISO is an input here"),
    ("W-M9",  "ESP32 GPIO4 IRQ",       "RJ45 pin 8",          "24 solid", "brown",
     "no resistor - IRQ is an input here"),
    ("W-M10", "ESP32 GND beside 18",   "RJ45 pin 6",          "24 solid", "green",
     "the SCLK pair's own return"),
    ("W-M11", "ESP32 GND, far end",    "RJ45 pin SH",         "24 solid", "any",
     "shield bonded at THIS end only"),
    ("W-S1",  "RJ45 pin 1",            "R1 100 ohm",          "24 solid", "wh/orange",
     "start of the local rail"),
    ("W-S2",  "RJ45 pin 2",            "PG rail",             "24 solid", "orange", ""),
    ("W-S3",  "RJ45 pin 6",            "PG rail",             "24 solid", "green",
     "the SCLK pair's return"),
    ("W-S4",  "U1 GND pin",            "PG rail",             "24 solid", "black", ""),
    ("W-S5",  "U1 OUT 3.3 V",          "C4 + / VCC node",     "24 solid", "red", ""),
    ("W-S6",  "C4 + node",             "sensor VCC",          "24 solid", "red",
     "one hole - do not lengthen"),
    ("W-S7",  "sensor GND",            "SG rail",             "24 solid", "black", ""),
    ("W-S8",  "sensor SI",             "SG rail",             "24 solid", "black",
     "grounds SI: selects SPI, not I2C"),
    ("W-S9",  "SG rail",               "PG rail",             "22 solid", "black",
     "THE ONLY TIE - mark it"),
    ("W-S10", "RJ45 pin 3",            "sensor SCK",          "24 solid", "wh/green", ""),
    ("W-S11", "RJ45 pin 4",            "sensor MOSI",         "24 solid", "blue", ""),
    ("W-S12", "RJ45 pin 5",            "sensor MISO",         "24 solid", "wh/blue", ""),
    ("W-S13", "RJ45 pin 7",            "sensor CS",           "24 solid", "wh/brown", ""),
    ("W-S14", "RJ45 pin 8",            "sensor IRQ",          "24 solid", "brown", ""),
    ("-",     "RJ45 pin SH (sensor)",  "nothing",             "-",        "-",
     "left floating: single-point shield"),
]


def page5(c):
    header(c, "5. Wire schedule",
           "Reference numbers match pages 2 and 3, and the hole coordinates in "
           "as3935-protoboard-layout.pdf.")
    y = H - M - 52
    colmap = {"red": RED, "black": BLACK_W, "orange": HexColor("#b06000"),
              "green": GREEN, "blue": BLUE, "wh/orange": HexColor("#b06000"),
              "wh/green": GREEN, "wh/blue": BLUE, "wh/brown": HexColor("#5a3a1a"),
              "brown": HexColor("#5a3a1a"), "any": MUTED, "-": MUTED}
    rows = [(r, a, b, awg, (col, colmap.get(col, INK)), nt)
            for r, a, b, awg, col, nt in WIRES]
    ny = table(c, M, y, ["Ref", "From", "To", "AWG", "Colour", "Note"], rows,
               [44, 118, 112, 44, 66, 96])

    ny -= 22
    ny = note(c, M, ny, "Nothing here is carrying any current worth the name", [
        "Past the RJ45 the whole sensor rail draws under 1 mA. The longest run on either board is",
        "about 90 mm; even 30 AWG would add 30 milliohms, or 15 microvolts at 500 uA. R1 drops",
        "0.1 V on purpose - six thousand times more. Gauge is electrically irrelevant on both",
        "boards. It is chosen on mechanical grounds alone, and page 6 says why.",
        "The one place gauge ever mattered in this project is the USB cable (README 7.4), and",
        "that is a cable you buy, not one you build.",
    ], accent=GREEN)
    note(c, M, ny - 10, "Colour is documentation, so keep it", [
        "The colour column is T568B, because the pigtails are cut from Cat5: the conductor",
        "colours then match the pin numbers on both breakouts and the cable between them, end",
        "to end, with nothing to remember. Where a wire is not part of the cable run (W-M1,",
        "W-M2, W-S4, W-S7, W-S8, W-S9) use plain red for 5 V, orange for 3.3 V, black for ground.",
    ])
    footer(c, 5)


# ----------------------------------------------------------------- page 6
def page6(c):
    header(c, "6. Wire specification, and bring-up",
           "What to buy, what not to use, and the order to switch things on in.")
    y = H - M - 52

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(INK)
    c.drawString(M, y, "What each job actually needs")
    y -= 16
    rows = [
        ("Buses on the sensor board", "bare SOLID tinned copper, 20-22 AWG", "~1 m",
         "must lie straight across the pads"),
        ("Links on both boards", "insulated SOLID, 24 AWG (26 also fine)", "~2 m",
         "must enter a 1 mm hole unaided"),
        ("Pigtails, jack to board", "solid Cat5e offcut, 8 cores", "2 x 15 cm",
         "colours match the pin table exactly"),
        ("USB brick to ESP32", "none - it plugs into the micro-USB", "-",
         "grommet and strain relief only"),
        ("Mains variant (README 7.3)", "stranded silicone, 18-20 AWG", "-",
         "not built in rev 2"),
    ]
    y = table(c, M, y, ["Where", "What", "Length", "Why"], rows,
              [140, 190, 60, 140])

    y -= 22
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(INK)
    c.drawString(M, y, "Shopping list")
    y -= 16
    rows = [
        ("Bus wire", "bare solid tinned copper, 22 AWG, ~0.64 mm", "1 spool",
         "sold as 'buss bar wire' / 'jumper wire'"),
        ("Hookup wire", "solid core, 24 AWG, PVC or PTFE, 6 colours", "1 kit",
         "PTFE if you can: it will not melt back"),
        ("Cat5e offcut", "SOLID conductor cable, ~1 m", "1",
         "riser/in-wall stock, NOT a patch cable"),
        ("Female header", "0.1 in, 1x40 breakaway", "2",
         "cut to 1x19 for the ESP32"),
        ("Male header", "0.1 in, 1x40 breakaway", "1",
         "8 pins for the SEN-39003, if not supplied"),
    ]
    y = table(c, M, y, ["Item", "Specification", "Qty", "Note"], rows,
              [90, 230, 50, 160])

    ny = y - 20
    ny = note(c, M, ny, "Why not the silicone stranded already on hand", [
        "16 / 18 / 20 / 24 AWG stranded silicone is excellent wire and the wrong wire for this.",
        "Stranded will not enter a 0.1 in hole without being tinned first, and a tinned end is a",
        "solid end with worse geometry. Silicone insulation is thick and soft, so at 2.54 mm pitch",
        "it crowds neighbouring holes and will not hold a route. And a bus has to be a straight",
        "bare bar soldered to eight pads in a row: stranded cannot be made straight. Keep it for",
        "the mains variant and for anything that has to flex.",
    ], accent=AMBER)
    ny = note(c, M, ny - 10, "Why solid Cat5e for the pigtails", [
        "Eight solid 24 AWG conductors in one jacket, already coloured to T568B, so the pigtail",
        "documents itself against the pin table on page 4. Do not cut up one of the patch cables",
        "bought for the distance sweep - those are the experiment. Buy a metre of in-wall stock,",
        "or salvage a dead cable, and check it is SOLID: patch cable is stranded.",
        "Its insulation is usually HDPE and shrinks back fast under an iron. Strip generously,",
        "tin quickly, do not dwell. Leave a service loop and cable-tie both ends to the board.",
        "SH has no conductor in the cable, so it is a ninth wire: any offcut will do.",
    ])
    ny = note(c, M, ny - 10, "Not 30 AWG wire-wrap, tempting as it is", [
        "Kynar wire-wrap is the classic perfboard wire and it is genuinely nicer to route. It is",
        "also fragile, and README 11.3 is this project's warning about builds that move: the old",
        "breadboard's noise floor fell by two thirds the moment it was handled. Rigidity is a",
        "pass/fail measurement here, so spend the extra bulk on 24 AWG solid.",
    ], accent=GREEN)

    ny = note(c, M, ny - 10, "Bring-up, in order", [
        "1.  Assemble both boxes; connect with the SHORTEST patch cable.",
        "2.  Measure 5 V at the ESP32 5V pin DURING WiFi activity, not at idle. Want >4.7 V.",
        "3.  Measure 3.3 V at the sensor VCC pin, at the far end, after the LDO.",
        "4.  Verify tuning capacitance OVER SERIAL - the one check WiFi cannot do (README 12.1).",
        "5.  Confirm the sensor responds to the SEN-39002 emulator. Expect disturbers, not lightning.",
        "6.  Platform-validity test: survey, handle the build, survey again. Rates must not move.",
        "7.  Only then mount, and run the distance sweep at 0.3 / 1 / 2 / 3 m.",
    ])
    footer(c, 6)


def main():
    c = canvas.Canvas(OUT, pagesize=letter)
    c.setTitle("AS3935 lightning detector node - revision 2 wiring")
    c.setAuthor("as3935_lightning_detector")
    for fn in (page1, page2, page3, page4, page5, page6):
        fn(c)
        c.showPage()
    c.save()
    print("wrote %s" % OUT)


if __name__ == "__main__":
    main()
