# Measurement tools

Instruments used to characterise the detector on the bench. Kept in the repo so
the numbers quoted in the parent [README](../README.md) can be reproduced rather
than taken on faith.

Both need only `pyserial`:

```bash
pip install pyserial
```

⚠️ The parent project's safety rule applies whenever the detector is on USB:
**never have USB and the IRM-02-5 mains supply powered at the same time** (parent §12).

---

## `ambient-survey.py` — site survey instrument

Counts what the sensor reports with nothing deliberately stimulating it, broken
down by interrupt type. **This is the instrument for the §10 site survey.**

```bash
./ambient-survey.py --minutes 10
./ambient-survey.py --port /dev/ttyUSB1 --minutes 60 --bucket 300
```

Rank candidate locations by the **ambient `INT_L` (false lightning) rate**, not by
the disturber rate — parent §11.2 explains why the obvious metric is the wrong
one. Disturbers are discarded and never reach Home Assistant; a false `INT_L`
publishes Storm Alert, Distance and Energy straight into HA.

It also splits reported distances. **Local EMI lands in the 1.0 km "overhead"
bin**; anything else is a candidate genuine detection worth cross-checking
against lightningmaps.org.

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
