#!/usr/bin/env python3
"""Regenerate loop-rotator-setup.pdf -- wiring and setup for the motorised
MLA-30+ direction-finding loop on gpiopi (docs/sdr-interference-hunting.md).

    python3 make-loop-rotator-setup.py      # needs reportlab

This script is the source of truth for the drawing; edit it, re-run it, commit
both. The software side is `loop-rotator`, puppet-managed on gpiopi
(privatepuppet: modules/local/privatepuppet/files/gpiopi/loop_rotator.py); the
pins and step angle here must match its DEFAULT_PINS and DEG_PER_HALFSTEP.

Visual language follows make-wiring-diagram.py. Not part of the AS3935 node's
drawing set, so it carries its own date stamp rather than DRAWING-VERSION.
"""
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

OUT = "loop-rotator-setup.pdf"
VERSION = "2026-10-15"
W, H = letter
M = 0.6 * inch

INK      = HexColor("#1a1a1a")
MUTED    = HexColor("#6b6b6b")
RULE     = HexColor("#c8c8c8")
BOXFILL  = HexColor("#f4f4f2")
WHITE    = HexColor("#ffffff")
RED      = HexColor("#b3261e")   # 12 V
BLACK_W  = HexColor("#333333")   # ground
BLUE     = HexColor("#1a5fb4")   # logic / GPIO
GREEN    = HexColor("#2c6e49")   # motor coils
PURPLE   = HexColor("#6c3483")   # RF / coax / USB
AMBER    = HexColor("#8a5a00")   # warnings
WOOD     = HexColor("#e9dcc3")
PVC      = HexColor("#e6e9ee")
STEEL    = HexColor("#b9bec6")

# Minebea 17PM-K077BP03CN pigtail colours (MPJA 33356MS data sheet).
MOTOR_RED, MOTOR_YEL = HexColor("#c0392b"), HexColor("#b7950b")
MOTOR_ORG, MOTOR_BLU = HexColor("#d35400"), HexColor("#1f4e9c")

PAGES = 4
TITLE = "MLA-30+ loop rotator - gpiopi"


# ------------------------------------------------------------------ helpers
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
    c.drawString(M, M + 11, "Print at 100% / actual size.")
    c.drawRightString(W - M, M + 11, "Page %d of %d" % (page, PAGES))
    c.setFont("Helvetica-Bold", 7.6)
    c.setFillColor(INK)
    c.drawCentredString(W / 2, M + 11, "DRAWING DATED " + VERSION)


def box(c, x, y, w, h, title, lines=(), fill=BOXFILL, titlesize=10, accent=INK):
    c.setFillColor(fill)
    c.setStrokeColor(accent)
    c.setLineWidth(1.1)
    c.roundRect(x, y, w, h, 5, stroke=1, fill=1)
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", titlesize)
    c.drawString(x + 8, y + h - 15, title)
    c.setFont("Helvetica", 8.1)
    ty = y + h - 28
    for ln in lines:
        c.setFillColor(MUTED if ln.startswith("  ") else INK)
        c.drawString(x + 8, ty, ln.strip() if ln.startswith("  ") else ln)
        ty -= 10.2
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
        c.setFont("Helvetica", 6.8)
        c.setFillColor(MUTED)
        c.drawString(x + 8, ytop - 26, sub)
    rows = []
    ry = ytop - pad - 8
    for label, colour in pins:
        c.setFillColor(colour)
        c.setFont("Helvetica-Bold" if colour is not MUTED else "Helvetica", 8.3)
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


def hwire(c, x1, x2, y, label, colour=INK, ends=True, size=7.2):
    c.setStrokeColor(colour)
    c.setLineWidth(1.3)
    c.line(x1, y, x2, y)
    if ends:
        dot(c, x1, y, colour)
        dot(c, x2, y, colour)
    c.setFillColor(colour)
    c.setFont("Helvetica-Bold", size)
    c.drawCentredString((x1 + x2) / 2, y + 3.5, label)


def poly(c, pts, colour=INK, wd=1.4, label=None, lpos=None, dash=None, ends=True):
    c.setStrokeColor(colour)
    c.setLineWidth(wd)
    if dash:
        c.setDash(*dash)
    for a, b in zip(pts, pts[1:]):
        c.line(a[0], a[1], b[0], b[1])
    c.setDash()
    if ends:
        dot(c, pts[0][0], pts[0][1], colour)
        dot(c, pts[-1][0], pts[-1][1], colour)
    if label:
        c.setFillColor(colour)
        c.setFont("Helvetica-Bold", 7.2)
        lx, ly = lpos if lpos else ((pts[0][0] + pts[-1][0]) / 2,
                                    (pts[0][1] + pts[-1][1]) / 2)
        c.drawString(lx, ly, label)


