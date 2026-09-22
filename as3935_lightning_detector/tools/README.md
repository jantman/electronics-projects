# Measurement tools

Instruments used to characterise the detector on the bench. Kept in the repo so
the numbers quoted in the [project notebook](../docs/project-notebook.md) can be reproduced rather
than taken on faith.

`emulator-trial.py` needs `pyserial`, and so does `ambient-survey.py` in its
serial mode:

```bash
pip install pyserial
```

`ambient-survey.py --stdin` needs nothing beyond the standard library.
`ws-log-bridge.py` needs `websockets`:

```bash
pip install websockets
```

⚠️ The parent project's safety rule applies whenever the detector is on USB:
**never have USB and the IRM-02-5 mains supply powered at the same time** (notebook §12).

---

## `ambient-survey.py` — site survey instrument

Counts what the sensor reports with nothing deliberately stimulating it, broken
down by interrupt type. **This is the instrument for the §10 site survey.**

Two input modes, parsed identically:

```bash
# USB serial, for a node on the bench
./ambient-survey.py --minutes 10
./ambient-survey.py --port /dev/ttyUSB1 --minutes 60 --bucket 300

# over WiFi, for a node already mounted where you don't want to follow it:
# through the ESPHome dashboard -- no local ESPHome, no secrets (ws-log-bridge.py below)
./ws-log-bridge.py --cafile /path/to/ca.pem | ./ambient-survey.py --stdin --minutes 30

# ...or with a local ESPHome venv and the real secrets.yaml (notebook §11.4). Note
# esphome logs does not exit with the survey; §11.4 has the FIFO workaround.
esphome logs ../lightning-detector.yaml | ./ambient-survey.py --stdin --minutes 30
```

**Use `--stdin` once the node is installed.** Every message this tool counts is
emitted from `loop()`, so it streams over the API just as it does over the wire —
the serial-only line is the `setup()` tune-cap message (notebook §12.1), which this
tool never needs. Network mode also sidesteps the USB-vs-mains safety rule
entirely, because nothing is plugged into the node.

Both modes are health-gated, for the same reason `emulator-trial.py` is (below):
a dead source and a silent sensor produce identical output. A source that emits
nothing for 10 s aborts the run, and any run that parses **zero** log lines is
reported as `MEANINGLESS` rather than as a quiet site. If the stream closes early
(the API drops, `esphome logs` exits) the survey stops, says so, and reports rates
over the time it actually observed.

Rank candidate locations by the **ambient `INT_L` (false lightning) rate**, not by
the disturber rate — notebook §11.2 explains why the obvious metric is the wrong
one. Disturbers are discarded and never reach Home Assistant; a false `INT_L`
publishes Storm Alert, Distance and Energy straight into HA.

It also splits reported distances, and interprets them. The AS3935 distance
register is a **table of codes, not a linear km value**, and ESPHome publishes
the raw code (see notebook §8.2):

| Reported | Means |
|---|---|
| `1.0 km` | Storm overhead — **where local EMI lands** |
| `5.0`–`40.0 km` | A real distance. Candidate genuine detection; cross-check against lightningmaps.org |
| `63.0 km` | **Not 63 km.** The out-of-range code: lightning classified, distance not estimable |
| anything else | Not a valid code at all — suspect the SPI mode (notebook §8.1) |

The "anything else" row is a free SPI-mode canary: in Mode 0 every byte reads
back shifted, so distances would land on codes that cannot occur.

Each INT_L is also reported with its **lightning energy**, paired to its distance
code. Energy is a bare number from the chip with no physical meaning, but zero
vs non-zero is diagnostic: a zero-energy INT_L has no measurable signal behind
the classification. If false strikes turn out to be reliably zero-energy, then
filtering on energy costs **nothing in sensitivity** — unlike raising
`spike_rejection`, which trades away real strikes to buy quiet. Events whose
energy line never arrived are counted separately (`N of M fully paired`) so a
dropped line can't quietly skew the percentage.

The timeline buckets distinguish a steady source (an SMPS, an ECM blower) from a
bursty one (a thermostatically-cycled compressor) — which is most of the work in
identifying what you're actually fighting.

## `emulator-trial.py` — controlled emulator correlation

The harness behind notebook §11.1. Fires known strikes on the SEN-39002 while
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

## `ws-log-bridge.py` — node logs over WiFi, via the ESPHome dashboard

The ESPHome that manages this node runs on a server, behind the ESPHome Device
Builder dashboard. The other way to get its logs onto a workstation is a
throwaway local ESPHome venv plus a copy of the real `secrets.yaml` (notebook
§11.4). This tool needs neither: the dashboard can stream a node's logs itself,
and this speaks its websocket protocol and prints one log line per line, which is
exactly what `--stdin` reads. It also exits when the survey closes the pipe, so
§11.4's FIFO workaround for `esphome logs` is unnecessary.

```bash
./ws-log-bridge.py --cafile /path/to/ca.pem | ./ambient-survey.py --stdin --minutes 60
```

- **Credentials** come from `~/.netrc`, as an entry for the dashboard host with
  the **same username and password as the dashboard's own sign-in page**.
  Exactly one login attempt is made per run: the dashboard rate-limits failed
  sign-ins, and a retry loop could lock you out of it.
