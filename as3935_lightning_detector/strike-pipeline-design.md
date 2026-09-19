# Per-strike telemetry pipeline — design

How every AS3935 strike gets recorded and visualised by distance and time, and why the
Home Assistant path cannot do it.

This is the **design**: the reasoning, the event contract, and the data rules that any
implementation has to honour. Site-specific deployment — hostnames, credentials, container
placement, dashboard provisioning — is deliberately not here; it lives in a private
infrastructure repository.

> **Status: design only, nothing built.** Recorded so the shape of the pipeline, and the
> reasons behind it, survive as project documentation.

---

## 1. Why the Home Assistant path cannot do this

The project's core deliverable — *every strike, visualised by distance and time* — fails
on the current path, and it is a data-model problem, not a sensor problem (§8.4):

1. **Home Assistant stores states, not events.** Two identical strikes are one state
   change. §8.4 is exactly this, and it will keep biting with real strikes whenever
   consecutive strikes share a distance code.
2. **Prometheus-via-HA is gauge sampling.** A gauge scraped every 15–60 s cannot represent
   an event stream; sampling a point process discards nearly all of it.
3. **The 10 ms Storm Alert pulse is the wrong signal shape** for anything downstream, and
   was measured at 79 ms because `loop()` runs late.

One move fixes all three: **carry a discrete, sequence-tagged event off the node into
event-shaped stores, and make every counter cumulative** so no scrape interval can lose a
strike.

---

## 2. Architecture

```
  ESP32 / AS3935
        |  MQTT, QoS 1, one message per strike
        v
     broker
        |
        v
  bridge  --> stdout (JSON, one line per strike) --> journald --> Loki --> Grafana
        |--> /metrics (Prometheus counters + histograms) ------> Prometheus --> Grafana
        |--> strikes.jsonl (permanent archive)
```

Three stores, because they answer different questions:

| Store | Answers | Loses |
|---|---|---|
| Prometheus | "how many, how often, at what distance" | which strike |
| Loki | "show me every strike, with its energy" | old data, at retention |
| JSONL archive | "what exactly happened during the 2027 storm" | nothing |

MQTT is the transport because it is the only one of the obvious candidates that is
event-shaped at both ends, fire-and-forget on a device whose `loop()` is documented as
running late, and does not involve Home Assistant's state machine.

---

## 3. The event contract

This is the entire interface between the node and everything downstream. Get it right and
the rest is mechanical.

### Topics

| Topic | Retain | QoS | Payload |
|---|---|---|---|
| `lightning/<node>/event` | **false** | 1 | one JSON event |
| `lightning/<node>/status` | **true** | 1 | `online` / `offline` (MQTT birth + LWT) |

⚠️ **Retain must be false on `event`.** A retained message is redelivered to every
subscriber on every reconnect, so a bridge restart would invent a strike that never
happened — precisely the class of self-deception §11 exists to prevent. Retain is correct
on `status` and nowhere else.

### Payload

```json
{
  "seq": 1234,
  "boot": 7,
  "uptime_ms": 84512345,
  "class": "lightning",
  "distance_code": 12,
  "energy": 48210
}
```

| Field | Type | Meaning |
|---|---|---|
| `seq` | uint32 | Per-boot event counter, from 1. **Mandatory** — see below. |
| `boot` | uint32 | Boot session id. Distinguishes `seq=1` after a reboot from a redelivered `seq=1`. |
| `uptime_ms` | uint32 | Node-side event time. Receive time is authoritative for charts; this detects queueing. |
| `class` | enum | `lightning` in practice — see §5. Reserved: `disturber`, `noise`. |
| `distance_code` | uint8 | **Raw `REG0x07[5:0]`, not km.** See §4. |
| `energy` | uint32 | Raw 21-bit chip value. No physical meaning; zero-vs-nonzero is diagnostic. |

**`seq` is mandatory, not a nicety.** It is the single field that makes two identical
strikes two events in every store downstream — the exact failure §8.4 documents. It also
gives gap detection (WiFi dropout, broker restart) and duplicate suppression, which QoS 1
requires because QoS 1 is *at-least-once*, not exactly-once. The bridge keys on
`(boot, seq)`.

---

## 4. `distance_code` is a lookup table, not a number

This trap (§8.2) must be carried through every layer or it quietly corrupts the dashboard.
The register holds one of sixteen codes:

| Code | Meaning |
|---|---|
| `1` | Storm overhead — **and where local EMI lands** (§11.2) |
| `5 6 8 10 12 14 17 20 24 27 31 34 37 40` | Real distances, km |
| `63` | **Not 63 km.** Out of range: lightning classified, distance not estimable |
| anything else | Impossible. A free SPI-mode canary (§8.1) |

Three rules follow, all load-bearing:

- **`63` never enters the distance histogram.** Put it in the top bucket and it reads as a
  plausible distant storm — the §8.2 bug reproduced one layer up. It gets its own counter.
- **An out-of-table code is a firmware fault, not a data point.** It gets its own counter
  too, which turns §8.1's SPI-mode canary into standing monitoring.