def vres(c, x, ytop, ybot, label="", sub=""):
    """Resistor hanging vertically from ytop to ybot."""
    mid = (ytop + ybot) / 2
    c.setStrokeColor(INK)
    c.setLineWidth(1.3)
    c.line(x, ytop, x, mid + 6)
    c.line(x, mid - 6, x, ybot)
    c.setFillColor(WHITE)
    c.rect(x - 3.5, mid - 6, 7, 12, stroke=1, fill=1)
    dot(c, x, ytop, INK)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 6.8)
    c.drawRightString(x - 6, mid - 2, label + (" " + sub if sub else ""))


def gnd(c, x, y, colour=BLACK_W):
    """Ground symbol whose top is at (x, y)."""
    c.setStrokeColor(colour)
    c.setLineWidth(1.3)
    c.line(x, y, x, y - 4)
    for i, hw in enumerate((7, 4.5, 2)):
        c.line(x - hw, y - 4 - i * 2.6, x + hw, y - 4 - i * 2.6)


def note(c, x, y, title, lines, accent=INK, size=8.1, lead=10.2):
    c.setStrokeColor(accent)
    c.setLineWidth(2)
    c.line(x, y, x, y - (len(lines) * lead + 14))
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 7, y - 9, title)
    c.setFillColor(INK)
    c.setFont("Helvetica", size)
    ty = y - 22
    for ln in lines:
        if ln.startswith("$ "):
            c.setFont("Courier", size - 0.3)
            c.drawString(x + 15, ty, ln[2:])
            c.setFont("Helvetica", size)
        else:
            c.drawString(x + 7, ty, ln)
        ty -= lead
    return ty


def table(c, x, y, heads, rows, widths, size=7.6, headsize=8):
    c.setFont("Helvetica-Bold", headsize)
    c.setFillColor(INK)
    cx = x
    for i, hd in enumerate(heads):
        c.drawString(cx, y, hd)
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
        y -= size + 3.4
    return y


def checkbox(c, x, y):
    c.setStrokeColor(INK)
    c.setLineWidth(0.9)
    c.rect(x, y - 1.5, 7, 7, stroke=1, fill=0)


def checklist(c, x, y, title, items, width, size=8.0, lead=10.0):
    """Numbered tick-box steps. An item is a string or (string, [code lines])."""
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(x, y, title)
    y -= 15
    for item in items:
        text, code = (item, []) if isinstance(item, str) else item
        if text:
            checkbox(c, x, y)
        else:
            y += 3.5   # code continuing the step above

        c.setFont("Helvetica", size)
        c.setFillColor(INK)
        for ln in wrap(c, text, "Helvetica", size, width - 14):
            c.drawString(x + 12, y, ln)
            y -= lead
        for ln in code:
            c.setFont("Courier", size - 0.4)
            c.setFillColor(BLUE)
            c.drawString(x + 22, y, ln)
            y -= lead
        y -= 3.5
    return y


def wrap(c, text, font, size, width):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if c.stringWidth(trial, font, size) <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


