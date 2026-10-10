# Hunting the attic's false-lightning sources

*Companion to the [project notebook](project-notebook.md); § references below are to it. Written
2026-10-10, from data up to 2026-10-10 08:05.*

This is the plan for finding what the node reports as lightning from the garage attic (§11.11). It
runs in three phases, cheapest first, with a decision between each: **mine what is already
recorded**, then **cheap physical experiments**, and only then the **SDR and direction-finding loop**
from [`sdr-interference-hunting.md`](sdr-interference-hunting.md). Phase 1 has been done, and its
results are below.

---

## 0. What we are hunting

Since the move on 2026-09-22 the node has reported **256 `INT_L` events in 18 days**, none of them
during a storm (§11.11). The data is the per-strike MQTT stream (boot 2, `seq` 1–256 complete).
Grouped into **121 bursts**, using a new burst after 10 minutes of silence, they fall into four
populations:

| Population | Bursts | Events | Character |
|---|---|---|---|
| **Scheduled**: ~00:36, ~04:10–04:45, ~12:10/12:25, ~20:10/20:25 | 66 | 168 | 1–6 events inside ~5 s, mid codes (8–14), energies ~10k–110k |
| **Afternoon**: ~15:50–18:10 | 38 | 65 | singles over 30–90 min, low energy (median 8.5k), far codes (14–34) |
| **~18:00** (17:55–18:06) | (inside the above) | 9 | single events, mixed codes |
| Everything else | 17 | 23 | scattered |

The scheduled windows are tight. **Fourteen of the 18 00:36 bursts started between 00:35:40 and
00:36:53**, and the other four came at 00:38 (twice), 00:44 and 00:46. The 12:10 and 20:10 bursts
start in the first minute past :10 when they are on time. When they are not, they come at
**:25 instead**, and the two usually shift together on the same day (09-28, 10-04, 10-08). The 04:xx
window sat at 04:30–04:52 until 10-05, then snapped to **04:10:0x–04:10:2x from 10-06 onwards**,
which brought it onto the same 8-hour grid as 12:10 and 20:10.

That is a device with its own clock. Two cautions about what it implies:

- **"Clock-locked" does not mean "programmed for a time of day."** An electronic timer counting
  exact 8-hour intervals from its own power-on looks identical from outside: an 8-hour period
  divides 24 hours, so it repeats at the same wall-clock times forever. The 04:xx jump on 10-06
  looks like something being **reset or power-cycled**, and that could be checked against
  whatever happened in the house on 10-05/10-06.
- **00:36 is not on the 8-hour grid** (20:10 + 4 h 26 m). It is either a second source or a
  second schedule on the same device.

---

## 1. Phase 1: what the recorded data says (done 2026-10-10)

**Method.** For each burst start, I compared each source over a ±2-minute window against eight
control windows offset −120, −90, −60, −45, +45, +60, +90 and +120 min from that burst. A source
scores only if it changes near bursts more often than near its own controls (binomial tail on the
control rate). Each population was scored separately. This controls for both base rate and
time of day; a naive "anything change near 00:36?" does not.

Sources swept:

- `hass_state_change_total` for **every** Home Assistant entity, ~2,000 of them
- `hass_automation_triggered_count_total` for every automation
- `hass_sensor_power_w` for all **80 power series**: Emporia per-circuit, Shellys, `garage_*`
- Loki log volume for **582 streams**: every host's journal, `/var/log`, ZoneMinder, UniFi
- Direct on/off transitions, at 15 s resolution, for 17 circuits: the fridge, the `garage_*`
  circuits, washer, dryer, dishwasher, AC, both furnaces and the outlet circuits

### The afternoon cluster: found. It is the oven.

| | |
|---|---|
| Oven circuits (`emporia_energy_oven2` + `oven4`, 240 V legs) stepping near an afternoon burst | **31 of 38**, against 23% at control times (p ≈ 4×10⁻¹⁴) |
| Oven sessions in the attic period | **10, and every one of them produced events** |
| Events inside oven sessions | **65 in ~13 h of oven use**, about 5/h, against ~0.45/h otherwise |
| Afternoons with no events (09-28, 10-05, 10-08) | no oven use |

The two late-morning oven sessions (10-02 11:45–12:17 and 10-09 11:47–12:28) also explain the
"other" bursts at 11:46–11:58 on those days. The oven sits directly under the attic wing, and the
element relay toggles roughly every 40 s while holding temperature (about 1,160 relay
transitions across the 10 sessions). A relay or contactor breaking a ~2 kW resistive load is a textbook
impulsive source (§10.1, "Relays & contactors").

The 15 s metering cannot say *which* edge (make or break) produces the event, because the
relay toggles roughly every 40 s. Phase 2 settles that in one cooking session.

This also retires the "real distant afternoon convection" hypothesis for most of the afternoon
events. A lightningmaps.org / Blitzortung look at **09-27, 09-29 and 10-06** is still worth
doing, but now to confirm the null rather than to find storms. Do it by hand; the house's
coordinates do not go to any third-party service from a script.