- **The chart's Y axis is sixteen discrete rows, not a 0–63 km linear scale.** A linear
  axis leaves roughly a third of the plot empty and puts `63` where "very far away"
  belongs.

---

## 5. Scope: `class` is `lightning` only

**Decided 2026-09-18: only `lightning` events are published. `disturber` and `noise` are
not collected.** The `class` field stays in the contract so adding them later is not a
breaking change, but nothing in this design expects them.

The reasoning, because it is not the obvious answer:

- **The site-health metric this project cares about is already in the lightning stream.**
  `tools/README.md` is explicit that locations are ranked by the ambient `INT_L` (false
  lightning) rate, *not* the disturber rate — "the obvious metric is the wrong one"
  (§11.2). Ambient false `INT_L` events publish as `class=lightning`, distance code `1`,
  usually zero energy. The overhead and zero-energy counters are therefore the site
  monitor, and they cost nothing extra.
- **The cost is permanent.** ESPHome's `as3935` component exposes a trigger only for the
  thunder alert; disturber and noise interrupts are logged at `VERBOSE` and nothing else.
  Collecting them needs an `external_components` override of `as3935.cpp`, maintained
  indefinitely against a repo whose maintainers closed the last fix `NOT_PLANNED` (§8.2).
- **There is nothing to watch.** At the finished build's 0.005 disturbers/min (§11.8), AFE
  deactivation costs roughly 0.01% deaf time.

What this gives up, so it is a decision rather than an omission:

- **AFE duty cycle** — how much of a quiet hour the sensor was actually deaf. Only matters
  if the site degrades by orders of magnitude, in which case the false-lightning rate would
  very likely move too.
- **Standing early warning of a new EMI source.** `tools/ambient-survey.py` already covers
  this ad hoc over WiFi, and the site selection it was built for is finished.

⚠️ **Do not reach for `mqtt: log_topic:` as a shortcut to the same data.** At `VERBOSE` the
node emits ~17 log lines/s (63,300/hour, measured — §8.4). Pointing that at a broker to
recover a few disturber lines is three orders of magnitude of waste.

---

## 6. What the bridge does

A small service subscribing to the broker. Responsibilities, in order:

1. Subscribe to `lightning/+/event` and `lightning/+/status`.
2. Drop duplicates on `(node, boot, seq)`; count them.
3. Detect gaps in `seq`; count them.
4. Validate `distance_code` against the sixteen-value table; count violations.
5. Emit one JSON line per accepted event to stdout.
6. Append the same line to a durable archive file.
7. Update Prometheus metrics; serve `/metrics`.

### Metrics

```
lightning_events_total{node,class}                    counter
lightning_strike_distance_km_bucket{node,le}          histogram   # valid codes only
lightning_strike_distance_km_sum{node}
lightning_strike_distance_km_count{node}
lightning_strikes_unknown_distance_total{node}        counter     # code 63
lightning_strikes_overhead_total{node}                counter     # code 1
lightning_strike_energy_bucket{node,le}               histogram
lightning_strikes_zero_energy_total{node}             counter
lightning_invalid_distance_code_total{node}           counter     # SPI-mode canary
lightning_last_event_timestamp_seconds{node,class}    gauge
lightning_node_status{node}                           gauge       # 1/0 from LWT
lightning_events_dropped_total{node}                  counter     # seq gaps
lightning_events_duplicate_total{node}                counter     # QoS 1 redelivery
lightning_bridge_mqtt_connected                       gauge
lightning_bridge_build_info{version}                  gauge
```

**Counters throughout, and that is the point.** A cumulative counter scraped every 60 s
loses event *timing* but never loses an *event*. This is precisely what the HA gauge path
could not do, and it is why the Prometheus half of this design works at all.

**Distance histogram buckets** are the code table's own values, so each bucket is exactly
one code:

```
le = 1, 5, 6, 8, 10, 12, 14, 17, 20, 24, 27, 31, 34, 37, 40
```

Because `63` and invalid codes are excluded, `+Inf` should always equal the `le="40"`
bucket. That invariant is a free secondary canary; `lightning_invalid_distance_code_total`
is the primary one.

**Energy histogram buckets** — the raw value is 21-bit (0–2,097,151), so exponential:

```
le = 0, 1, 10, 100, 1000, 10000, 100000, 1000000
```

The `le="0"` bucket counts exactly-zero observations, making
`lightning_strikes_zero_energy_total` technically redundant. Keep it anyway: "did this
strike have any measurable signal behind it" is a question asked often enough
(`tools/README.md`) to deserve a metric that reads directly.

**Cardinality is ~40 series total.** Every label is bounded: one node, one class in
practice, fifteen buckets.

### Log line

One JSON line per event on stdout, so a log pipeline's JSON parser handles it with no
regex:

```json
{"ts":"2026-09-18T21:14:02.881Z","node":"esp32-lightning-sensor","seq":1234,"boot":7,"class":"lightning","distance_code":12,"distance_valid":true,"energy":48210,"uptime_ms":84512345}
```