# ------------------------------------------------------------------- page 1
def page1(c):
    header(c, "Overview and parts",
           "A stepper turns the loop so gpiopi can take null bearings unattended "
           "(sdr-interference-hunting.md).")

    top = H - M - 44
    bw, bh = 140, 62
    gap = (W - 2 * M - 3 * bw) / 2
    col = [M, M + bw + gap, M + 2 * (bw + gap)]
    row = [top - bh, top - bh - 112, top - bh - 224]

    box(c, col[0], row[0], bw, bh, "MLA-30+ active loop",
        ["Receive-only magnetic loop,", "amplifier at the loop base.", "  on the PVC mast"],
        accent=PURPLE)
    box(c, col[1], row[0], bw, bh, "USB bias-tee injector",
        ["From the MLA-30+ kit: puts DC", "up the coax to the amplifier.",
         "  V4's own bias-tee stays OFF"], accent=PURPLE)
    box(c, col[2], row[0], bw, bh, "RTL-SDR Blog V4",
        ["R828D, HF via upconverter.", "rtl_power logs band power", "  verified genuine 2026-10-13"],
        accent=PURPLE)
    box(c, col[1], row[1], bw, bh, "USB battery bank",
        ["Powers the injector only.", "A USB wall charger is a", "  candidate noise source"],
        accent=PURPLE)
    box(c, col[2], row[1], bw, bh, "gpiopi (Raspberry Pi 4)",
        ["loop-rotator (puppet) drives", "GPIO 12/13/22/27; runs as pi.",
         "  screw-terminal GPIO breakout"], accent=BLUE)
    box(c, col[0], row[2], bw, bh, "Minebea NEMA 17 stepper",
        ["17PM-K077BP03CN (33356MS)", "1.8 deg, 34 ohm, 10.2 V / 0.3 A",
         "  half-stepped: 0.9 deg per step"], accent=GREEN)
    box(c, col[1], row[2], bw, bh, "L298 module (34652MP)",
        ["Plain H-bridge, voltage drive:", "held position = DC, no chopper.",
         "  J-1 jumper REMOVED"], accent=GREEN)
    box(c, col[2], row[2], bw, bh, "12 V DC wall wart",
        [">= 1 A, barrel plug.", "Transformer type preferred;", "  test any switcher (page 4)"],
        accent=RED)

    mid = lambda r: r + bh / 2
    # RF chain
    poly(c, [(col[0] + bw, mid(row[0])), (col[1], mid(row[0]))], PURPLE, 1.6,
         "coax", (col[0] + bw + gap / 2 - 8, mid(row[0]) + 4))
    poly(c, [(col[1] + bw, mid(row[0])), (col[2], mid(row[0]))], PURPLE, 1.6,
         "coax", (col[1] + bw + gap / 2 - 8, mid(row[0]) + 4))
    poly(c, [(col[1] + bw / 2, row[1] + bh), (col[1] + bw / 2, row[0])], PURPLE, 1.4,
         "USB 5 V", (col[1] + bw / 2 + 5, row[1] + bh + 10))
    poly(c, [(col[2] + bw / 2, row[0]), (col[2] + bw / 2, row[1] + bh)], PURPLE, 1.4,
         "USB", (col[2] + bw / 2 + 5, row[1] + bh + 10))
    # control and power
    poly(c, [(col[2] + 30, row[1]), (col[2] + 30, row[2] + bh + 26),
             (col[1] + bw - 30, row[2] + bh + 26), (col[1] + bw - 30, row[2] + bh)],
         BLUE, 1.6, "IN1-IN4 + GND (5 wires)", (col[1] + bw - 22, row[2] + bh + 30))
    poly(c, [(col[2], mid(row[2])), (col[1] + bw, mid(row[2]))], RED, 1.6,
         "12 V", (col[1] + bw + gap / 2 - 8, mid(row[2]) + 4))
    poly(c, [(col[1], mid(row[2])), (col[0] + bw, mid(row[2]))], GREEN, 1.6,
         "4 wires", (col[0] + bw + gap / 2 - 13, mid(row[2]) + 4))
    # mechanical
    poly(c, [(col[0] + bw / 2, row[2] + bh), (col[0] + bw / 2, row[0])], MUTED, 2.2,
         None, dash=(5, 3), ends=False)
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Oblique", 7.6)
    c.drawString(col[0] + bw / 2 + 6, mid(row[1]) + 8, "1\" PVC mast:")
    c.drawString(col[0] + bw / 2 + 6, mid(row[1]) - 2, "the motor turns the")
    c.drawString(col[0] + bw / 2 + 6, mid(row[1]) - 12, "whole loop (page 3)")

    y = row[2] - 26
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(M, y, "Parts")
    y = table(c, M, y - 16,
              ["Qty", "Part", "Source / notes"],
              [["1", "Minebea 17PM-K077BP03CN NEMA 17 stepper", "MPJA 33356MS (on hand)"],
               ["1", "L298 stepper / DC driver module", "MPJA 34652MP (on hand)"],
               ["4", "10 kohm resistor, 1/4 W", "IN1-IN4 pull-downs (page 2)"],
               ["1", "12 V DC >= 1 A supply, barrel plug + screw-terminal adapter",
                "e.g. MPJA 19452PL plug-to-terminal"],
               ["1", "Flexible beam coupler, 5 mm to 8 mm (or 5/16\")", "motor shaft to mast plug"],
               ["1", "Hardwood dowel, 1\" x 2-3\", and 8 mm or 5/16\" bolt / rod",
                "plug for the bottom of the mast"],
               ["1", "NEMA 17 L-bracket, M3 x 6-8 mm screws", "motor to base board"],
               ["1", "Base board (plywood) + 2 spacer blocks (2x4 offcuts)", "page 3"],
               ["1", "Hose clamp to fit 1\" PVC", "thrust collar on top of the 4x4"],
               ["2-3", "Clip-on ferrite cores for the coax", "at the amplifier and the mast foot"],
               ["~6", "Hook-up wire (22-24 AWG), ideally 5 colours", "Pi to L298, and ground"]],
              [30, 270, 225])

    note(c, M, y - 10, "Three things that break hardware", [
        "1. J-1 on the L298 module must be REMOVED. It ties the logic 5 V rail to the motor supply;",
        "    fitted with 12 V applied, it puts 12 V into the L298's logic and out of its +5V terminal.",
        "2. The L298 module's +5V terminal is an OUTPUT (78M05 regulator). Connect nothing to it,",
        "    and never connect the Pi's 5 V anywhere on the module.",
        "3. Do not unplug the motor while it is powered: the L298 is driving 60 mH coils.",
    ], accent=RED)
    footer(c, 1)