- **`--cafile`** names the CA that signs the dashboard's TLS certificate, if it
  is not in the system trust store. It is deliberately not kept in this repo.
  ⚠️ **A `phoenixca` anchor in the system store is not enough.** On the
  workstation used on 2026-09-13, `trust list` showed phoenixca as an anchor and
  verification still failed (`self-signed certificate in certificate chain`, both
  `openssl s_client` and Python). Fetch the CA as below and pass `--cafile`
  rather than debugging the store.
- **It ends when the survey does.** The survey closing the pipe is the normal
  way out; `--max-seconds` is only a safety stop and is off by default.
- **It redacts the WiFi password.** At logger level VERBOSE and above, ESPHome
  prints it in plain text whenever it connects to WiFi (notebook §8).

### Setting it up on another machine

Three things, none of them in this repo:

1. `pip install websockets`
2. A `~/.netrc` entry for the dashboard host, `chmod 600`, holding the web
   sign-in's username and password:

   ```
   machine esphome.jasonantman.com login USER password PASS
   ```

3. The CA that signs the dashboard's certificate — unless it is already in that
   machine's trust store, in which case leave `--cafile` off. To fetch it, take
   the second certificate the server presents, then **check its fingerprint
   against the one below before trusting it**; fetching a CA over the connection
   it is meant to protect proves nothing on its own:

   ```bash
   echo | openssl s_client -connect esphome.jasonantman.com:16052 \
          -servername esphome.jasonantman.com -showcerts 2>/dev/null \
     | awk '/BEGIN CERT/{n++} n==2{print} /END CERT/&&n==2{exit}' > ca.pem
   openssl x509 -in ca.pem -noout -subject -fingerprint -sha256
   # subject ... OU=phoenixca, CN=jasonantman.com   (expires 2032-04-30)
   # sha256 F3:A3:45:35:4A:19:9A:DD:0E:5A:94:DF:F0:76:8C:2D:
   #        27:5D:BE:54:0E:B4:BB:F8:54:30:F0:EB:A4:CB:BB:71
   ```

Then a survey, keeping the raw stream so every event has a timestamp. The
survey itself only reports five-minute buckets; the timestamps are what let a
burst be matched against the house (notebook §11.6):

```bash
./ws-log-bridge.py --cafile ca.pem \
  | tee survey-raw.log \
  | ./ambient-survey.py --stdin --minutes 60 --bucket 300

# afterwards: one line per event, with the dashboard's own timestamp
sed 's/\x1b\[[0-9;]*m//g' survey-raw.log | grep -E 'Disturber was|Noise was|Lightning has'
```

`survey-raw.log` has the WiFi password already redacted by the bridge, but it is
still a raw node log; keep it out of the repo.

### Watching events live, with someone at the bench

A survey only reports when it ends, which is no use when a person is pressing
emulator buttons and wants to know whether each one landed. For that, take the
same stream and print just the interrupts as they arrive:

```bash
./ws-log-bridge.py --cafile ca.pem \
  | tee -a liveness-raw.log \
  | sed -u 's/\x1b\[[0-9;]*m//g' \
  | grep --line-buffered -E 'Disturber was|Noise was|Lightning has'
```

`sed -u` and `grep --line-buffered` are both required — without them each stage
sits on its output until a buffer fills, and events appear in clumps minutes
late. This is the form used for the §11.8 liveness check, where matching each
press to its event in real time is the whole point. Run a normal survey
alongside it if you also want the counts; two dashboard log clients coexist
fine.

**Validated against serial, 2026-09-13.** A serial survey and a survey through
this bridge ran side by side while the SEN-39002 emulator fired 15 bursts: both
counted **15 disturbers**, and all 181 lines the bridge forwarded were read.
That is what makes a laptop-free run on the USB brick trustworthy.

The protocol was reverse-engineered from the dashboard's own JS bundle (server
1.1.0, ESPHome 2026.6), and has two traps worth knowing if it ever breaks:

- **`message_id` must be a string.** An integer id is dropped with no reply at
  all, so the login just hangs — which looks exactly like a credentials problem
  and isn't one.
- **Each `output` event is exactly one log line, with no trailing newline**, and
  ANSI escapes arrive as the literal four characters `\033`. The bridge fixes
  both up so the survey's ANSI filter and line splitting work unchanged.

## The serial port resets the node

Both `ambient-survey.py` and `emulator-trial.py` drop DTR and RTS before opening
the port. Their comments say this leaves the ESP32 alone; on the ESP32-DevKitC
it does not. pyserial lowers DTR before RTS, and that brief DTR-low/RTS-high
state is exactly the auto-reset circuit's reset condition. **Every serial run
starts with a reboot of the node** — visible as `'Uptime' >> 2 s` at the start of
the log.

- It is harmless: the AS3935 stays powered and keeps its registers through an
  ESP32 reset (notebook §8.3).
- It does mean no serial tool here can attach to a running node without
  rebooting it. To capture a genuine *sensor* cold boot (notebook §12.1), hold EN
  while plugging in USB, open the port, then release EN.
- Opening with DTR/RTS left asserted avoids the reset, but on 2026-09-13 it twice
  produced unreadable captures (a byte stream that 115200 baud could not have
  carried). The cause was not determined; use the reset-on-open method, which
  produced clean text every time.