`distance_valid` is `false` for code 63 — precomputed so no dashboard query has to
remember the §4 rule.

### Durable archive

Also append each line to a JSONL file, rotated yearly, **never deleted**.

Log retention is tuned for logs, not for a multi-year scientific record; a storm is rare
and the raw capture is what §15 Phase 4 actually wants. A busy storm is a few hundred KB.
This is the artefact still worth having in five years.

---

## 7. The silence problem

This deserves naming because the project has already been bitten by it twice — the
`ambient-survey.py` health gate and the `emulator-trial.py` reader gate both exist because
**a dead source and a quiet sky produce identical output** (`tools/README.md`).

The same hazard applies to the whole pipeline. Zero strikes on a dashboard means either no
storms or a broken chain, and nothing on the chart distinguishes them. So the pipeline
needs its own health gate, and these are not optional polish:

| Condition | Why |
|---|---|
| Bridge scrape target down | The pipeline is dead |
| `lightning_node_status == 0` | **The one signal separating "node online, sky quiet" from "node offline."** |
| `lightning_events_dropped_total` increasing | Strikes were lost in transit |
| `lightning_invalid_distance_code_total` increasing | **SPI-mode regression (§8.1)** — a firmware fault the node itself reports as healthy |

**Do not alert on lightning.** A strike is a notification and belongs in Home Assistant,
which already has delivery. Alerting is for the instrument failing.

---

## 8. Visualisation

### Scatter first, heat map second

The original sketch was a heat map — time on X, distance on Y, colour for strike count.
It works, but **the scatter plot is probably the better primary panel.**

The stated goal is to see *every* strike. A heat map is an aggregation: it answers "how
many" per cell and discards which. With a few thousand strikes in a storm, one mark per
strike is entirely tractable, shows every event, and has a free third channel — colour —
for energy, which is the field that would show whether real strikes separate from EMI
(§11.2). A heat map earns its place only once marks overlap enough to hide density.

Build both. They come from the same data and cost one extra panel; let a real storm decide
which one gets looked at.

### The honesty panel

A panel showing the share of events that are code `63`, code `1`, or zero-energy. **Do not
omit it.** A dashboard that hides this reads as a storm every time local EMI acts up
(§11.2), and with disturbers out of scope (§5) this is also the standing site-health
monitor.

⚠️ **Reading it:** code `1` means "overhead" for genuine overhead storms *and* for local
EMI; the chip cannot tell you which. It is an EMI monitor **in fair weather only** — which
is when you would read it. Zero energy is the corroborating signal: an `INT_L` with no
measurable energy behind it had nothing real to classify.

### Cross-check against the WS90

The Ecowitt gateway exports its own `ecowitt_lightning_strike_count` and
`ecowitt_lightning_distance_meters`, making the independent cross-check of §15 Phase 4 a
dashboard query rather than a project. ⚠️ **That metric is in metres while the AS3935
reports a code in km** — without the conversion the two traces sit 1000× apart.

---

## 9. Acceptance

**An unverified pipeline is not a pipeline.** Run this before believing any dashboard, and
treat the synthetic injection as the control.

**1. Inject a known sequence with the node powered off.** Publish ten events to
`lightning/esp32-lightning-sensor/event`, **all identical in distance and energy** —
deliberately, because that is the case §8.4 proves the HA path silently collapses to one.
Assert:

- the event counter increased by exactly **10**
- the `le="12"` distance bucket increased by exactly **10**
- the log store returns exactly **10** lines
- the JSONL archive gained exactly **10** lines

Ten, not one, is the whole point of the build.

**2. Duplicate suppression.** Re-send `seq=5`. Duplicate counter +1, event counter
unchanged, no new log line.

**3. Gap detection.** Send `seq=20`. Dropped counter +9.

**4. Code-table handling.** Send `distance_code: 63`, then `distance_code: 41`. The first
increments the unknown-distance counter and **must not** appear in the distance histogram.
The second increments the invalid-code counter.

**5. Liveness.** Take the node offline. `lightning_node_status` → 0 and the alert fires.
**Then restore it and confirm the alert clears** — an alert that fires but never resolves
trains you to ignore it.

**6. Restart the bridge mid-stream.** No invented events (the retain trap), no lost counter
continuity beyond the restart itself.

Only after all six should a real strike be read as a real strike.

---

## 10. Build order

Each step is independently testable and nothing waits on a storm.

1. Broker, users, ACLs.
2. Bridge, metrics only. Drive it with the injector from §9.
3. Scrape job plus the four instrument alerts from §7. Verify one fires *and clears*.
4. Confirm bridge stdout is reaching the log store.
5. Dashboard panels, still on injected data. **A dashboard built on synthetic events is a
   feature, not a compromise** — you know exactly what it should show.
6. *(node-side)* sequence counter and MQTT publish in `lightning-detector.yaml`.
7. The WS90 cross-check panel.

Steps 1–5 are pure infrastructure and can be finished before the node changes at all.