# ------------------------------------------------------------------- page 2
def page2(c):
    header(c, "Electrical wiring",
           "Every line is one physical wire, numbered W1-W11 to match the schedule below.")

    top = H - M - 44
    rowh = 32
    pi_rows, (px, py, pw, ph) = pinbox(
        c, M, top, 128, "gpiopi GPIO breakout",
        [("GPIO12   (pin 32)", BLUE), ("GPIO13   (pin 33)", BLUE),
         ("GPIO22   (pin 15)", BLUE), ("GPIO27   (pin 13)", BLUE),
         ("GND       (pin 34)", BLACK_W)],
        rowh=rowh, pad=34, sub="BCM numbers; physical pin in ( )")
    lx = W - M - 250
    l_rows, (lbx, lby, lbw, lbh) = pinbox(
        c, lx, top, 112, "L298 header",
        [("IN1", BLUE), ("IN2", BLUE), ("IN3", BLUE), ("IN4", BLUE), ("GND (TS-1)", BLACK_W)],
        rowh=rowh, pad=34, sub="ENA / ENB jumpers ON")

    x1, x2 = px + pw, lbx
    names = ["W1", "W2", "W3", "W4"]
    rx = x2 - 22
    for i, (yp, yl) in enumerate(zip(pi_rows[:4], l_rows[:4])):
        hwire(c, x1, x2, yp, names[i] + "    IN%d" % (i + 1), BLUE)
        vres(c, rx, yp, yp - 19, "R%d" % (i + 1), "10k")
        gnd(c, rx, yp - 19)
    hwire(c, x1, x2, pi_rows[4], "W5    GND (common)", BLACK_W)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7)

    # L298 power and motor side
    tx = lbx + lbw + 18
    t_rows, (tbx, tby, tbw, tbh) = pinbox(
        c, tx, top, W - M - tx, "L298 terminals",
        [("TS-1  +12V", RED), ("TS-1  GND", BLACK_W), ("TS-1  +5V   NC", MUTED),
         ("OUT1", GREEN), ("OUT2", GREEN), ("OUT3", GREEN), ("OUT4", GREEN)],
        rowh=22, pad=34, sub="screw terminals")
    c.setFillColor(AMBER)
    c.setFont("Helvetica-Bold", 7.6)
    c.drawString(tbx + 8, tby - 12, "J-1: REMOVED")
    c.setFont("Helvetica", 7)
    c.setFillColor(MUTED)
    c.drawString(tbx + 8, tby - 22, "+5V is the regulator's output.")

    # supply and motor below
    sy = py - 30
    s_rows, (sbx, sby, sbw, sbh) = pinbox(
        c, M, sy, 128, "12 V wall wart",
        [("+12 V", RED), ("GND / -", BLACK_W)], rowh=22, pad=34, sub=">= 1 A, centre +")
    m_rows, (mbx, mby, mbw, mbh) = pinbox(
        c, M + 210, sy, 150, "Minebea NEMA 17",
        [("red      coil A", MOTOR_RED), ("yellow   coil A'", MOTOR_YEL),
         ("orange   coil B", MOTOR_ORG), ("blue     coil B'", MOTOR_BLU)],
        rowh=22, pad=34, sub="4-wire pigtail, bipolar")

    # W6, W7: supply to TS-1
    poly(c, [(sbx + sbw, s_rows[0]), (sbx + sbw + 40, s_rows[0]),
             (sbx + sbw + 40, sy + 18), (tbx - 9, sy + 18), (tbx - 9, t_rows[0]),
             (tbx, t_rows[0])], RED, 1.4, "W6", (sbx + sbw + 8, s_rows[0] + 3))
    poly(c, [(sbx + sbw, s_rows[1]), (sbx + sbw + 52, s_rows[1]),
             (sbx + sbw + 52, sy + 8), (tbx - 5, sy + 8), (tbx - 5, t_rows[1]),
             (tbx, t_rows[1])], BLACK_W, 1.4, "W7", (sbx + sbw + 8, s_rows[1] + 3))
    # W8-W11: OUTn to motor
    for i, (col, wname) in enumerate(zip((MOTOR_RED, MOTOR_YEL, MOTOR_ORG, MOTOR_BLU),
                                         ("W8", "W9", "W10", "W11"))):
        xr = tbx + tbw + 10 + i * 0
        jog = mbx + mbw + 14 + i * 12
        poly(c, [(tbx + tbw, t_rows[3 + i]), (W - M + 4 + i * 4, t_rows[3 + i]),
                 (W - M + 4 + i * 4, m_rows[i] - 0), (mbx + mbw, m_rows[i])],
             col, 1.4, wname, (jog + 50, m_rows[i] + 3), ends=True)

    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7)
    c.drawString(M, min(mby, sby) - 12,
                 "Every ground symbol is this one common ground: Pi GND = L298 GND = supply -. "
                 "R1-R4 sit at the L298 end of W1-W4.")

    # schedule
    y = min(mby, sby) - 36
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(M, y, "Wire schedule")
    y = table(c, M, y - 16,
              ["Wire", "From", "To", "Notes"],
              [["W1", "gpiopi GPIO12 (pin 32)", "L298 IN1", "coil A side 1"],
               ["W2", "gpiopi GPIO13 (pin 33)", "L298 IN2", "coil A side 2"],
               ["W3", "gpiopi GPIO22 (pin 15)", "L298 IN3", "coil B side 1"],
               ["W4", "gpiopi GPIO27 (pin 13)", "L298 IN4", "coil B side 2"],
               ["W5", "gpiopi GND (pin 34; or 6/9/14/20/25/30/39)", "L298 TS-1 GND",
                ("REQUIRED: logic reference", AMBER)],
               ["W6", "wall wart +12 V", "L298 TS-1 +12V", "check polarity with a meter"],
               ["W7", "wall wart GND", "L298 TS-1 GND", "shares the terminal with W5"],
               ["W8", "L298 OUT1", "motor red", "OUT1/OUT2 = 'OUT A' terminal"],
               ["W9", "L298 OUT2", "motor yellow", ""],
               ["W10", "L298 OUT3", "motor orange", "OUT3/OUT4 = 'OUT B' terminal"],
               ["W11", "L298 OUT4", "motor blue", ""],
               ["R1-R4", "10 kohm from each of IN1-IN4", "to GND", "at the L298 end (note below)"]],
              [42, 215, 110, 160], size=7.3)

    note(c, M, y - 8, "Why the pull-down resistors", [
        "The L298 module has no pull resistors on IN1-IN4 (MPJA schematic), and an undriven L298",
        "input can read high and switch a coil on. gpiopi pulls the pins down at boot (config.txt)",
        "and loop-rotator re-applies that on every exit, but R1-R4 keep the coils off even when the",
        "Pi is off, rebooting or unplugged. Fit them at the L298 end of W1-W4 where you can.",
    ], accent=BLUE, size=7.8, lead=9.6)
    footer(c, 2)


