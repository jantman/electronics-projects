# Measurement tools

Instruments used to characterise the detector on the bench. Kept in the repo so
the numbers quoted in the parent [README](../README.md) can be reproduced rather
than taken on faith.

`emulator-trial.py` needs `pyserial`, and so does `ambient-survey.py` in its
serial mode:

```bash
pip install pyserial
```

`ambient-survey.py --stdin` needs nothing beyond the standard library.

⚠️ The parent project's safety rule applies whenever the detector is on USB:
**never have USB and the IRM-02-5 mains supply powered at the same time** (parent §12).

---

## `ambient-survey.py` — site survey instrument

Counts what the sensor reports with nothing deliberately stimulating it, broken
down by interrupt type. **This is the instrument for the §10 site survey.**

Two input modes, parsed identically:

```bash
# USB serial, for a node on the bench
./ambient-survey.py --minutes 10
./ambient-survey.py --port /dev/ttyUSB1 --minutes 60 --bucket 300

# over WiFi, for a node already mounted where you don't want to follow it
esphome logs ../lightning-detector.yaml | ./ambient-survey.py --stdin --minutes 30
```

**Use `--stdin` once the node is installed.** Every message this tool counts is
emitted from `loop()`, so it streams over the API just as it does over the wire —
the serial-only line is the `setup()` tune-cap message (parent §12.1), which this
tool never needs. Network mode also sidesteps the USB-vs-mains safety rule
entirely, because nothing is plugged into the node.

Both modes are health-gated, for the same reason `emulator-trial.py` is (below):
a dead source and a silent sensor produce identical output. A source that emits
nothing for 10 s aborts the run, and any run that parses **zero** log lines is
reported as `MEANINGLESS` rather than as a quiet site. If the stream closes early
(the API drops, `esphome logs` exits) the survey stops, says so, and reports rates
over the time it actually observed.

Rank candidate locations by the **ambient `INT_L` (false lightning) rate**, not by
the disturber rate — parent §11.2 explains why the obvious metric is the wrong
one. Disturbers are discarded and never reach Home Assistant; a false `INT_L`
publishes Storm Alert, Distance and Energy straight into HA.

It also splits reported distances, and interprets them. The AS3935 distance
register is a **table of codes, not a linear km value**, and ESPHome publishes
the raw code (see parent §8.2):

| Reported | Means |
|---|---|
| `1.0 km` | Storm overhead — **where local EMI lands** |
| `5.0`–`40.0 km` | A real distance. Candidate genuine detection; cross-check against lightningmaps.org |
| `63.0 km` | **Not 63 km.** The out-of-range code: lightning classified, distance not estimable |
| anything else | Not a valid code at all — suspect the SPI mode (parent §8.1) |

The "anything else" row is a free SPI-mode canary: in Mode 0 every byte reads
back shifted, so distances would land on codes that cannot occur.

The timeline buckets distinguish a steady source (an SMPS, an ECM blower) from a
bursty one (a thermostatically-cycled compressor) — which is most of the work in
identifying what you're actually fighting.

## `emulator-trial.py` — controlled emulator correlation

The harness behind parent §11.1. Fires known strikes on the SEN-39002 while
watching the detector, and attributes interrupts by timestamp.

```bash
./emulator-trial.py --rounds 5
```

Two design points matter, and both were learned the hard way:

- **Sham controls.** One trial in four fires nothing. At ~16 ambient events/min a
  2.5 s attribution window has a ~49% chance of catching a coincidence — easily
  enough to invent a result that isn't there. The sham column measures that false
  attribution rate directly, under identical conditions. A tight window (400 ms)
  plus sham controls made the difference between "the emulator sometimes works"
  and "it never does".
- **A reader health gate.** The detector-serial reader is checked for liveness
  before the run starts. A dead reader thread looks exactly like a silent sensor,
  and once cost a full run that read as a dramatic (and completely fictitious)
  result.

Expect **disturbers, not lightning**. Parent §11.1 documents why, and what was
ruled out. This tool proves the interrupt path works; it cannot validate
lightning classification.
