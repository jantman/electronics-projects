#!/usr/bin/env python3
"""Regenerate loop-rotator-dial.pdf -- a paper angle dial for the loop
rotator's base plate (see loop-rotator-setup.pdf, page 3).

    python3 make-loop-rotator-dial.py      # needs reportlab

Cut out the 1" centre hole, slit along the 180 deg cut line, slip it round the
PVC mast under the shaft collar and tape it to the plate. Angles increase
clockwise seen from above, matching loop-rotator, and 0 deg is where the line
through the loop's hole points when the rotator is zeroed.

Author: Jason Antman, 2026.
"""
import math

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm, inch
from reportlab.pdfgen import canvas

OUT = "loop-rotator-dial.pdf"
VERSION = "2026-11-07"
W, H = letter
M = 0.6 * inch

INK    = HexColor("#1a1a1a")
MUTED  = HexColor("#6b6b6b")
RULE   = HexColor("#c8c8c8")
BLUE   = HexColor("#1a5fb4")
PURPLE = HexColor("#6c3483")
AMBER  = HexColor("#8a5a00")

R_OUT = 3.5 * inch    # outer cut line: the plate allows no more than 3.5"
R_HOLE = 0.5 * inch   # 1" hole for the mast


def polar(cx, cy, r, deg):
    """Point at radius r and dial angle deg (0 at top, clockwise)."""
    a = math.radians(90 - deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def radial(c, cx, cy, deg, r1, r2):
    x1, y1 = polar(cx, cy, r1, deg)
    x2, y2 = polar(cx, cy, r2, deg)
    c.line(x1, y1, x2, y2)


def label(c, cx, cy, r, deg, text, font, size, colour):
    """Text centred at radius r, along the tangent; the bottom half is
    turned so it reads upright from the front of the plate."""
    x, y = polar(cx, cy, r, deg)
    c.saveState()
    c.translate(x, y)
    c.rotate(-deg + (180 if 90 <= deg < 270 else 0))
    c.setFont(font, size)
    c.setFillColor(colour)
    c.drawCentredString(0, -size * 0.35, text)
    c.restoreState()


def dial(c, cx, cy):
    # cut lines
    c.setStrokeColor(INK)
    c.setLineWidth(0.8)
    c.circle(cx, cy, R_OUT, stroke=1, fill=0)
    c.circle(cx, cy, R_HOLE, stroke=1, fill=0)
    c.setLineWidth(0.4)
    c.line(cx - 0.12 * inch, cy, cx + 0.12 * inch, cy)
    c.line(cx, cy - 0.12 * inch, cx, cy + 0.12 * inch)

    # graduations: 1 deg minor, 5 deg medium, 10 deg major
    rim = R_OUT - 0.04 * inch
    c.setStrokeColor(INK)
    for deg in range(360):
        if deg % 10 == 0:
            c.setLineWidth(0.9)
            length = 0.30 * inch
        elif deg % 5 == 0:
            c.setLineWidth(0.6)
            length = 0.20 * inch
        else:
            c.setLineWidth(0.35)
            length = 0.12 * inch
        radial(c, cx, cy, deg, rim - length, rim)
    c.setLineWidth(0.5)
    c.circle(cx, cy, rim - 0.30 * inch, stroke=1, fill=0)

    for deg in range(0, 360, 10):
        bold = deg % 90 == 0
        label(c, cx, cy, rim - 0.45 * inch, deg, "%d" % deg,
              "Helvetica-Bold" if bold else "Helvetica", 9.5 if bold else 8, INK)
    # loop-rotator's angles are signed, so the anticlockwise side also reads negative
    for deg in range(210, 360, 30):
        label(c, cx, cy, rim - 0.68 * inch, deg, "%d" % (deg - 360),
              "Helvetica", 6.5, BLUE)

    # zero: the hole ray
    c.setStrokeColor(PURPLE)
    c.setLineWidth(1.6)
    radial(c, cx, cy, 0, R_HOLE + 0.08 * inch, rim - 0.85 * inch)
    tip = polar(cx, cy, rim - 0.85 * inch, 0)
    c.setFillColor(PURPLE)
    p = c.beginPath()
    p.moveTo(tip[0], tip[1] + 0.02 * inch)
    p.lineTo(tip[0] - 0.07 * inch, tip[1] - 0.14 * inch)
    p.lineTo(tip[0] + 0.07 * inch, tip[1] - 0.14 * inch)
    p.close()
    c.drawPath(p, stroke=0, fill=1)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(cx + 0.1 * inch, cy + 1.75 * inch, "LINE THROUGH THE LOOP'S HOLE")
    c.drawString(cx + 0.1 * inch, cy + 1.62 * inch, "POINTS HERE AT ZERO")

    # slit: along 180, between the hole and the rim
    c.setStrokeColor(AMBER)
    c.setLineWidth(0.9)
    c.setDash(4, 2)
    radial(c, cx, cy, 180, R_HOLE, R_OUT)
    c.setDash()
    c.saveState()
    x, y = polar(cx, cy, 1.25 * inch, 180)
    c.translate(x + 0.09 * inch, y)
    c.rotate(90)
    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(AMBER)
    c.drawCentredString(0, 0, "SLIT HERE")
    c.restoreState()

    c.setFont("Helvetica", 7)
    c.setFillColor(MUTED)
    c.drawCentredString(cx, cy - 0.68 * inch, "1\" hole: cut out")
    c.drawString(cx + 0.85 * inch, cy + 1.02 * inch, "clockwise from above")
    c.setStrokeColor(MUTED)
    c.setLineWidth(0.7)
    p = c.beginPath()
    p.arc(cx - 1.05 * inch, cy - 1.05 * inch, cx + 1.05 * inch, cy + 1.05 * inch,
          startAng=70, extent=-40)
    c.drawPath(p, stroke=1, fill=0)
    ax, ay = polar(cx, cy, 1.05 * inch, 60)
    c.line(ax, ay, ax - 0.02 * inch, ay + 0.09 * inch)
    c.line(ax, ay, ax - 0.09 * inch, ay + 0.02 * inch)


def scale_check(c, x, y):
    """Bars to measure before cutting. A scaled print still reads the right
    angles, but the hole and outer diameter come out the wrong size."""
    c.setStrokeColor(INK)
    c.setLineWidth(0.8)
    c.line(x, y, x + 3 * inch, y)
    for i in range(4):
        c.line(x + i * inch, y, x + i * inch, y + 0.12 * inch)
    c.setFont("Helvetica", 7)
    c.setFillColor(INK)
    c.drawString(x, y - 10, "3 in")
    yc = y - 0.35 * inch
    c.line(x, yc, x + 5 * cm, yc)
    for i in range(6):
        c.line(x + i * cm, yc, x + i * cm, yc + 0.12 * inch)
    c.drawString(x, yc - 10, "5 cm")


def main() -> None:
    c = canvas.Canvas(OUT, pagesize=letter)
    c.setTitle("Loop rotator angle dial")
    c.setAuthor("Jason Antman")

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(M, H - M, "Loop rotator angle dial")
    c.setFont("Helvetica", 9)
    c.setFillColor(MUTED)
    c.drawRightString(W - M, H - M, "MLA-30+ loop rotator - gpiopi")
    c.setStrokeColor(RULE)
    c.setLineWidth(0.7)
    c.line(M, H - M - 9, W - M, H - M - 9)

    cx, cy = W / 2, H - M - 0.25 * inch - R_OUT
    dial(c, cx, cy)

    ytop = cy - R_OUT - 0.4 * inch
    scale_check(c, M, ytop)
    notes = [
        "1. Print at 100% / actual size. Check both bars above before cutting; the dial is 7\" across.",
        "2. Cut the outer circle and the 1\" hole. Slit along the dashed line at 180.",
        "3. Slip it round the mast under the shaft collar's bearing and tape it to the plate.",
        "4. The dial stays still and the mast turns, so add a pointer that turns with the mast: a",
        "   straw or stiff wire taped to the collar, reaching over the graduations, aligned with the",
        "   line through the loop's hole. Turn the loop to set 0 when you tape the dial down.",
        "5. Blue figures are loop-rotator's negative angles: goto -30 reads 330 on the dial.",
    ]
    c.setFont("Helvetica", 8.5)
    c.setFillColor(INK)
    for i, ln in enumerate(notes):
        c.drawString(M, ytop - 0.75 * inch - i * 11.5, ln)

    c.setStrokeColor(RULE)
    c.line(M, M + 22, W - M, M + 22)
    c.setFont("Helvetica-Bold", 7.6)
    c.setFillColor(INK)
    c.drawCentredString(W / 2, M + 11, "DRAWING DATED " + VERSION)
    c.showPage()
    c.save()
    print("wrote " + OUT)


if __name__ == "__main__":
    main()
