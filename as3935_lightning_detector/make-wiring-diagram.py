#!/usr/bin/env python3
"""Regenerate as3935-node-wiring.pdf -- the point-to-point wiring set for the
revision 2 hardware (README section 16).

    python3 make-wiring-diagram.py          # needs reportlab

The rev 1 drawing was produced ad hoc with no generator committed, so it could
not be revised when the design changed. This script is the source of truth for
the drawing; edit it, re-run it, commit both.

Every line on the drawings is one physical wire, labelled W<n>, and the wire
numbers match the table on the last page.
"""
from reportlab.lib.colors import HexColor, black, white
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
BLACK_W  = HexColor("#333333")   # ground
BLUE     = HexColor("#1a5fb4")   # SPI
GREEN    = HexColor("#2c6e49")   # IRQ / misc
AMBER    = HexColor("#8a5a00")   # warnings

PAGES = 4
TITLE = "AS3935 lightning detector node - revision 2"


def header(c, page, subtitle, blurb):
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
                 "Print at 100% / actual size. Wire colours are labelled, so the "
                 "drawing still reads correctly in greyscale.")
    c.drawRightString(W - M, M + 11, f"Page {page} of {PAGES}")


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


def pinbox(c, x, ytop, w, title, pins, rowh=12.5, pad=24, right=False):
    """Box whose pin labels sit on a fixed grid. Returns {name: y} so wires
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
    rows = {}
    c.setFont("Helvetica", 8.3)
    ry = ytop - pad - 8
    for name, label in pins:
        c.setFillColor(INK)
        if right:
            c.drawRightString(x + w - 8, ry - 3, label)
        else:
            c.drawString(x + 8, ry - 3, label)
        rows[name] = ry
        ry -= rowh
    return rows, (x, y, w, h)


def hwire(c, x1, x2, y, label, colour=INK):
    c.setStrokeColor(colour)
    c.setLineWidth(1.3)
    c.line(x1, y, x2, y)
    c.setFillColor(colour)
    c.circle(x1, y, 1.8, stroke=0, fill=1)
    c.circle(x2, y, 1.8, stroke=0, fill=1)
    c.setFont("Helvetica-Bold", 7.2)
    c.drawCentredString((x1 + x2) / 2, y + 3.5, label)


def elbow(c, x1, y1, x2, y2, label, colour=INK):
    """Horizontal, vertical, horizontal. Keeps the power chain clear of the
    signal wires instead of crossing them."""
    xm = (x1 + x2) / 2
    c.setStrokeColor(colour)
    c.setLineWidth(1.4)
    c.line(x1, y1, xm, y1)
    c.line(xm, y1, xm, y2)
    c.line(xm, y2, x2, y2)
    c.setFillColor(colour)
    c.circle(x1, y1, 1.8, stroke=0, fill=1)
    c.circle(x2, y2, 1.8, stroke=0, fill=1)
    c.setFont("Helvetica-Bold", 7.2)
    c.drawCentredString(xm, (y1 + y2) / 2 + 3, label)


def note(c, x, y, w, title, lines, accent=INK):
    c.setStrokeColor(accent)
    c.setLineWidth(2)
    c.line(x, y, x, y - (len(lines) * 10.5 + 14))
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 7, y - 9, title)
    c.setFillColor(INK)
    c.setFont("Helvetica", 8.3)
    ty = y - 22
    for ln in lines:
        c.drawString(x + 7, ty, ln)
        ty -= 10.5
    return ty


# ----------------------------------------------------------------- page 1
def page1(c):
    header(c, 1, "1. System overview",
           "Two enclosures. The patch cable length is a variable to be measured, "
           "not a fixed design choice - see README section 16.")
    y = H - M - 58
    bw = 2.55 * inch                      # narrow enough to leave a label gap
    box(c, M, y - 150, bw, 150, "MAIN ENCLOSURE  (vented)", [
        "USB brick, 2-3 A",
        "  <=1 m cable, 20-24 AWG power",
        "",
        "ESP32 dev board",
        "  5 V bulk cap AT the 5V/GND pins",
        "",
        "RJ45 panel jack",
        "",
        "No mains. No fuse. No MOV.",
        "  (mains variant: README 7.3)",
    ])
    sx = W - M - bw
    box(c, sx, y - 150, bw, 150, "SENSOR ENCLOSURE  (sealed)", [
        "RJ45 panel jack",
        "",
        "100 ohm + 10-47 uF",
        "MCP1700-3302E/TO  ->  3.3 V",
        "1 uF || 100 nF  (100 nF at pin)",
        "",
        "SEN-39003 (AS3935)",
        "  SI strapped to GND locally",
        "",
        "SELV only - no mains anywhere",
    ])
    midy, gx1, gx2 = y - 75, M + bw, sx
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

    ny = y - 178
    ny = note(c, M, ny, 0, "Why two boxes", [
        "Near-field magnetic coupling falls as 1/r^3, so 5 cm -> 50 cm is roughly a 1000x reduction.",
        "Distance is the strongest lever available and nothing else is close.",
        "The interference source was never identified (README 11.3), so the separation is left",
        "adjustable on purpose: survey at each cable length and read the curve. A flat curve",
        "eliminates the ESP32 and the supply properly for the first time.",
    ])
    ny = note(c, M, ny - 10, 0, "Do not plug this into a network switch", [
        "The RJ45 carries 5 V and SPI, not Ethernet. A live PoE port puts 48 V on those lines",
        "and destroys the ESP32 and the sensor. Label both ends.",
    ], accent=AMBER)
    note(c, M, ny - 10, 0, "Signal assignment", [
        "T568B at both ends. Pairs are (1,2) (3,6) (4,5) (7,8). Seven signals plus one spare,",
        "and the spare is spent on a second ground paired with SCLK so the fastest edge gets",
        "its own return. SI is not carried - it straps to GND inside the sensor box.",
    ], accent=GREEN)
    footer(c, 1)


# ----------------------------------------------------------------- page 2
def page2(c):
    header(c, 2, "2. Main enclosure",
           "USB supply, ESP32, and the RJ45 jack. Every line is one physical wire.")
    y = H - M - 58

    box(c, M, y - 52, 2.0 * inch, 52, "USB brick  2-3 A, 5 V", [
        "quality unit, treated as a consumable",
    ])

    etop = y - 74
    epins = [("5v", "5V / VIN"), ("gnd", "GND"), ("sclk", "GPIO18  SCLK"),
             ("gnd2", "GND"), ("mosi", "GPIO23  MOSI"), ("miso", "GPIO19  MISO"),
             ("cs", "GPIO5   CS"), ("irq", "GPIO4   IRQ")]
    erows, (ex, ey, ew, eh) = pinbox(c, M, etop, 2.3 * inch, "ESP32 dev board", epins)

    jw = 1.25 * inch
    jx = W - M - jw
    jpins = [("5v", "1  5V"), ("gnd", "2  GND"), ("sclk", "3  SCLK"), ("gnd2", "6  GND"),
             ("mosi", "4  MOSI"), ("miso", "5  MISO"), ("cs", "7  CS"), ("irq", "8  IRQ")]
    jrows, _ = pinbox(c, jx, etop, jw, "RJ45 jack", jpins)

    # USB -> ESP32: terminate at the box edge, do not draw over its text
    for dx, lbl, col in ((0.35, "W1  +5 V", RED), (1.35, "W2  GND", BLACK_W)):
        c.setStrokeColor(col); c.setLineWidth(1.4)
        c.line(M + dx * inch, y - 52, M + dx * inch, etop)
        c.setFillColor(col)
        c.circle(M + dx * inch, etop, 1.8, stroke=0, fill=1)
        c.setFont("Helvetica-Bold", 7.2)
        c.drawString(M + (dx + 0.07) * inch, (y - 52 + etop) / 2 - 3, lbl)

    for key, lbl, col in (("5v", "W3  5 V", RED), ("gnd", "W4  GND", BLACK_W),
                          ("sclk", "W5  SCLK", BLUE), ("gnd2", "W6  GND", BLACK_W),
                          ("mosi", "W7  MOSI", BLUE), ("miso", "W8  MISO", BLUE),
                          ("cs", "W9  CS", BLUE), ("irq", "W10  IRQ", GREEN)):
        hwire(c, ex + ew, jx, erows[key], lbl, col)

    c.setFillColor(RED); c.setFont("Helvetica-Bold", 8)
    c.drawString(M, ey - 16, "C1  470-1000 uF, 16-25 V, 105 C  --  mounted AT the 5V/GND pins")
    c.setFillColor(MUTED); c.setFont("Helvetica", 8)
    c.drawString(M, ey - 27, "Reservoir for the 300-500 mA WiFi bursts the cable resistance cannot supply fast enough.")

    ny = ey - 46
    ny = note(c, M, ny, 0, "The USB cable is a circuit element, not an accessory", [
        "28 AWG conductors are ~0.21 ohm/m. Over 2 m, counting the ground return, that is ~0.84 ohm:",
        "a 500 mA burst drops ~0.42 V, so 5.0 V arrives as 4.58 V. The onboard AMS1117 needs over a",
        "volt of headroom, so a thin or long cable browns the board out - the same failure the",
        "undersized IRM-02-5 produced, by a different route.",
        "Use <=1 m with 20-24 AWG power conductors, and MEASURE at the 5V pin under WiFi load.",
        "Keep the USB cable away from the Cat5 run; do not bundle them parallel.",
    ], accent=AMBER)
    note(c, M, ny - 10, 0, "No mains in revision 2", [
        "The old rule - never have USB and the mains supply powered at the same time - does not",
        "apply, because there is only ever one supply. It returns in full if README 7.3 is built.",
    ])
    footer(c, 2)


# ----------------------------------------------------------------- page 3
def page3(c):
    header(c, 3, "3. Sensor enclosure",
           "Everything here sits within a few centimetres of the AS3935. "
           "5 V arrives on the cable; 3.3 V is made locally.")
    y = H - M - 58

    jw = 1.25 * inch
    jpins = [("5v", "1  5V"), ("gnd", "2  GND"), ("sclk", "3  SCLK"), ("gnd2", "6  GND"),
             ("mosi", "4  MOSI"), ("miso", "5  MISO"), ("cs", "7  CS"), ("irq", "8  IRQ")]
    ybox = y - 64                       # leave a band above for the power chain
    jrows, (jx, jy, _, jh) = pinbox(c, M, ybox, jw, "RJ45 jack", jpins)

    sw = 1.85 * inch
    sx = W - M - sw
    spins = [("vdd", "VDD  3.3 V"), ("gnd", "GND"), ("sclk", "SCLK"), ("gnd2", "GND"),
             ("mosi", "MOSI"), ("miso", "MISO"), ("cs", "CS"), ("irq", "IRQ")]
    srows, _ = pinbox(c, sx, ybox, sw, "SEN-39003 (AS3935)", spins, right=True)

    # power chain lives in the band above the pin boxes, elbowed in and out
    rw = 2.45 * inch
    rx = (W - rw) / 2
    rh = 56
    rtop = y + 2
    box(c, rx, rtop - rh, rw, rh, "Local 3.3 V rail", [
        "100 ohm  >  10-47 uF  >  LDO",
        "  MCP1700-3302E/TO",
        "  out: 1 uF || 100 nF at the pin",
    ], titlesize=9)
    rmid = rtop - rh / 2 - 4

    elbow(c, jx + jw, jrows["5v"], rx, rmid, "W11  5 V", RED)
    elbow(c, rx + rw, rmid, sx, srows["vdd"], "W13  3.3 V", RED)
    for key, lbl, col in (("gnd", "W12 / W19  GND", BLACK_W), ("sclk", "W14  SCLK", BLUE),
                          ("gnd2", "GND", BLACK_W), ("mosi", "W15  MOSI", BLUE),
                          ("miso", "W16  MISO", BLUE), ("cs", "W17  CS", BLUE),
                          ("irq", "W18  IRQ", GREEN)):
        hwire(c, jx + jw, sx, jrows[key], lbl, col)

    c.setFillColor(AMBER); c.setFont("Helvetica-Bold", 8)
    c.drawString(M, jy - 16, "SI strapped to GND at the sensor board - selects SPI. Not carried on the cable.")

    ny = jy - 36
    ny = note(c, M, ny, 0, "Why a linear regulator, and why here", [
        "A switching regulator would put a 100 kHz - 1 MHz noise source centimetres from a 500 kHz",
        "magnetic antenna: the worst possible place for one. A linear regulator has no switching node,",
        "and at under 1 mA the wasted heat is nothing.",
        "The E suffix is the -40/+125 C grade, required for a ~52 C attic. The 1 uF output cap is",
        "REQUIRED for MCP1700 stability, not optional.",
    ])
    ny = note(c, M, ny - 10, 0, "The LDO does NOT replace the passives", [
        "LDO power-supply rejection is strong at low frequency - droop, WiFi burst sag - and is",
        "largely gone by 500 kHz. The LDO handles what the cable delivers at low frequency; the RC",
        "and the ceramics handle the band the AS3935 actually cares about. Neither suffices alone.",
    ], accent=AMBER)
    note(c, M, ny - 10, 0, "Set data_rate: 200kHz in the YAML", [
        "as3935_spi inherits the standard SPI device schema and DEFAULTS TO 1 MHz. At 200 kHz",
        "reflections over a few metres stop mattering; traffic is a few single-byte reads per event.",
        "IRQ is level-read in loop(), so cable capacitance cannot cost an interrupt.",
    ], accent=GREEN)
    footer(c, 3)


# ----------------------------------------------------------------- page 4
def page4(c):
    header(c, 4, "4. Wire list and bring-up",
           "Wire numbers match pages 2 and 3.")
    y = H - M - 52

    rows = [
        ("W1",  "USB brick +5 V",     "ESP32 5V / VIN",    "red",   "<=1 m, 20-24 AWG"),
        ("W2",  "USB brick GND",      "ESP32 GND",         "black", "with W1"),
        ("W3",  "ESP32 5V",           "RJ45 pin 1",        "red",   "w/orange"),
        ("W4",  "ESP32 GND",          "RJ45 pin 2",        "black", "orange"),
        ("W5",  "ESP32 GPIO18 SCLK",  "RJ45 pin 3",        "blue",  "w/green"),
        ("W6",  "ESP32 GND",          "RJ45 pin 6",        "black", "green - SCLK return"),
        ("W7",  "ESP32 GPIO23 MOSI",  "RJ45 pin 4",        "blue",  "blue"),
        ("W8",  "ESP32 GPIO19 MISO",  "RJ45 pin 5",        "blue",  "w/blue"),
        ("W9",  "ESP32 GPIO5 CS",     "RJ45 pin 7",        "blue",  "w/brown"),
        ("W10", "ESP32 GPIO4 IRQ",    "RJ45 pin 8",        "green", "brown"),
        ("W11", "RJ45 pin 1",         "100 ohm -> LDO in", "red",   "sensor box"),
        ("W12", "RJ45 pins 2 + 6",    "LDO GND / star",    "black", "sensor box"),
        ("W13", "LDO out 3.3 V",      "sensor VDD",        "red",   "caps at the pin"),
        ("W14", "RJ45 pin 3",         "sensor SCLK",       "blue",  ""),
        ("W15", "RJ45 pin 4",         "sensor MOSI",       "blue",  ""),
        ("W16", "RJ45 pin 5",         "sensor MISO",       "blue",  ""),
        ("W17", "RJ45 pin 7",         "sensor CS",         "blue",  ""),
        ("W18", "RJ45 pin 8",         "sensor IRQ",        "green", ""),
        ("W19", "sensor GND",         "LDO GND / star",    "black", "SI strapped here"),
    ]
    cols = [M, M + 0.5 * inch, M + 2.05 * inch, M + 3.6 * inch, M + 4.6 * inch]
    c.setFont("Helvetica-Bold", 8.2)
    c.setFillColor(INK)
    for cx, t in zip(cols, ("#", "From", "To", "Colour", "Note")):
        c.drawString(cx, y, t)
    c.setStrokeColor(RULE)
    c.line(M, y - 4, W - M, y - 4)
    yy = y - 15
    c.setFont("Helvetica", 8)
    for n, a, b, col, nt in rows:
        c.setFillColor(INK)
        c.drawString(cols[0], yy, n)
        c.drawString(cols[1], yy, a)
        c.drawString(cols[2], yy, b)
        c.setFillColor({"red": RED, "black": BLACK_W, "blue": BLUE, "green": GREEN}[col])
        c.drawString(cols[3], yy, col)
        c.setFillColor(MUTED)
        c.drawString(cols[4], yy, nt)
        yy -= 11.2

    ny = yy - 14
    ny = note(c, M, ny, 0, "Bring-up, in order", [
        "1.  Assemble both boxes; connect with the SHORTEST patch cable.",
        "2.  Measure 5 V at the ESP32 5V pin DURING WiFi activity, not at idle. Want >4.7 V.",
        "3.  Measure 3.3 V at the sensor VDD pin, at the far end, after the LDO.",
        "4.  Verify tuning capacitance OVER SERIAL - the one check WiFi cannot do (README 12.1).",
        "5.  Confirm the sensor responds to the SEN-39002 emulator. Expect disturbers, not lightning.",
        "6.  Platform-validity test: survey, handle the build, survey again. Rates must not move.",
        "7.  Only then mount, and run the distance sweep at 0.3 / 1 / 2 / 3 m.",
    ])
    note(c, M, ny - 8, 0, "Step 6 is not optional", [
        "The previous breadboard build's interference floor fell by two thirds when it was touched,",
        "and nobody noticed for thirteen hours of apparently stable data. A platform that moves when",
        "handled cannot measure anything else. If the rates shift, fix the mechanics before going on.",
    ], accent=AMBER)
    footer(c, 4)


def main():
    c = canvas.Canvas(OUT, pagesize=letter)
    c.setTitle("AS3935 lightning detector node - revision 2 wiring")
    c.setAuthor("as3935_lightning_detector")
    for fn in (page1, page2, page3, page4):
        fn(c)
        c.showPage()
    c.save()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
