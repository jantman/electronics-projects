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

Requires the node's logger at VERY_VERBOSE. There are two ways to feed it, and
they parse identically:

  # USB serial, for a node on the bench (needs pyserial)
  ./ambient-survey.py --minutes 10
  ./ambient-survey.py --port /dev/ttyUSB1 --minutes 60 --bucket 300

  # over WiFi, for a node already mounted (needs nothing but python)
  esphome logs ../lightning-detector.yaml | ./ambient-survey.py --stdin --minutes 30

Network mode works because every message this tool counts is emitted from
loop(), so it streams over the API exactly as it does over the wire. (The one
line that is genuinely serial-only is the setup() tune-cap message -- see parent
section 12.1 -- and this tool never needs it.) Use --stdin once the node is in
the attic; hauling a laptop and a USB cable up there proves nothing extra.

DISTINGUISHING REAL STRIKES FROM NOISE: local EMI reports 1.0 km (the "overhead"
bin). A genuinely distant storm reports a large distance. Any lightning event
whose distance is NOT 1.0 km is a candidate real detection -- cross-check the
timestamp against lightningmaps.org.

SAFETY: never have USB and the IRM-02-5 mains supply connected at the same time.
See README section 12. (Network mode sidesteps this entirely: nothing is plugged
into the node at all.)
"""

import argparse
import collections
import os
import re
import select
import sys
import time

ANSI = re.compile(r"\x1b\[[0-9;]*m")
DISTANCE = re.compile(r"'Lightning Distance' >> ([0-9.]+) km")

DEFAULT_PORT = "/dev/ttyUSB0"


def open_serial_source(port, baud):
    """Return (read_chunk, close, label) for a USB serial connection."""
    try:
        import serial
    except ImportError:
        sys.exit("pyserial not installed:  pip install pyserial\n"
                 "(or pipe an ESPHome log client in with --stdin, which needs no "
                 "extra packages)")

    try:
        s = serial.Serial()
        s.port, s.baudrate, s.timeout = port, baud, 0.3
        # Leave DTR/RTS alone: toggling them can wedge an ESP32 into a reset loop.
        s.dtr = False
        s.rts = False
        s.open()
    except Exception as exc:
        sys.exit(f"could not open {port}: {exc}")

    # A serial port never reaches EOF -- a quiet line just reads empty.
    return (lambda: s.read(2048)), s.close, port


def open_stdin_source():
    """Return (read_chunk, close, label) for a piped-in log stream."""
    if sys.stdin is None or sys.stdin.closed:
        sys.exit("--stdin given but stdin is not open")

    fd = sys.stdin.fileno()
    if os.isatty(fd):
        sys.exit("--stdin given but stdin is a terminal -- pipe a log client in:\n"
                 "  esphome logs ../lightning-detector.yaml | "
                 "./ambient-survey.py --stdin")

    def read_chunk():
        # select() with a timeout rather than a blocking read, so the survey's
        # duration still expires while the stream is quiet. A quiet stream is
        # the expected case at a good site.
        ready, _, _ = select.select([fd], [], [], 0.3)
        if not ready:
            return b""
        chunk = os.read(fd, 2048)
        return chunk if chunk else None  # None == writer closed the pipe

    return read_chunk, (lambda: None), "stdin"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stdin", action="store_true",
                    help="read the log stream from stdin instead of a serial port, "
                         "e.g. piped from `esphome logs`; use this for a node on WiFi")
    ap.add_argument("--port", default=None,
                    help=f"serial port (default: {DEFAULT_PORT}); not valid with --stdin")
    ap.add_argument("--baud", type=int, default=115200, help="baud rate (default: %(default)s)")
    ap.add_argument("--minutes", type=float, default=10.0, help="survey duration (default: %(default)s)")
    ap.add_argument("--bucket", type=float, default=60.0,
                    help="timeline bucket in seconds; reveals bursty vs steady sources "
                         "(default: %(default)s)")
    args = ap.parse_args()

    if args.stdin and args.port is not None:
        ap.error("--stdin and --port are mutually exclusive")

    if args.stdin:
        read_chunk, close, label = open_stdin_source()
    else:
        read_chunk, close, label = open_serial_source(args.port or DEFAULT_PORT, args.baud)

    counts = collections.Counter()
    distances = collections.Counter()
    timeline = collections.defaultdict(collections.Counter)
    lines_seen = 0
    buf = b""
    duration = args.minutes * 60
    start = time.time()
    ended_early = None

    print(f"surveying {label} for {args.minutes:g} min ... (Ctrl-C to stop early)", flush=True)
    try:
        while time.time() - start < duration:
            # Liveness gate first, so it still fires on a source that produces
            # nothing at all. A dead pipe and a silent sensor look identical in
            # the output, and a survey that quietly reports zero events is worse
            # than no survey -- the same failure that cost a run in section 11.1.
            if lines_seen == 0 and time.time() - start > 10:
                sys.exit(f"no output from {label} after 10s -- is the node running "
                         "with logger level VERY_VERBOSE?")

            chunk = read_chunk()
            if chunk is None:
                ended_early = "the log stream closed (did `esphome logs` lose the API?)"
                break
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
    except KeyboardInterrupt:
        ended_early = "interrupted"
        print("\ninterrupted", flush=True)
    finally:
        close()

    elapsed = max(time.time() - start, 1e-9)
    mins = elapsed / 60.0

    print(f"\n=== ambient survey: {elapsed/60:.1f} min, {lines_seen} log lines "
          f"(source: {label}) ===")
    if ended_early and ended_early != "interrupted":
        print(f"WARNING: stopped after {elapsed/60:.1f} of {args.minutes:g} min -- "
              f"{ended_early}")
        print("         Rates below are over the time actually observed.")
    print(f"{'type':12} {'count':>7} {'per min':>9}")
    for kind in ("lightning", "disturber", "noise"):
        print(f"{kind:12} {counts[kind]:>7} {counts[kind]/mins:>9.1f}")

    print(f"\nFIGURE OF MERIT -- ambient false lightning: {counts['lightning']/mins:.1f}/min")
    if lines_seen == 0:
        # Not a quiet site -- a broken run. Never let this read as an all-clear:
        # a silent source and a silent sensor produce identical output, and the
        # liveness gate above only catches it once 10s have elapsed.
        print("  MEANINGLESS -- not one log line was parsed. This is a broken run,")
        print("  not a quiet location. Check the source and the VERY_VERBOSE level.")
    elif counts["lightning"] == 0:
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
