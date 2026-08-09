#!/usr/bin/env python3
"""
Controlled correlation trial: SEN-39002 emulator vs AS3935 detector.

Fires known strikes on the emulator while watching the detector's serial log, and
attributes interrupts to strikes by timestamp. This is the harness behind the
findings in README section 11.1.

  ./emulator-trial.py --rounds 5
  ./emulator-trial.py --uno /dev/ttyACM1 --esp /dev/ttyUSB1 --window 0.4

Needs BOTH boards connected: the emulator Uno (running sen39002-emulator-uno/)
and the detector ESP32 (logger at VERY_VERBOSE). They coexist happily as
/dev/ttyACM* and /dev/ttyUSB*.

WHAT TO EXPECT: disturbers, not lightning. Section 11.1 documents why, and what
was ruled out. This proves the interrupt path; it cannot validate classification.

TWO DESIGN POINTS, both learned the hard way:

  * SHAM CONTROLS. One trial in four fires nothing. At ~16 ambient events/min a
    2.5 s window has a ~49% chance of catching a coincidence -- enough to invent
    a result that isn't there. The sham column measures that rate directly.

  * READER HEALTH GATE. The detector reader is proven alive before the run
    starts. A dead reader thread looks exactly like a silent sensor, and once
    produced a full run of "nothing detected" that was purely a software fault.

SAFETY: never have USB and the IRM-02-5 mains supply powered at the same time.
"""

import argparse
import collections
import math
import re
import sys
import threading
import time
import traceback

try:
    import serial
except ImportError:
    sys.exit("pyserial not installed:  pip install pyserial")

ANSI = re.compile(r"\x1b\[[0-9;]*m")
LABELS = {8: "LIGHTNING (8)", 4: "disturber (4)", 1: "noise (1)"}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--uno", default="/dev/ttyACM0", help="emulator Uno port (default: %(default)s)")
    ap.add_argument("--esp", default="/dev/ttyUSB0", help="detector ESP32 port (default: %(default)s)")
    ap.add_argument("--rounds", type=int, default=5, help="rounds of close/mid/far/sham (default: %(default)s)")
    ap.add_argument("--window", type=float, default=0.40,
                    help="attribution window in seconds. Keep tight: real responses land "
                         "in 30-230ms (default: %(default)s)")
    ap.add_argument("--baseline", type=float, default=45.0, help="ambient baseline seconds (default: %(default)s)")
    ap.add_argument("--gap", type=float, default=3.2,
                    help="seconds between trials; must exceed the AS3935's ~1.5s post-disturber "
                         "deactivation (default: %(default)s)")
    args = ap.parse_args()

    events = []
    stop = threading.Event()
    health = {"lines": 0, "err": None}

    def reader():
        try:
            s = serial.Serial()
            s.port, s.baudrate, s.timeout = args.esp, 115200, 0.2
            s.dtr = False   # leave DTR/RTS alone: toggling can wedge an ESP32
            s.rts = False
            s.open()
        except Exception as exc:
            health["err"] = f"open failed: {exc}"
            return
        buf, pending = b"", False
        try:
            while not stop.is_set():
                d = s.read(2048)
                if not d:
                    continue
                buf += d
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    now = time.time()
                    health["lines"] += 1
                    txt = ANSI.sub("", raw.decode("utf-8", errors="replace")).strip()
                    # The interrupt value is the first register read after the
                    # "Calling read_interrupt_register_" marker. Later reads in the
                    # same iteration are distance/energy and must not be counted.
                    if "Calling read_interrupt_register_" in txt:
                        pending = True
                    elif pending and "read_register_:" in txt:
                        pending = False
                        events.append((now, int(txt.split("read_register_:")[1].strip())))
        except Exception:
            health["err"] = traceback.format_exc()
        finally:
            try:
                s.close()
            except Exception:
                pass

    th = threading.Thread(target=reader, daemon=True)
    th.start()

    time.sleep(5)
    if health["err"] or health["lines"] == 0:
        sys.exit(f"ABORT: detector reader not working. lines={health['lines']} err={health['err']}")
    print(f"reader OK ({health['lines']} lines in 5s)\n", flush=True)

    try:
        uno = serial.Serial(args.uno, 115200, timeout=0.3)   # opening resets the Uno
    except Exception as exc:
        sys.exit(f"could not open emulator {args.uno}: {exc}")
    time.sleep(6)                                            # Uno boot + LED sweep
    uno.reset_input_buffer()

    print(f"=== PHASE 1: ambient baseline {args.baseline:g}s (emulator idle) ===", flush=True)
    t0 = time.time()
    time.sleep(args.baseline)
    base = [e for e in events if e[0] >= t0]
    rate = len(base) / args.baseline
    print(f"  {len(base)} interrupts = {rate*60:.1f}/min  "
          f"{collections.Counter(v for _, v in base).most_common()}", flush=True)

    print(f"\n=== PHASE 2: window {args.window*1000:.0f}ms, sham controls ===", flush=True)
    print(f"  P(coincidence per window) = {(1-math.exp(-rate*args.window))*100:.1f}%\n", flush=True)

    slots = [("c", "CLOSE"), ("m", "MID"), ("f", "FAR"), (None, "SHAM")] * args.rounds
    res = collections.defaultdict(list)
    print(f"{'#':>3} {'slot':6} {'response':22} {'lat':>7}", flush=True)
    for i, (key, name) in enumerate(slots, 1):
        uno.reset_input_buffer()
        fired = time.time()
        if key:
            uno.write(key.encode())
            uno.flush()
        time.sleep(args.window)
        hits = [e for e in events if fired <= e[0] <= fired + args.window]
        if hits:
            t, v = hits[0]
            print(f"{i:>3} {name:6} {LABELS.get(v, f'? ({v})'):22} {(t-fired)*1000:6.0f}ms", flush=True)
            res[name].append(v)
        else:
            print(f"{i:>3} {name:6} {'-- nothing --':22}", flush=True)
            res[name].append(None)
        time.sleep(args.gap)

    stop.set()
    th.join(timeout=2)
    uno.close()

    print(f"\n=== SUMMARY ({args.rounds} trials each) ===")
    print(f"{'slot':6} {'responded':>10} {'LIGHTNING':>10} {'disturber':>10}")
    for n in ("CLOSE", "MID", "FAR", "SHAM"):
        v = res[n]
        got = [x for x in v if x is not None]
        print(f"{n:6} {len(got):>7}/{len(v)} "
              f"{sum(1 for x in got if x == 8):>10} {sum(1 for x in got if x == 4):>10}")
    print("\nSHAM is the control: responses there are pure ambient coincidence.")
    print("Compare the strike rows against it -- a result is only real if it beats SHAM.")


if __name__ == "__main__":
    main()