### The ~18:00 cluster: unexplained, and probably scheduled

Nine events between 17:55 and 18:06 fell **outside** any oven session: 09-25 18:00:19,
09-26 18:04, 09-29 18:05, 10-01 17:58, 10-02 17:58, 10-03 17:58, 10-04 17:55, 10-07 18:00:20 and
10-09 18:00:30. Three land at 18:00:2x and four at 17:58. That is a fifth window, probably a timer.
Nothing in the sweep matches it.

### The scheduled bursts: nothing recorded explains them

Every candidate came out at chance:

- **No Home Assistant entity.** After the node's own sensors, the best was
  `light.bedroomlight_light` at 8/66 against 2.5% base. That is unremarkable after ~2,000
  comparisons, and nowhere near the attic.
- **No automation.** None triggers near the windows above its base rate.
- **No metered circuit**, at either a 10 W or a 50 W step. In particular:
  - **The kitchen fridge** (`fridge9a`, ~110 W compressor) cycles about 27 times a day. It
    switched within 60 s of 5 of the 66 bursts, against 6% at control times.
  - **`garage_5`**, an 83 W ↔ 15 W load, probably a garage fridge or freezer: 3/66 against 1%.
  - **The rest:** washer, dryer, dishwasher, AC, both furnaces and every outlet circuit are all at
    chance.
- **No log stream.** No cron, systemd timer, container, camera (`zmc_m*`) or UniFi stream
  logs near the windows above base rate. `kitchenpi`'s `wpa_supplicant` (23/66 against 19%) is the
  only thing kitchen-side that registers, and it is not significant.

**What that leaves:** something that **switches less than ~10 W, or is not metered at all, or runs
on a battery**, and keeps its own time. That is the same blind spot as the noise floor (§11.5):
"not in the power data" means "not a big load", not "not in the house." Plausible classes near
that attic, from §10.1's list:

- a device's own SMPS or relay doing something periodic, such as a defrost-control board, a
  water softener, a smart plug or bulb on a schedule, or a doorbell or garage-door-opener controller
- a small motor on a timer, such as a dehumidifier, condensate pump or air freshener
- an unmetered or neighbour's load on the other side of the wall
- the attic HVAC unit's control board (there is a `shellyflood_attichvac` sensor up there)

Find the device first, then work out the mechanism.

### Decision point 1

The oven is found; Phase 2 only needs to confirm it. **The scheduled source and the ~18:00
source go to Phase 2**, which is cheap because the windows say exactly when to be watching.

---

## 2. Phase 2: cheap physical experiments

All of this uses tools the project already has. Every experiment is timed to a window, so none of
them needs an all-day survey.

### 2.1 Disturbers and noise across the windows: already recording, nothing to run

The MQTT stream only carries `INT_L`. **Since 2026-10-10 ~09:00 the rest is recorded
continuously too:** Home Assistant forwards the node's INFO log lines into Loki, including
"Disturber was detected" and the noise-floor message. So every window from then on already
has its own survey. Running [`ws-log-bridge.py`](../tools/README.md) on top would only add
the node's own WiFi traffic, its worst interferer (§10.1). Use it only when you need its
VERBOSE register-level lines.

[`tools/window-report.py`](../tools/README.md) reads all of it per window: strikes, disturbers,
noise, pipeline health and overlapping oven sessions. Look at whether a burst is the visible
tip of a longer disturbed period (disturbers or noise for minutes either side), which points to
a device *running*, or a single sharp cluster, which points to a *switching* event.

First read, 2026-10-10: the **04:10 window did not fire** on 10-10, its first miss since it
moved onto the 8-hour grid on 10-06. One miss is not a pattern; it is worth watching whether
the 8-hour source is drifting or has gone quiet.

**Liveness first.** §11.10 still owes the attic its emulator check. Run it in the same visit, or a
quiet survey proves nothing (§11.7).

### 2.2 The oven: confirm in one cooking session

Run a survey from preheat to off, then match each event to the oven's relay edges. Use the Emporia
15 s data, or better, listen for the click. Run the **A′ control** (§11.3) by running the
oven again on another day with no survey. This is mostly a formality given 10/10 sessions, but it
settles make versus break, and it is the reference result for tuning (§2.5).

### 2.3 Elimination by switching things off, timed to a window

Turn off one candidate a few minutes before a window, leave it off across the window, and
restore it. Repeat on a following day with the same candidate **on** (the control). Order by
proximity to the attic, closest first, because coupling falls off as 1/r³ (§10.1):

1. Anything in the garage on a plug or timer: the `garage_5` fridge/freezer, the garage-door
   opener controller, chargers and battery-tool docks, the compressor's controller board
2. The kitchen fridge (`fridge9a`), the breakfast-room `brkfstvero`, and `kitchenpi`
3. The laundry: washer and dryer control boards on standby, and any dehumidifier or
   condensate pump
4. The attic HVAC unit (the breaker for its control board, not just the thermostat)

