#!/usr/bin/env python3
"""
Ambient interference survey for the AS3935 lightning detector node.

Counts what the sensor reports when nothing is deliberately stimulating it, and
breaks it down by interrupt type. This is the instrument for the site survey in
README section 10 -- run it in each candidate location and rank the spots by the
ambient INT_L (false lightning) rate.

  RANK BY FALSE LIGHTNING, NOT BY DISTURBERS.
  Disturbers are the obvious metric and the wrong one: they are discarded by the
  component and never reach Home Assistant. A false INT_L publishes Storm Alert,
  Distance and Energy straight into HA and corrupts the data. See section 11.2.

Requires the node's logger at VERY_VERBOSE and a USB serial connection. The
runtime messages this parses come from loop(), so they DO stream over WiFi too --
but reading them over the network needs an ESPHome log client, whereas this only
needs pyserial. For an attic survey, a laptop and a long USB cable is usually the
path of least resistance.

  ./ambient-survey.py --minutes 10
  ./ambient-survey.py --port /dev/ttyUSB1 --minutes 60 --bucket 300

DISTINGUISHING REAL STRIKES FROM NOISE: local EMI reports 1.0 km (the "overhead"
bin). A genuinely distant storm reports a large distance. Any lightning event
whose distance is NOT 1.0 km is a candidate real detection -- cross-check the
timestamp against lightningmaps.org.

SAFETY: never have USB and the IRM-02-5 mains supply connected at the same time.
See README section 12.
"""

import argparse
import collections
import re
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial not installed:  pip install pyserial")

ANSI = re.compile(r"\x1b\[[0-9;]*m")
DISTANCE = re.compile(r"'Lightning Distance' >> ([0-9.]+) km")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default="/dev/ttyUSB0", help="serial port (default: %(default)s)")
    ap.add_argument("--baud", type=int, default=115200, help="baud rate (default: %(default)s)")
    ap.add_argument("--minutes", type=float, default=10.0, help="survey duration (default: %(default)s)")
    ap.add_argument("--bucket", type=float, default=60.0,
                    help="timeline bucket in seconds; reveals bursty vs steady sources "
                         "(default: %(default)s)")
    args = ap.parse_args()

    try:
        s = serial.Serial()
        s.port, s.baudrate, s.timeout = args.port, args.baud, 0.3
        # Leave DTR/RTS alone: toggling them can wedge an ESP32 into a reset loop.
        s.dtr = False
        s.rts = False
        s.open()
    except Exception as exc:
        sys.exit(f"could not open {args.port}: {exc}")

    counts = collections.Counter()
    distances = collections.Counter()
    timeline = collections.defaultdict(collections.Counter)
    lines_seen = 0
    buf = b""
    duration = args.minutes * 60
    start = time.time()

    print(f"surveying {args.port} for {args.minutes:g} min ... (Ctrl-C to stop early)", flush=True)
    try:
        while time.time() - start < duration:
            chunk = s.read(2048)
            if not chunk:
                continue
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                lines_seen += 1
                txt = ANSI.sub("", raw.decode("utf-8", errors="replace")).strip()
                bucket = int((time.time() - start) // args.bucket)

                if "Lightning has been detected" in txt:
                    counts["lightning"] += 1
                    timeline[bucket]["lightning"] += 1
                elif "Disturber was detected" in txt:
                    counts["disturber"] += 1
                    timeline[bucket]["disturber"] += 1
                elif "Noise was detected" in txt:
                    counts["noise"] += 1
                    timeline[bucket]["noise"] += 1
                else:
                    m = DISTANCE.search(txt)
                    if m:
                        distances[m.group(1)] += 1

            # Fail fast rather than silently reporting a quiet sensor.
            if lines_seen == 0 and time.time() - start > 10:
                sys.exit("no serial output after 10s -- is the node running with "
                         "logger level VERY_VERBOSE?")
    except KeyboardInterrupt:
        print("\ninterrupted", flush=True)
    finally:
        s.close()

    elapsed = max(time.time() - start, 1e-9)
    mins = elapsed / 60.0

    print(f"\n=== ambient survey: {elapsed/60:.1f} min, {lines_seen} log lines ===")
    print(f"{'type':12} {'count':>7} {'per min':>9}")
    for kind in ("lightning", "disturber", "noise"):
        print(f"{kind:12} {counts[kind]:>7} {counts[kind]/mins:>9.1f}")

    print(f"\nFIGURE OF MERIT -- ambient false lightning: {counts['lightning']/mins:.1f}/min")
    if counts["lightning"] == 0:
        print("  Zero. This location is a viable candidate.")
    else:
        print("  Non-zero. Every one of these publishes a bogus strike into Home Assistant.")

    if distances:
        print("\nlightning distances reported:")
        for km, n in sorted(distances.items(), key=lambda kv: float(kv[0])):
            flag = "  <-- local EMI (overhead bin)" if km == "1.0" else "  <-- candidate REAL strike"
            print(f"  {km:>6} km  x{n}{flag}")

    if timeline and len(timeline) > 1:
        print(f"\ntimeline ({args.bucket:g}s buckets) -- steady or bursty?")
        for b in sorted(timeline):
            c = timeline[b]
            bar = "#" * min(c["lightning"] + c["disturber"] + c["noise"], 60)
            print(f"  t+{b*args.bucket/60:5.1f}m  L{c['lightning']:<3} D{c['disturber']:<3} "
                  f"N{c['noise']:<3} {bar}")


if __name__ == "__main__":
    main()