# ------------------------------------------------------------------- page 3
def page3(c):
    header(c, "Mechanical setup",
           "Side view, not to scale. The 4x4's hole stays the bearing; the motor only turns the mast.")

    cx = M + 150             # mast centre line
    floor = M + 178
    # base board
    c.setFillColor(WOOD)
    c.setStrokeColor(INK)
    c.setLineWidth(1)
    c.rect(cx - 125, floor, 250, 12, stroke=1, fill=1)
    # spacers
    sp_h = 70
    for sx in (cx - 115, cx + 75):
        c.rect(sx, floor + 12, 40, sp_h, stroke=1, fill=1)
    # 4x4 block, with the through hole
    blk_y = floor + 12 + sp_h
    blk_h = 62
    c.rect(cx - 115, blk_y, 230, blk_h, stroke=1, fill=1)
    c.setFillColor(WHITE)
    c.rect(cx - 13, blk_y, 26, blk_h, stroke=0, fill=1)
    c.setDash(2, 2)
    c.line(cx - 13, blk_y, cx - 13, blk_y + blk_h)
    c.line(cx + 13, blk_y, cx + 13, blk_y + blk_h)
    c.setDash()
    # motor on its bracket
    mot_top = floor + 12 + 40
    c.setFillColor(STEEL)
    c.rect(cx - 21, floor + 12, 42, 40, stroke=1, fill=1)
    c.rect(cx - 30, floor + 12, 60, 4, stroke=1, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(cx, floor + 30, "NEMA 17")
    # shaft, coupler, rod
    c.setFillColor(STEEL)
    c.rect(cx - 2.5, mot_top, 5, 8, stroke=1, fill=1)
    c.setFillColor(HexColor("#9aa3ad"))
    c.rect(cx - 8, mot_top + 8, 16, 18, stroke=1, fill=1)
    pipe_bot = mot_top + 34
    c.setFillColor(STEEL)
    c.rect(cx - 3, mot_top + 26, 6, 20, stroke=1, fill=1)
    # mast with the dowel plug in its foot
    pipe_top = H - M - 175
    c.setFillColor(PVC)
    c.rect(cx - 12, pipe_bot, 24, pipe_top - pipe_bot, stroke=1, fill=1)
    c.setFillColor(WOOD)
    c.rect(cx - 10, pipe_bot, 20, 26, stroke=1, fill=1)
    c.setFillColor(STEEL)
    c.rect(cx - 3, pipe_bot, 6, 14, stroke=1, fill=1)
    # hose clamp collar resting on the block
    c.rect(cx - 17, blk_y + blk_h, 34, 6, stroke=1, fill=1)
    # loop, edge-on, and its amplifier
    c.setStrokeColor(PURPLE)
    c.setLineWidth(2.2)
    c.ellipse(cx - 70, pipe_top - 10, cx + 70, pipe_top + 120, stroke=1, fill=0)
    c.setFillColor(HexColor("#d8cfe3"))
    c.setStrokeColor(INK)
    c.setLineWidth(1)
    c.rect(cx - 14, pipe_top - 14, 28, 18, stroke=1, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 6.4)
    c.drawCentredString(cx, pipe_top - 8, "amp")
    # coax: down the left of the mast, away at the block, slack to the floor
    c.setStrokeColor(PURPLE)
    c.setLineWidth(1.6)
    c.line(cx - 14, pipe_top - 10, cx - 18, pipe_top - 18)
    c.line(cx - 18, pipe_top - 18, cx - 18, blk_y + blk_h + 30)
    p = c.beginPath()
    p.moveTo(cx - 18, blk_y + blk_h + 30)
    p.curveTo(cx - 60, blk_y + blk_h + 10, cx - 100, blk_y + blk_h + 70, cx - 125, blk_y + blk_h + 20)
    p.curveTo(cx - 140, blk_y, cx - 135, floor + 40, cx - 145, floor + 6)
    c.drawPath(p, stroke=1, fill=0)
    c.setFillColor(HexColor("#555555"))
    for fy in (pipe_top - 34, blk_y + blk_h + 34):
        c.roundRect(cx - 23, fy, 10, 14, 2, stroke=0, fill=1)

    # callouts: fixed slots in the same top-to-bottom order as their features,
    # so no two leader lines cross
    tx = M + 268
    callouts = [
        ((cx + 66, pipe_top + 70), PURPLE, ["MLA-30+ loop",
            "Turns with the mast. Keep metal", "a loop diameter away from it."]),
        ((cx - 13, pipe_top - 27), INK, ["Ferrite clip at the amplifier",
            "Stops the coax acting as an antenna,", "which fills in the nulls."]),
        ((cx + 12, (pipe_top + pipe_bot) / 2 + 30), INK, ["1\" PVC mast",
            "Coax taped flat along it. Motor as far", "below the loop as it allows (>= 0.5 m)."]),
        ((cx - 110, blk_y + blk_h + 40), PURPLE, ["Coax service loop",
            "Leaves the mast at right angles to the", "loop; slack for +/-190 deg of travel."]),
        ((cx + 17, blk_y + blk_h + 3), INK, ["Hose clamp = thrust collar",
            "Rests on the 4x4 and carries the", "mast's weight, not the motor bearings."]),
        ((cx + 100, blk_y + blk_h - 14), INK, ["4x4, hole drilled THROUGH",
            "The hole keeps the mast upright", "and is its bearing."]),
        ((cx + 10, pipe_bot + 18), INK, ["Dowel plug + 8 mm rod",
            "1\" hardwood dowel glued / pinned in", "the mast foot, rod centred in it."]),
        ((cx + 8, mot_top + 17), INK, ["Flexible beam coupler, 5 to 8 mm",
            "Takes up misalignment between the", "hole and the motor; carries torque only."]),
        ((cx + 95, floor + 52), INK, ["Spacers",
            "Tall enough for coupler + plug", "(2x4 offcuts on edge, ~3.5\")."]),
        ((cx + 30, floor + 14), INK, ["Motor on a NEMA 17 L-bracket",
            "screwed to the base board, shaft", "centred under the hole."]),
    ]
    slot_top, slot_step = H - M - 52, 41
    for i, ((fx, fy), colour, lines) in enumerate(callouts):
        ty = slot_top - i * slot_step
        c.setStrokeColor(MUTED)
        c.setLineWidth(0.6)
        c.line(fx, fy, tx - 4, ty + 2)
        dot(c, fx, fy, MUTED, 1.4)
        c.setFillColor(colour)
        c.setFont("Helvetica-Bold", 7.6)
        c.drawString(tx, ty, lines[0])
        c.setFont("Helvetica", 7.2)
        c.setFillColor(INK)
        for j, ln in enumerate(lines[1:], start=1):
            c.drawString(tx, ty - j * 9, ln)

    # top view: angle convention
    import math
    ox, oy, r = W - M - 48, M + 268, 38
    c.setStrokeColor(INK)
    c.setLineWidth(1)
    c.setFillColor(BOXFILL)
    c.circle(ox, oy, r, stroke=1, fill=1)
    c.setFont("Helvetica", 6.8)
    c.setFillColor(INK)
    for deg in range(0, 360, 15):
        a = math.radians(90 - deg)
        inner = r - (7 if deg % 90 == 0 else 4)
        c.line(ox + inner * math.cos(a), oy + inner * math.sin(a),
               ox + r * math.cos(a), oy + r * math.sin(a))
        if deg % 90 == 0:
            c.drawCentredString(ox + (r + 9) * math.cos(a), oy + (r + 9) * math.sin(a) - 2,
                                "%d" % deg)
    c.setStrokeColor(PURPLE)
    c.setLineWidth(3)
    c.line(ox, oy - r + 10, ox, oy + r - 10)
    c.setStrokeColor(MUTED)
    c.setLineWidth(1)
    c.setDash(3, 2)
    c.line(ox - r + 5, oy, ox + r - 5, oy)
    c.setDash()
    p = c.beginPath()
    p.arc(ox - r + 12, oy - r + 12, ox + r - 12, oy + r - 12, startAng=80, extent=-50)
    c.setStrokeColor(BLUE)
    c.setLineWidth(1.2)
    c.drawPath(p, stroke=1, fill=0)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawCentredString(ox - 10, oy - r - 22, "Top view: base plate")
    c.setFont("Helvetica", 7)
    c.setFillColor(MUTED)
    for i, ln in enumerate(["Angles increase clockwise (blue).", "Purple: loop plane at 0 deg.",
                            "Dashed: loop axis = null line."]):
        c.drawCentredString(ox - 10, oy - r - 32 - i * 8.5, ln)

    note(c, M, floor - 34, "Reading a bearing", [
        "A small loop nulls when it FACES the source: the source lies along the loop's axis (dashed),",
        "perpendicular to its plane. loop-rotator reports the base-plate angle of the null; the source is",
        "along the axis at that angle, in one of two opposite directions. Resolve which with a second",
        "bearing from another spot: the lines cross on the source. Note which way the loop plane points",
        "at 0 deg before the first sweep, so plate angles can be turned into compass bearings.",
    ], accent=PURPLE, size=7.8, lead=9.6)
    footer(c, 3)


# ------------------------------------------------------------------- page 4
def page4(c):
    header(c, "Bring-up and first sweep",
           "Tick each step. Commands run on gpiopi as pi (ssh gpiopi); no root needed.")
    colw = (W - 2 * M - 20) / 2
    x1, x2 = M, M + colw + 20
    y = H - M - 46
    y = checklist(c, x1, y, "A. Before any power", [
        "Meter the motor pigtail: red-yellow and orange-blue each about 34 ohm; red-orange open. "
        "If not, the coil pairs differ from page 2: find the pairs by resistance and wire each pair to one OUT terminal.",
        "J-1 removed from the L298 module. ENA and ENB jumpers fitted.",
        "R1-R4 (10k) fitted from IN1-IN4 to GND.",
        "Wall wart polarity checked with a meter before it goes into TS-1.",
    ], colw)
    y = checklist(c, x1, y - 4, "B. Power, motor not yet connected", [
        "Apply 12 V only. TS-1 +5V should read about 5 V; IN1-IN4 about 0 V; module LED on.",
        "Connect W1-W5 to gpiopi. IN1-IN4 still about 0 V.",
        "Power off, connect the motor (W8-W11), power on. The motor should be free to turn by hand.",
    ], colw)
    y = checklist(c, x1, y - 4, "C. Software", [
        ("Puppet has run on gpiopi since the loop-rotator commit:", ["which loop-rotator"]),
        ("Turn the loop to 0 on the base plate by hand, then:", ["loop-rotator zero",
                                                                  "loop-rotator goto 45"]),
        "Plate reads 45, turned clockwise? If it went to 315 instead:",
        ("Put it back and declare the direction reversed:", ["loop-rotator goto 0",
                                                             "loop-rotator zero --reverse"]),
        ("Back and forth a few times; it must come back to 0 exactly:",
         ["loop-rotator goto 180", "loop-rotator goto 0"]),
    ], colw)

    y2 = H - M - 46
    y2 = checklist(c, x2, y2, "D. Is the motor kit quiet?", [
        ("Log the AM band (Ctrl-C to stop):",
         ["rtl_power -f 520k:1720k:2k -g 20 -i 1 noise.csv"]),
        "Meanwhile, ~30 s each, noting the times: wart unplugged; wart plugged in, coils off; "
        "then coils holding, which only happens during a sweep's dwell:",
        ("", ["loop-rotator sweep --stop 0 --dwell 30"]),
        "The floor at a quiet channel (720 kHz) should not move between the three. "
        "If it does: ferrite on the DC lead, then another wart.",
    ], colw)
    y2 = checklist(c, x2, y2 - 4, "E. Calibration sweep on an AM station", [
        ("Two passes over 180 deg in 9 deg steps (about 9 minutes):",
         ["loop-rotator sweep --stop 180 --step 9 \\", "  --dwell 10 --passes 2 \\",
          "  --rtl-power ~/cal.csv"]),
        ("Then (the event log path is printed by the sweep):",
         ["loop-rotator analyze \\", "  --log ~/loop-rotator/sweep-*.log \\",
          "  --rtl ~/cal.csv --freq 680k \\", "  --freq 750k --ref 720k"]),
    ], colw)

    note(c, x2, y2 - 2, "What good looks like", [
        "Null depth over 20 dB, and both passes agree within a few deg.",
        "680 and 750 kHz null at similar angles if they are co-sited.",
        "Under ~10 dB: coax pickup. Add ferrites, re-route, repeat.",
        "Passes disagree: lost steps. Lower --rate, check the coupler.",
    ], accent=GREEN, size=7.8, lead=9.8)

    yb = min(y, y2 - 70) - 6
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(M, yb, "Troubleshooting")
    table(c, M, yb - 16, ["Symptom", "Likely cause", "Fix"], [
        ["Motor buzzes or twitches, does not turn", "A coil's pair split across OUT A / OUT B",
         "Re-pair by resistance (step A1)"],
        ["Turns the wrong way", "One coil's two wires swapped (harmless)", "zero --reverse (step C)"],
        ["Misses steps / passes disagree", "Too fast for the loop's inertia, or binding",
         "--rate 10; check coupler + collar"],
        ["L298 or motor hot after long holds", "Expected: ~6 W while holding",
         "Coils release after each command"],
        ["'position unknown'", "No zero recorded yet", "Set to 0 by hand; loop-rotator zero"],
        ["'another loop-rotator is running'", "A sweep is still going", "Wait, or stop it with Ctrl-C"],
        ["rtl_power: device busy / exited", "Another rtl_* program has the dongle",
         "Stop it; one user at a time"],
        ["All channels identical in analyze", "rtl_power span under ~1 MHz",
         "Keep the default 520k:1720k span"],
    ], [180, 190, 160], size=7.4)
    footer(c, 4)


def main():
    c = canvas.Canvas(OUT, pagesize=letter)
    c.setTitle("MLA-30+ loop rotator - wiring and setup")
    c.setAuthor("as3935_lightning_detector")
    for fn in (page1, page2, page3, page4):
        fn(c)
        c.showPage()
    c.save()
    print("wrote %s" % OUT)


if __name__ == "__main__":
    main()