The 00:36 window is the easy one: it fires 18 days in 18. Kill a whole **breaker** across 00:30–00:45
and one night answers "is it on this circuit?". That is §10.1's breaker-by-breaker ladder, made
cheap by the timetable. Keep `fridge9a` and the freezer breaker-off periods under 20 minutes.

**What happened on 10-05/10-06?** The 04:xx window moved then. Anything plugged in, reset,
power-cycled or re-scheduled that day is a suspect worth checking before any of the above.

### 2.4 Move or rotate the sensor at a window

The SEN-39003 is a directional loop (§10.1). On the cable it can be **rotated independently**
of the ESP32 (§16):

- **Rotate 90° between consecutive windows** (e.g. 12:10 at 0°, 20:10 at 90°). A burst that
  disappears at one orientation gives a bearing line. Two positions give a fix (see
  `sdr-interference-hunting.md` §3 on the 180° ambiguity).
- **Move the sensor box across the attic** on a longer patch cable. The burst energy for the
  same window rising or falling with position points towards or away from the source.

⚠️ Change **one thing per window**, and leave at least one window untouched between changes.
Handling the build has fooled this project before (§11.3).

### 2.5 The closet as a control

If 2.3 and 2.4 have not localised it, move both boxes back to the bedroom closet for **two or
three days**. Nothing else should change. The closet saw nothing outside storms for four days
(§11.9).

- **Bursts stop:** the source is at the attic site. This is the expected result, but it should
  be confirmed before buying anything.
- **Bursts continue at the same times:** the source is house-wide, either mains-conducted or a
  strong radiator, or it is the node itself. That reverses the whole search.

### 2.6 What tuning would do, and when to try it

`indoor: false` and a higher `spike_rejection` may well suppress all of this. **Try them only
after the sources are known**, and use the scheduled windows and an oven session as the
before/after measure. If the scheduled source is still unidentified, tune *one* knob and check
whether the 00:36 burst still appears. A threshold that removes it has a measured margin. One that
removes it by luck will not hold.

### Decision point 2

- **Source found by 2.3:** done. Unplug it, confirm the window goes quiet, plug it back in,
  confirm the window returns (the A′ control).
- **2.4 gives a bearing but nothing on it switches off:** go to Phase 3 with that bearing.
- **2.5 shows the bursts follow the node:** the problem is the build or the house wiring, not
  the attic. Repeat Phase 1 against the closet data before buying an SDR.
- **Nothing localises:** Phase 3.

---

## 3. Phase 3: SDR and direction-finding loop, timed to the windows

Use [`sdr-interference-hunting.md`](sdr-interference-hunting.md) for what to buy, how to wind
and tune the loop, and the driver setup. All of that applies unchanged. Two things change in
method:

**This is a far easier target than the noise floor that document was written for.** §11.5's
noise floor had no schedule, so the guide's method centres on long `rtl_power` runs correlated
against survey buckets. Here the source tells you when it will transmit, to within a minute:

1. **Correlate first, but cheaply.** Log `rtl_power` beside the sensor across one 00:36 window
   (00:30–00:45, 1 s integration, `-f 450k:550k:1k -i 1`). A band-power spike at the burst
   seconds, and nowhere else, confirms the SDR sees what the AS3935 sees. That takes one night,
   not several hours of buckets.
2. **Then direction-find in the windows only.** Be in position, loop tuned, waterfall up, at
   00:35, 04:09, 12:09 and 20:09. Take a null bearing at one position per window. Each window
   lasts only seconds, so plan the position before the window rather than hunting during it.
   Two bearings from well-separated points (the attic hatch and the garage floor, say) cross on
   the source.
3. **Characterise what you see.** A single broadband click is a relay or contact. A burst of
   hash lasting seconds is a motor start or an SMPS start-up. A carrier is a transmitter, and
   unlikely given it only appears in the windows.

The oven is a free calibration target for all of this. Before chasing the unknown source, check
that the loop nulls on the kitchen from the attic and from the garage, while the oven is cycling.

**Keep your own kit out of it** (guide §5.4): laptop on battery, as far from the loop as the
cable allows, and re-check any bearing with the laptop moved.

### Decision point 3

- **Bearing crosses on a device:** switch it off across a window, then back on (A′). Record it in
  §11.11.
- **Bearing crosses off-property:** it is a neighbour's device. The remedies are relocation within
  the attic (towards a null), the closet, or tuning against the measured 00:36 burst (§2.6).
- **SDR sees nothing in the window while the AS3935 fires:** the coupling is conducted, not
  radiated. Go back to breaker isolation (§2.3) and the power-bank test (§10.1 step 2).

---

## 4. Record-keeping

For every experiment, note the window, what changed, and whether the burst appeared, with its
`(boot, seq)` range from the MQTT stream. The stream is lossless, so a window with no burst is a
real zero, **provided the bridge's health metrics read 1 throughout** (`lightning_node_status`,
`lightning_bridge_mqtt_connected`, `up{job="lightning"}`) and **the sensor's liveness has been
checked** (§11.7). Without both, a quiet window means nothing.
