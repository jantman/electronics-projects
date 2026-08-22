# AS3935 Lightning Detector Node — Project Documentation

*Per-strike lightning detection for Home Assistant / ESPHome*
*Compiled July 2026; last updated 2026-08-21*

---

## Project status — read this first

**Working:** the sensor detects, over SPI, interrupt-driven. The ESPHome node runs headless in the garage attic on WiFi and streams `INT_NH` / `INT_D` / `INT_L` events. The measurement tooling in `tools/` is trustworthy and reproducible over the network (§11.4).

**Hardware revision 2 is specified and ready to build (§16):** two enclosures, sensor on a swappable Cat5 patch cable, USB power. The mains supply was built and abandoned — see §5.

**Two things block progress, and neither is the sensor:**

1. **The build is a solderless breadboard, and it is not a valid measurement platform (§10.2, §11.3).** Its interference floor dropped by two thirds the moment the build was physically handled, and stayed down. Every number measured on it — including thirteen hours of beautifully stable data — describes the breadboard at least as much as it describes the attic. **A protoboard rebuild is a prerequisite for every remaining question**, not one task among several.
2. **The per-strike path into Home Assistant does not work (§8.4).** The Storm Alert binary sensor pulses for ~10 ms and Home Assistant never registers it: zero state changes across 34.7 hours and thousands of detections. Per-strike events in HA are the entire point of the project, so this is a headline defect, not a detail. The fix is understood and not yet applied.

**Never validated:** the detector has never seen a real strike. Every `INT_L` recorded so far is believed false. The SEN-39002 emulator proves the interrupt path but is always classified a disturber (§11.1), so **there is no bench substitute for a live storm.**

**Current configuration is bench-tuned, not deployed** — `indoor: true` and `spike_rejection: 1` are leftovers from emulator work (§11.1). Every rate quoted in §11.3 is a worst case for that configuration, not for a tuned one.

---

## 1. The idea and motivation

A newly installed **Ecowitt WS90** weather station (temporarily at ground level, awaiting roof mount) includes a lightning sensor, but the Ecowitt ecosystem only exposes **aggregate** data: number of strikes today, time of the last strike, and distance of the last strike. During a very active, very nearby thunderstorm this smears closely-spaced strikes together and misses individual close events.

**Goal:** capture and log *individual* strikes locally, with approximate distance, as fast as possible per strike, integrated with Home Assistant — cheaply.

## 2. The key insight

The WS90's lightning sensor is an **AMS/ScioSense AS3935 "Franklin" chip**, and that chip raises a hardware interrupt (IRQ) on *every* event it classifies. The limitation is Ecowitt's **data exposure** (aggregation), not the sensor. The fix is therefore to run our own AS3935 and read its per-strike interrupt directly — no new detection technology required.

An inherent AS3935 limit to keep in mind: it resolves roughly **one event per second**, and after classifying a disturber it deactivates for ~1.5 s. So no single-AS3935 solution captures every strike in an intense close storm. Since the accepted goal is *approximate distance, fastest per-strike*, this limit is acceptable — it caps how many rapid strikes are caught, not how fast each caught one is reported.

## 3. Options considered (the discussion)

| Option | Verdict |
|---|---|
| **DIY AS3935 + ESP32 + ESPHome (SPI, IRQ-driven)** | **Chosen.** Direct per-strike events, local, cheap, in-wheelhouse. |
| Blitzortung HA integration (crowd network) | Great free geolocated data, but network-dependent, not a local sensor. |
| Host a Blitzortung station (System Blue/Mini) | Endgame hobby project; a *network* contributor, not a local counter. |
| Boltek LD-350 / StormTracker / EFM-100 | **Rejected:** >$1000 and Windows-centric software. Also, single-station RF gives an *estimate*, not true distance. |
| Flash-to-bang (optical + acoustic timing) | The only genuinely *true* local distance method, but rejected — only approximate distance was wanted, and it can't range distant strikes. |

**Why the pre-calibrated DIY board:** the AS3935's antenna must be tuned to 500 kHz. A pre-calibrated board ships with its per-board tuning capacitance printed on the label, eliminating the tuning procedure.

## 4. Final design overview

**Revision 2 — two enclosures, no mains.** Superseded the single-box mains design; see §16 for the reasoning and §7 for the wiring.

```
  MAIN ENCLOSURE                                 SENSOR ENCLOSURE
  ┌────────────────────────────┐                 ┌──────────────────────────┐
  │ USB brick (2-3 A)          │   Cat5 patch    │  RJ45 jack               │
  │   │ short, thick cable     │   0.3 - 3 m     │    │ 5 V                 │
  │   ▼                        │  ┌───────────┐  │    ▼                     │
  │ ESP32 dev board  ──────────┼──┤ RJ45 jack ├──┼─► 100 Ω ─► bulk cap      │
  │   + 5 V bulk cap at pin    │  └───────────┘  │    ▼                     │
  │                            │   5V GND SCLK   │  MCP1700 LDO (3.3 V)     │
  │                            │   MISO MOSI     │    ▼                     │
  │                            │   CS  IRQ  GND  │  1 µF ∥ 100 nF           │
  │                            │                 │    ▼                     │
  │                            │                 │  SEN-39003 (AS3935)      │
  └────────────────────────────┘                 └──────────────────────────┘
     vented (§9)                                    sealed, SELV only
```

- **Detection:** Playing With Fusion SEN-39003 (AS3935), SPI, interrupt-driven.
- **Compute/network:** ESP32 dev board on WiFi (PoE was not feasible at the site).
- **Power:** quality 2–3 A USB brick. **The mains design was built and abandoned** — see §5 and §16.
- **Interconnect:** Cat5 patch cable on RJ45, 5 V sent down the cable and regulated at the sensor.
- **Firmware:** ESPHome native `as3935_spi` component → per-strike events into Home Assistant (**note §8.4: that last hop does not currently work**).

**The separation distance is deliberately a variable, not a decision.** §11.3 never identified the interference source, so the sensor box is on a swappable patch cable specifically to measure how much distance from the ESP32 and supply is worth. See §16.

## 5. Hardware

### Sensor — Playing With Fusion SEN-39003
- Replaces the discontinued SEN-39001 (adds Qwiic connectors; otherwise identical).
- Sensor IC: AS3935. Interface: SPI or I²C (**SPI by default**).
- Supply: 2.4–5.5 V. Operating temp: −40 to +85 °C. Board: 25 × 23 mm.
- Range ~40 km; distance reported 1–40 km in 14 steps.
- **Ships fully calibrated**; per-board tuning capacitance (pF) printed on the label.
- Requires the 0.1″ breakaway header (≈ $0.50 add-on) soldered on.
- **Wire via SPI, not Qwiic** — the Qwiic path cannot send the interrupt, which defeats the purpose.

### Tester — Playing With Fusion SEN-39002
- Arduino-shield lightning emulator; mimics near/medium/far strikes at ~4–15 cm (start ~7 cm).
- An MCP4725 I²C DAC drives an air-core coil with a decaying staircase — **no RF oscillator**. Near/mid/far are 1/2/3 replays of the *same* burst; only total energy differs.
- The driver writes to **both `0x62` and `0x64`**, which looks like two DACs but isn't: those are the MCP4725**A1** and **A2** part variants, and the board carries one. A bus scan of this board finds only `0x64`. The NAK from the absent address is part of the calibrated step timing — don't remove it. See the emulator README §4.
- **Stacks directly on a spare Arduino Uno R3** — it's an Arduino shield, so there is no wiring at all. `sen39002-emulator-uno/` is PWFusion's reference sketch with the serial-label bug fixed and keyboard control added; see [that README](sen39002-emulator-uno/README.md).

### Power supply — USB brick (the IRM-02-5 was built and failed)

**Rev 2 uses a quality 2–3 A USB brick.** The mains design got as far as being built and did not work.

- **Mean Well IRM-02-5 — built, insufficient, abandoned.** 5 V / 400 mA / 2 W. ESP32 WiFi TX bursts approach 500 mA, which at 5 V is ~2.5 W against a 2 W supply. It browned out. A 2–3 A USB supply fixed it immediately.
- **The warning was already in this document and was not acted on.** The line "400 mA is tight for an ESP32 on WiFi (TX bursts approach ~500 mA)" sat in this section while the part stayed in the BOM. A margin note that says the part is marginal *is* a rejection; treat it as one.
- **IRM-05-5 (1 A) and IRM-10-5 (2 A) are on hand** if mains is ever wanted. Prefer the 5 W part: a very lightly loaded SMPS tends to drop into burst/pulse-skipping mode, whose low-frequency broadband modulation is plausibly worse for a 500 kHz magnetic sensor than steady switching. Verify against the derating curve at 52 °C ambient before trusting the 1 A figure.
- **Why USB is acceptable despite §9's thermal argument.** That argument still stands — cheap bricks use 85 °C electrolytics and a 52 °C attic shortens their life. It is outweighed here by three things: the two-box layout moved the supply away from the antenna, so the *EMI* case for an industrial part evaporated; the failure mode is loud (the node drops off WiFi and Home Assistant shows it offline immediately); and attic access is a walk-out door, not a crawl. **The brick is a consumable.** Use a decent one, not the cheapest in the box.

## 6. Bill of materials (final, DigiKey part numbers)

| Function | Part | Notes |
|---|---|---|
| Sensor | Playing With Fusion **SEN-39003** | Pre-calibrated AS3935 breakout |
| Tester | Playing With Fusion **SEN-39002** | Emulator shield; stacks on a spare Arduino Uno R3 |
| MCU | ESP32 dev board | WiFi |
| PSU | **2–3 A USB brick** | See §5. The IRM-02-5 was built and browned out. |
| USB cable | **≤1 m, 20–24 AWG power conductors** | Not incidental — see §7.4. Thin/long cables reproduce the brownout. |
| Sensor-rail LDO | Microchip **MCP1700-3302E/TO** | 3.3 V, TO-92. **`E` = −40/+125 °C grade**, required for the attic. |
| Interconnect | **Cat5/Cat5e patch cables**, 0.3 / 1 / 2 / 3 m | Pre-made so length is the only variable (§16) |
| Connectors | 2 × **RJ45 panel jacks** | Wired T568B per §7.1 |
| Enclosure ×2 | Non-metallic | Main (vented) + sensor (small, sealed) — §9 |
| 5 V bulk cap | Nichicon **UPW** series, 470–1000 µF, 16–25 V, 105 °C | e.g. UPW1C471MPD. (Panasonic EEU-FR1C471 was out of stock.) |
| Sensor-rail bulk cap | Panasonic **EEU-FR1H470** | 47 µF, 50 V, 105 °C |
| Ceramic 100 nF | Kemet **C320C104K5R5TA** | X7R, closest to sensor |
| Ceramic 1 µF | Kemet **C330C105K5R5TA** | X7R, mid-band |
| Series resistor | 100 Ω, ¼ W metal film | RC filter element |
| Ferrite bead | Murata **BLM18AG601SZ1D** | 0603, 600 Ω @ 100 MHz; optional/complementary |


**Mains parts — not used in rev 2.** Retained because the design in §7.3 is drawn and built, and because the IRM-05-5/IRM-10-5 are on hand if the USB brick ever proves inadequate.

| Function | Part | Notes |
|---|---|---|
| PSU (mains variant) | Mean Well **IRM-05-5** or **IRM-10-5** | On hand. Prefer 5 W — see §5. |
| Fuse | Littelfuse **0215.250MXP** | 250 mA, 250 VAC, 5×20 mm, ceramic, time-lag |
| Fuse holder | Littelfuse **345621** | Panel mount, 12.7 mm hole |
| MOV | Littelfuse **V150LA10AP** | **150 VAC** (correct for 120 V line), 14 mm |

**Do NOT use:** Fair-Rite **5943003801** — this was mis-specced earlier; it is a 2.4″ FT-240 balun/power toroid, absurdly oversized for a sub-milliamp rail. The Murata 0603 bead replaces it. If a no-solder option is still wanted, a **small-bore (3–5 mm) clip-on ferrite** with **2–3 turns** of the 3.3 V wire looped through it works fine — bore size and turns matter far more than material (generic NiZn is fine here).

## 7. Wiring

### 7.1 The RJ45 interconnect (main box ↔ sensor box)

Seven signals plus one spare conductor. `SI` is **not** carried on the cable — it ties to GND locally at the sensor board (it must be grounded to select SPI; §5).

Wired **T568B** at both ends so any pre-made patch cable works. The cable's twisted pairs are (1,2), (3,6), (4,5), (7,8), and the assignment below deliberately spends the spare conductor on a **second ground paired with SCLK**, so the fastest edge gets its own return path.

| Pin | T568B colour | Signal | ESP32 pin | Sensor pin |
|---|---|---|---|---|
| 1 | white/orange | **5 V** | `5V` rail | to LDO input (§7.2) |
| 2 | orange | GND | `GND` | GND |
| 3 | white/green | **SCLK** | GPIO18 | SCLK |
| 6 | green | GND | `GND` | GND |
| 4 | blue | MOSI | GPIO23 | MOSI |
| 5 | white/blue | MISO | GPIO19 | MISO |
| 7 | white/brown | CS | GPIO5 | CS |
| 8 | brown | IRQ | GPIO4 | IRQ |

- **Use plain UTP, not shielded.** A shield bonded at both ends makes a ground loop, and it would do nothing against magnetic coupling anyway.
- **Set `data_rate: 200kHz`** in the YAML. `as3935_spi` inherits the standard SPI device schema, so this is settable; it **defaults to 1 MHz**. The traffic is a handful of single-byte register reads per event, so 200 kHz is far more than enough and it makes reflections over a few metres a non-issue. Series termination (33–100 Ω at the ESP32 end on SCLK/MOSI/CS) then becomes optional belt-and-braces.
- **IRQ over a long cable is safe.** The component *level-reads* the pin in `loop()` rather than edge-triggering, so added cable capacitance cannot cost you an interrupt.
- ⚠️ **This is not Ethernet.** The jack carries 5 V and SPI. Plugging it into a live PoE switch port puts 48 V onto those lines and destroys both the ESP32 and the sensor. Accepted knowingly in exchange for certified pre-made cables — which the §16 distance sweep needs, since hand-terminated cables would add a variable per length. Label both ends.

### 7.2 Sensor rail: regulate at the sensor, not at the ESP32

**5 V travels down the cable; 3.3 V is generated at the sensor.** All of this lives in the sensor enclosure, within a few centimetres of the AS3935:

```
RJ45 pin 1 (5 V) ──► 100 Ω ──► 10-47 µF ──► MCP1700-3302E ──► 1 µF ∥ 100 nF ──► sensor VDD
                                                                (100 nF nearest the pin)
```

- **In the main box**, the 5 V bulk cap (C1) still mounts physically at the ESP32 `5V`/`GND` pins. It is the local reservoir for WiFi bursts, and it matters *more* with a USB supply than it did with mains — see §7.4.
- **The 100 Ω costs ~0.1 V** at the sensor's sub-1 mA draw. Free.
- **The 1 µF output cap is not optional** — the MCP1700 requires it for stability.
- **Why a linear regulator specifically:** a *switching* regulator would put a 100 kHz–1 MHz noise source centimetres from a 500 kHz magnetic antenna, which is the worst possible place for one. A linear regulator has no switching node. The wasted heat is nothing at 1 mA.
- ⚠️ **The LDO does not replace the passives, it complements them.** LDO power-supply rejection is strong at low frequency — droop, WiFi burst sag — and **falls off well before 500 kHz**. The LDO handles the low-frequency junk the cable delivers; the RC and the ceramics handle the band the AS3935 actually cares about. Neither alone is sufficient.
- **Honest caveat:** at under 1 mA, well-filtered 3.3 V over twisted pair with good decoupling would very likely also work. The LDO is 50 cents of insurance placed exactly where this project has repeatedly been burned; it is not a proven necessity.

### 7.3 AC mains side — built, not used in rev 2

**Retained for reference.** This was built and works as drawn; it was abandoned only because the IRM-02-5 behind it was undersized (§5). If mains is ever revisited with the IRM-05-5, this section and the §12 safety rule apply again unchanged.

`cord → fuse (Line only) → MOV across L–N (after the fuse) → IRM-0x-5`

- Fuse in the **Line** conductor only, ahead of everything.
- **MOV across Line–Neutral, downstream of the fuse** (electrically the T2 / AC-L node), so the fuse also protects against the MOV's end-of-life short. Land the MOV lead at a junction on the fused-line run — *not* on the upstream side of the fuse, which would leave the MOV unfused.
- **Ground:** capped off, not bonded — the IRM-02-5 is a 2-wire isolated supply and the enclosure is plastic, so `−Vo` is the (floating) DC common, not earth.
- Sleeve every AC terminal; keep ≥ 6 mm from any DC wiring.

### 7.4 The USB cable is a circuit element, not an accessory

It can reproduce the exact brownout the IRM-02-5 caused, by a different route.

Many cheap USB cables use **28 AWG** power conductors (~0.21 Ω/m). Over 2 m, counting both the 5 V conductor and the ground return, that is ~0.84 Ω. At a 500 mA WiFi burst it drops **~0.42 V**, so 5.0 V at the brick arrives as 4.58 V at the board — and the dev board's AMS1117 needs over a volt of headroom to hold 3.3 V. Thinner or longer puts you into brownout.

- **≤1 m, with 20–24 AWG power conductors.** Cables sold as "3 A" or "fast charge" generally have the heavier gauge. Avoid thin charge-only cables and avoid extensions.
- **Measure, don't assume.** §12 already says to check 5.0 V at the `5V` pin; that check now covers the cable. Confirm it stays comfortably above ~4.7 V *during* WiFi activity, not at idle.
- **Don't bother with a clip-on ferrite** — §13 established that ferrites are nearly transparent at 500 kHz.
- **Route the USB cable away from the Cat5 run.** Do not bundle them parallel.
- **Treat the cable as a fixed experimental variable.** Pick one, label it, keep it across every survey. Swapping cables between runs is exactly the kind of silent uncontrolled change that produced the §11.3 retraction.

## 8. ESPHome configuration notes

Native `as3935_spi` component. Full config is in `lightning-detector.yaml`. Key parameters:

- **`capacitance`** — **not in pF.** ESPHome takes the raw `TUN_CAP` register value: *8 pF steps*, valid range **0–15**. Take the pF value printed on the board label and **divide by 8** (round to nearest step if it isn't a clean multiple). This board's label reads **72 pF → `capacitance: 9`**. Entering pF directly fails validation with `must be between 0 and 15`. This is the payoff of the pre-calibrated board.
- **`indoor`** — `true` while bench testing indoors; **`false` for the final attic/outdoor deployment** (outdoor AFE gain).
- **`lightning_threshold: 1`** — report every strike.
- **`noise_level` (1–7) / `watchdog_threshold` (1–10) / `spike_rejection` (1–11)** — raise to reject noise/disturbers if needed. Note the minimums are 1, not 0.
- **`mask_disturber`** — `false` during testing (so you can see disturbers), `true` in production to quiet them.
- **`tune_antenna`** — set `true` once to confirm the written capacitance in the log, then back to `false` (detection is disabled while true).
- **`calibration`** — RCO calibration at startup; default `true` and should stay `true`. `tune_antenna` already takes precedence over it in the component's `setup()`, so there's no reason to disable it manually.
- **`div_ratio`** — accepts `0/16/32/64/128`. The schema default `0` hits a `default: return;` branch and writes *nothing*, leaving the chip's power-on ÷16; passing `16` writes ÷16 explicitly. Same result, but explicit is better.

### ⚠️ 8.1 `spi_mode: MODE1` is mandatory

**Without it the sensor never reports anything.** This cost a bench session, so it leads the section.

The AS3935 is a Mode 1 SPI part (CPOL=0, CPHA=1). SparkFun's library — which ESPHome's component was ported from, comment-for-comment — uses `SPI_MODE1`. But `as3935_spi.h` declares `CLOCK_POLARITY_LOW` + `CLOCK_PHASE_LEADING`, which is **Mode 0**, and nothing overrides it unless `spi_mode: MODE1` is set in YAML.

In Mode 0 the ESP32 samples MISO on the rising edge — the same edge the AS3935 changes it on — so **every byte reads back shifted right one bit**.

The symptom is unmistakable once you know it. With `level: VERY_VERBOSE` you get this, forever, with nothing else:

```
[V][as3935:192]: Calling read_interrupt_register_
[V][as3935_spi:040]: read_register_: 2
```

`loop()` only calls `read_interrupt_register_()` while the IRQ pin reads HIGH, then matches the value against `1` (noise), `4` (disturber) and `8` (lightning). **`2` is not a valid AS3935 interrupt code**, so all three branches fall through silently — no log line, no published state. `2` is disturber (`4`) shifted; lightning (`8`) would read as `4` and be reported as a *disturber*.

### 8.2 Other unfixed defects in the ESPHome component

The component genuinely is buggy — this is not just the pF-vs-8 pF confusion above. [ESPHome issue #10455](https://github.com/esphome/esphome/issues/10455) documents several defects; it was **closed `NOT_PLANNED` by the stale bot in March 2026 with the fix never merged**, and all of the following are still present in `dev`:

| Defect | Effect |
|---|---|
| `write_div_ratio` has `case 22:` where the AS3935 value is **32** | `div_ratio: 32` is unreachable. `16` (our setting) is unaffected. |
| Storm Alert binary sensor pulses `true` for only **10 ms** | May be too short to reliably fire a Home Assistant automation. Watch for this when building automations. |
| `get_distance_to_storm_()` publishes the raw `REG0x07[5:0]` code straight to the distance sensor, in km, with no interpretation | That register is a **table of codes, not a linear value**. `1` = storm overhead and `63` = *out of range* (lightning classified, distance not estimable). So an out-of-range event lands in Home Assistant as a **`63 km` strike**, which reads as a plausible distant storm and is not one. Only `5`–`40` are real distances. Observed live on 2026-08-19. |

**The "inverted mask" complaint in #10455 is *not* a live bug — verified.** ESPHome does `write_reg &= (~mask)` where SparkFun does `&= mask`, but ESPHome also inverted the mask *constants*, so the two changes cancel and every live path is correct. Checking all twelve constants against SparkFun's, eight are inverted correctly and four are not — but of those four, `LIGHT_MASK` and `DISTURB_MASK` are **dead code** (the functions that would use them pass explicit literal masks instead), `DIV_MASK` appears only on a read path where the un-inverted value is correct, and `CAP_MASK` lands correctly from a power-on reset because `TUN_CAP` starts at 0.

Practical upshot: **every `as3935_spi:` option in this config is written to the chip correctly.** If detection misbehaves, tune the sensor — don't go patching the component.

### ⚠️ 8.3 Changing `capacitance:` requires power-cycling the *sensor*

The one place `CAP_MASK` can still bite. `write_capacitance` reads `REG0x08`, keeps the existing `TUN_CAP` nibble (it should clear it), then ORs the new value in — so the register ends up holding **`old | new`**, not `new`.

An ESP32 reset (EN button, OTA, `restart` button) does **not** power-cycle the AS3935 — it stays powered from 3V3 and keeps its registers. Serial confirms this: on a warm boot the read-before-write returns `9`, the value left over from the previous run, and `9 | 9 = 9` so it looks fine.

It only looks fine because the value didn't change. Go from `9` (72 pF) to `6` (48 pF) on a warm reset and you get `9 | 6 = 15` → **120 pF**, silently detuning the antenna.

**After changing `capacitance:`, remove power from the sensor** (unplug USB/mains, don't just reset) so `TUN_CAP` starts at 0. Then confirm with the `read_register_:` value logged right after `Setting tune cap to N pF` — that's the read-before-write, so on a cold boot it should be `0`, and the *next* boot's read should equal your new setting.

If these bite, the options are an `external_components` override with a patched copy, or the PWFusion Arduino sketch bridged to MQTT.

**On verifying capacitance:** note that the `Setting tune cap to N pF` line is computed in software (`capacitance * 8`) and printed *before* the write — it confirms what ESPHome intended, not what the chip stored. It is still worth checking, but it is not proof. Set `logger: level: VERY_VERBOSE` and confirm the log line reads **`Setting tune cap to 72 pF`** (the component logs `capacitance * 8`, so 9 → 72). If it prints anything other than your label value, that's a genuine bug — fall back to PWF's Arduino SPI sketch bridged to MQTT.

⚠️ **This check requires a serial connection — it is not visible over WiFi at any log level.** The line is printed from `setup()`, before the API is up. See **§12.1** for the procedure and the reason.

### ⚠️ 8.4 The per-strike path to Home Assistant does not work

**This is the project's core deliverable failing, and it is not a sensor problem.** Verified 2026-08-20.

`binary_sensor.esp32_lightning_sensor_storm_alert` had a `last_updated` stamp equal to the node's boot time after **34.7 hours of uptime and thousands of `INT_L` events**. Home Assistant had recorded zero state changes for it. The same applies to `Lightning Distance`, though for a benign reason — every event published the identical value `63`, and HA does not advance `last_updated` for an unchanged state.

What was checked, in order, so the next person does not repeat it:

| Hypothesis | Test | Result |
|---|---|---|
| Binary sensor not linked to the component | `dump_config()` only logs "Thunder alert" when the pointer is non-null | **Linked.** `[C][as3935:016]: Thunder alert 'Storm Alert'` is present. |
| Device is not publishing | Watch the API log stream during a detection | **It publishes.** `'Storm Alert' >> ON` at 05:28:57.119, `>> OFF` at 05:28:57.198. |
| Node→HA path is broken generally | Compare against another entity on the same node | **Healthy.** `wifi_signal_db` from the same node updates every 60 s. |

So the device emits the pulse and HA never records it. Note the measured gap was **79 ms, not the 10 ms** the component intends — `set_timeout(10, ...)` fires late because the loop is saturated (the baseline hour pushed 63,300 log lines, ~17/s, at `VERY_VERBOSE`). Even 79 ms does not survive the trip.

Whether Home Assistant drops the update or coalesces the ON and OFF into a single no-op write was **not** determined; distinguishing them needs HA-side logs (available in Loki). The practical consequence is identical either way: **no automation can trigger on Storm Alert as configured.**

**The fix is not a longer pulse — it is not using a pulse at all.** An ESPHome-side `on_press` automation incrementing a counter sensor keeps everything on-device, where 79 ms is ample, and publishes a monotonically increasing value. Every strike then produces a genuine state change HA can trigger on, and the counter is independently useful. Not yet implemented — deliberately deferred until the hardware is trustworthy.

Note the interaction with §8.2: because a false `INT_L` publishes distance `63` and energy `0` every time, **none of the three entities currently changes value between events.** With real, varied strikes distance and energy would at least move, but Storm Alert would stay unreliable.

## 9. Enclosures (two, in rev 2)

Both **non-metallic** — the AS3935's 500 kHz loop antenna must not be shielded or detuned. Confirm no metal faceplate or conductive coating on either.

### Sensor enclosure

Small, and **SELV only** — it carries nothing but 5 V and SPI, which is what lets it be mounted anywhere without any of the §12 mains concerns.

- Contents: SEN-39003, MCP1700 LDO, the §7.2 passives, RJ45 panel jack. That is all.
- **Sealed is fine** — it dissipates essentially nothing, so unlike the main box there is no bake risk, and an attic is dry.
- Sensor PCB on **nylon standoffs**, antenna clear of the box screws and of the RJ45 jack's metal shell.
- **Mechanically rigid.** §11.3 is a warning here: if flexing the box moves the noise floor, the build is furniture rather than an instrument. §15 Phase 2 tests exactly this.

### Main enclosure

- Contents: ESP32 dev board, 5 V bulk cap at its pins, RJ45 panel jack, USB entry.
- **Vent it.** The attic peaks ~52 °C and this box has active dissipation; a sealed box bakes. A few screened holes for convection — the usual outdoor sealing logic inverts here because the attic is already sheltered from rain.
- **105 °C electrolytics** are mandatory at that ambient. Every ~10 °C over rating roughly halves electrolytic life; at 52 °C plus self-heating, 105 °C parts last years where 85 °C parts fail in a couple of summers.
- USB cable entry through a grommet or cord grip, with strain relief.
- No fuse holder in rev 2 — that was for the mains variant (§7.3).

## 10. Mounting location

**Chosen: the garage / breakfast / laundry attic** (over the single-story wing).

Site-selection priority for the AS3935: low *continuous* EMI, distance from large metal masses, install/tuning access, then thermal. Height is irrelevant (500 kHz is not line-of-sight).

- **Garage-side attic (chosen):** easy access, easy power/network, and its noise sources (washer/dryer, garage-door opener, microwave) are *intermittent* — friendlier to the AS3935's disturber rejection than a continuous source. Check for a continuous garage fridge/freezer compressor or EV charger near the spot.
- **Main 2-story attic (rejected):** the furnace/HVAC (especially a variable-speed ECM blower) is a *continuous* broadband EMI source, plus metal ductwork. The DTV antenna and 900 MHz Ecowitt gateway antenna are **not** RF interferers (spectrally far from 500 kHz) — only metal masses to clear by 2–3 ft — but the HVAC plus harder access made this the worse choice.
- **Master-bedroom wing attic:** inaccessible → out.

**Placement within the attic:** low near the ceiling joists (cooler; away from any foil radiant barrier), in the corner farthest from the laundry appliances and garage-door opener. The build can be relocated to try several spots.

**Thermal:** both accessible attics peak ~125 °F (52 °C); 2-year data confirms that as the high. The AS3935 and ESP32 are rated to 85 °C — fine. Electrolytics are **105 °C-rated** (every ~10 °C over rating roughly halves electrolytic life; at 52 °C ambient plus self-heating, 105 °C parts last years where 85 °C parts fail in a couple of summers).

**Empirical site survey:** run the node in each candidate spot for a day (spanning HVAC/laundry cycles) and log the AS3935 interrupt rate to rank spots from data rather than theory. **Rank by ambient `INT_L` (false lightning), not by disturber rate** — see §11.2 for why the obvious metric is the wrong one. `tools/ambient-survey.py` is the instrument, and it reads a piped log stream as happily as a serial port, so the node can stay where it is mounted:

```bash
esphome logs lightning-detector.yaml | tools/ambient-survey.py --stdin --minutes 60 --bucket 300
```

The messages it counts all come from `loop()` and stream over the API normally (contrast §12.1, where the one `setup()` line genuinely needs serial).

### 10.1 What actually interferes, and how to hunt it

Written after the bench measured 3–8 *false lightning* classifications per minute (§11.2) — with the §7.2 RC filter correctly built, so this is not a power-filtering problem.

**Two physical facts drive everything here:**

- The AS3935 is a 500 kHz resonant **loop antenna** — a near-field *magnetic* sensor, not a conventional RF receiver. Near-field coupling falls off as **1/r³**, so a feeble source 30 cm away beats a powerful one across the room. **Proximity dominates.**
- It hunts **impulsive broadband transients with energy near 500 kHz**. Continuous narrowband emitters far from that frequency are largely irrelevant — which is why the 900 MHz Ecowitt gateway and the DTV antenna are *not* interferers.

**Ranked suspects:**

| Source | Why | Character |
|---|---|---|
| **Switch-mode supplies (any)** | Most switch at 100–500 kHz; lower-frequency ones hit the band on harmonics (65 kHz × 8 ≈ 520 kHz). Phone chargers, wall warts, laptop bricks. | Continuous |
| **Laptop + its charger** | The bench's prime suspect once USB-powered — DC-DC converters plus the brick, coupled straight to the sensor supply. | Continuous |
| **Qi wireless chargers** | 87–205 kHz at high field strength; **3rd harmonic lands on 500 kHz**. Brutal if nearby, and easy to overlook. | Continuous |
| **HVAC (ECM / inverter)** | 4–20 kHz PWM with ~50 ns edges → spectrum well past 500 kHz, running *continuously*. Contactor closing is a separate impulse. | Both — worst class |
| **LED drivers** | Every one is a small SMPS (50–200 kHz + harmonics). Cheap dimmable bulbs worst; PWM dimming adds sharp-edged modulation. | Continuous |
| **Class-D amplifiers** | Switch at 250–500 kHz — one of the few consumer devices whose *fundamental* sits in band. Class-AB linear amps are nearly silent. | Continuous |
| **Brushed/universal motors** | Brush arcing is broadband and impulsive — exactly the signature the chip's model likes. Vacuum, drill, grinder, older blowers. | Impulsive |
| **TRIAC / phase-cut dimmers** | Chop the mains 120×/sec with a very fast edge. Includes fan speed controls. | Impulse train |
| **Relays & contactors** | Inrush + contact bounce. Fridge/freezer, dehumidifier, well pump, water heater, doorbell transformer. | Impulsive |
| **Powerline networking** | HomePlug/G.hn adapters are famously broadband-dirty. | Continuous |
| **Solar microinverters / EV charger** | Large SMPS sitting on the house wiring. | Continuous |
| **Induction cooktop** | 20–100 kHz at kilowatt levels — very strong H-field. | Intermittent |
| **Workshop** | Inverter welder (worst single item in a house), 3D printer (steppers + heated-bed PWM), tool battery chargers, bench supplies, fluorescent shop lights. | Mixed |
| **Arc sources** | Gas/furnace igniters, static discharge — and worth ruling out, a loose or arcing connection in the wiring itself. | Impulsive |

**WiFi access points are a special case:** *not* interferers via their radio (2.4/5 GHz is four orders of magnitude away), but **yes** via their wall-wart SMPS and bursty TX current draw pulsing the supply. Suspect the power brick, not the antenna. The same mechanism applies to the node's *own* ESP32 — WiFi TX bursts draw ~300–500 mA, which is one argument for the separate sensor enclosure in §9 and §16.

**In-band oddity:** aviation NDBs transmit at 190–535 kHz and the AM broadcast band starts at 530 kHz. Both are continuous, so they'd raise the noise floor (`INT_NH`) rather than generate disturbers. Logging zero noise interrupts is evidence against them.

**Diagnostic ladder**, ordered by information-per-minute:

1. **Laptop on battery, charger unplugged.** One second, and it isolates the supply most recently introduced.
2. **Run everything from a USB power bank.** Removes every mains-conducted path at once. Rate collapses → coupling is *conducted*, chase supplies. Rate unchanged → *radiated*, chase proximity. **This one test halves the search space** and is the highest-value thing on the list.
3. **Rotate the sensor 90°.** The loop antenna is directional with sharp nulls. A big change with orientation means a single dominant source, and the null bearing points at it. Cheapest localization available.
4. **Breaker-by-breaker.** Kill circuits one at a time, logging ambient `INT_L` for a minute each. Definitive, and it feeds this section's survey directly.
5. **Correlate against cycles.** Bursty rather than steady implies something thermostatically switching.

### 10.2 Breadboard is not a valid test platform

The bench measurements above were taken on a solderless breadboard, and some of that noise is likely the breadboard itself:

- **Long, separated power jumpers form loop antennas** — the one structure a 500 kHz magnetic sensor is *built* to detect.
- Solderless contacts are high-resistance and intermittent, degrading the §7.2 filter's effectiveness at exactly the frequencies that matter.
- The ESP32 sits centimetres from the sensor rather than at the opposite end of an enclosure (§9).

Move to protoboard before drawing conclusions about any *location*. When laying it out: keep the sensor's 3V3/GND pair short and twisted, put the RC filter physically at the sensor, keep the antenna clear of everything, and put the sensor in its own enclosure on a cable so it can sit far from the ESP32 and PSU — that is the rev 2 design (§16).

## 11. Testing

- **SEN-39002 emulator — what it actually validates.** `sen39002-emulator-uno/` runs the shield on a spare **Arduino Uno R3** (it just stacks, no wiring), triggered by its pushbuttons or single keypresses over serial. See [its README](sen39002-emulator-uno/README.md).

  **It validates the interrupt path, not lightning classification.** Measured on this build at 5 cm: 15/15 bursts produced an AS3935 interrupt within 400 ms (latency 34–226 ms) against 0/5 sham controls — so coupling and the IRQ→SPI→ESPHome→HA path are proven end to end. But **every burst was classified as a disturber (`INT_D`), never lightning (`INT_L`).** See §11.1 for what was ruled out. Use it to prove the plumbing works; do not expect `Lightning Distance` to move.

- **Real validation requires a live storm** cross-checked against lightningmaps.org — see below. There is no bench substitute.
- **Quick "is it alive" check:** a piezo BBQ igniter clicked ~10–30 cm away throws broadband RF the AS3935 usually registers — no emulator needed.
- **Real-world validation:** during an actual storm, cross-check the per-strike log against lightningmaps.org (Blitzortung) and the WS90's aggregate count.
- **Disturber spam** is expected indoors; raise `noise_level` / `watchdog_threshold` / `spike_rejection` or set `mask_disturber: true`, and move away from noise sources.

### 11.1 Why the emulator reads as a disturber — what was ruled out

Investigated on 2026-08-09 with a controlled harness (45 s ambient baseline, 400 ms attribution window, sham controls interleaved 1-in-4). Each of these was tested and **none changed the classification**:

| Hypothesis | Test | Result |
|---|---|---|
| **Amplitude / saturation** — too much signal at close range | FAR/MID/CLOSE are 1×/2×/3× the same burst | All three identical. Kills the saturation theory outright: at ⅓ the energy FAR should have passed more often, and didn't. |
| **Shape-match too strict** | `spike_rejection` 2 → 1 | Detection improved (12/15 → 15/15) but lightning stayed at 0. The knob demonstrably worked — *ambient* lightning went from 5/15 to 8/12 — it just doesn't help the emulator. |
| **Staircase too slow** — 644 µs/step vs a real stroke's ~tens of µs | Emulator rebuilt at 400 kHz I²C, 209 µs/step | **Worse**: 11/15 detected, still 0 lightning. |
| **Our driver differs from the vendor's** | Line-by-line audit of all 8 deviations | Burst loop is identical — same array, same 19 steps, same `delayMicroseconds(30)`, same `TWI_FREQ 100000` default. Vendor sketch would emit a bit-identical stimulus. |

`watchdog_threshold` was deliberately *not* lowered: WDTH only gates whether a signal is strong enough to enter validation, and the emulator already clears it. Lowering it cannot reclassify an already-detected event — it would only admit more ambient noise.

**Conclusion:** the AS3935 does not accept this emulator's waveform as lightning, and no host-side setting changes that. The striking asymmetry is that **ambient bench EMI *does* pass the lightning model** (see §11.2) while the purpose-built emulator does not.

### 11.2 The bench environment generates false lightning

Ambient interrupts with the emulator idle, measured over 45 s windows:

| `spike_rejection` | rate | disturber | **lightning** |
|---|---|---|---|
| 2 | 20/min | 10 | **5** |
| 1 | 16/min | 4 | **8** |
| 1 (later run) | 13/min | 7 | **3** |

Every one reported **1.0 km**. These are genuine `INT_L` events — they publish Storm Alert, Distance and Energy straight into Home Assistant. So a few false strikes per minute were arriving in HA the whole time.

Two consequences:
1. **This bench cannot validate anything** while ambient false-lightning outnumbers real stimulus.
2. **It is a strong argument for the §10 site survey.** A location producing several false strikes a minute would be useless. Run the empirical noise survey *before* committing to a mounting spot, and treat the ambient `INT_L` rate — not the disturber rate — as the figure of merit.

Suspects at the bench, untested: the ESP32's own WiFi radio centimetres away on jumpers, unfiltered 3V3 (the §7.2 RC filter and decoupling caps are not present on the breadboard), and long separated power jumpers forming a loop antenna.

### 11.3 Garage attic results: 15 hours, and why none of it is trustworthy

Measured 2026-08-19/20 with `tools/ambient-survey.py --stdin` over the network, breadboard build in the garage attic, config unchanged throughout (`indoor: true`, `spike_rejection: 1`).

| phase | window | disturber/min | noise/min | `INT_L`/min |
|---|---|---|---|---|
| **A** — wall wart, 13 hourly runs | 18:14 → 17:23 | **63–85, mean 72.7** | 102–275, mean 181 | 0.0–1.3, mean 0.6 |
| **B** — USB power bank | 17:33–18:33 | **26.6** | 138.3 | 1.3 |
| **A′** — wall wart restored | 19:02–20:02 | **25.7** | 125.7 | 1.3 |

**Read phase B alone and the conclusion is obvious and wrong.** A 63% fall in disturbers, far outside the band the rate held across thirteen hours, looked like proof that the wall wart was conducting most of the interference. That was written up here as a finding. **The A′ control refuted it:** putting the wall wart back left the rate at 25.7/min. The power source was never the variable.

**What the step change actually coincides with is the node being physically handled** — 17:33 was the first time anyone had touched the build since it booted on 08-18. Two power cycles later the rate is still ~26/min.

Ruled out as explanations for the step:

- **The power source.** That is what A′ tests, and it fails.
- **Time of day.** Phase A includes an 18:14–19:14 evening hour at 72.4/min; B and A′ are the same evening slot on the following day.
- **A household load change.** Per-circuit metering across 17:33 shows only loads coming *on* (oven +202 W, basement lights +172 W) and the AC dropping slightly. Nothing switched off, and the interference fell.

The remaining candidates are all properties of the build itself: a reseated jumper, shifted wire geometry, a marginal contact remade, or a cold power cycle clearing an AS3935 register that had been wrong (the §8.3 `TUN_CAP` hazard is the obvious suspect, and it is only checkable over serial — see §12.1).

**The conclusion that matters does not depend on resolving which.** A measurement platform whose interference floor drops by two thirds because somebody touched it cannot support conclusions about anything else — not the location, not the supply, not the HVAC. The thirteen hours of beautifully stable data in phase A were stable only because nobody went near it. **This is the strongest possible confirmation of §10.2, arrived at the hard way.**

#### The full dataset

All runs 60 min, `--bucket 300`, config unchanged, breadboard in the garage attic. Kept because the *spread* is the point: it is what made the phase B drop look conclusive, and what makes the A′ result unambiguous.

| run | window | disturber/min | noise/min | `INT_L`/min | zero-energy |
|---|---|---|---|---|---|
| baseline | 08-19 18:14–19:14 | 72.4 | 123.9 | 2.3 | — |
| hvacoff | 08-20 05:23–06:23 | 73.9 | 171.5 | 0.4 | 18/24 |
| run-01 | 06:23–07:23 | 69.9 | 197.8 | 0.5 | 27/30 |
| run-02 | 07:23–08:23 | 84.9 | 274.8 | 0.6 | 35/38 |
| run-03 | 08:23–09:23 | 78.8 | 247.3 | 0.5 | 21/29 |
| run-04 | 09:23–10:23 | 77.8 | 102.5 | 0.7 | 35/43 |
| run-05 | 10:23–11:23 | 66.9 | 218.8 | 1.2 | 64/72 |
| run-06 | 11:23–12:23 | 63.4 | 185.1 | 1.0 | 57/60 |
| run-07 | 12:23–13:23 | 70.4 | 122.0 | 1.3 | 75/77 |
| run-08 | 13:23–14:23 | 67.8 | 184.5 | 0.9 | 54/56 |
| run-09 | 14:23–15:23 | 74.0 | 117.8 | 0.0 | 3/3 |
| run-10 | 15:23–16:23 | 72.0 | 172.1 | 0.0 | — |
| run-11 | 16:23–17:23 | 73.5 | 131.3 | 0.0 | — |
| **B — power bank** | **17:33–18:33** | **26.6** | 138.3 | 1.3 | 79/80 |
| **A′ — wall wart back** | **19:02–20:02** | **25.7** | 125.7 | 1.3 | 74/77 |

**On the energy column:** the fraction of `INT_L` events carrying zero energy varies widely (from 3/3 to 21/29) and some non-zero values are large — 780,961 in one run. An early claim here that *all* false lightning was zero-energy, and that an `energy > 0` filter would therefore cost nothing in sensitivity, was **based on six samples and is wrong**. Roughly a quarter of false events carry real energy. The filter idea is much weaker than it first appeared.

#### What still stands

The eliminations came from whole-house per-circuit power metering correlated against the survey buckets, and none of them depend on the phase B/A′ confusion:

| Suspect | Verdict |
|---|---|
| **Garage attic gable fan** — a motor in the same attic, the best suspect on 1/r³ proximity grounds | **Ruled out.** 0 W throughout; it never ran. |
| **Upstairs air handler** | **Ruled out.** 271 W → 5 W between two runs changed the disturber rate not at all. |
| **Any large cycling load** | **Argued against.** Whole-house draw halved (9,921 → 5,112 W) with the disturber rate unchanged (72.4 → 73.9/min). |
| **HVAC generally** | **Not testable in hot weather.** Over 24 h `downfurnace23` never dropped below 103 W and the AC exceeded 500 W in 283 of 289 buckets. |

**AFE dead time couples the two rates.** Each disturber deactivates the AFE for ~1.5 s. When the disturber rate fell to ~26/min the false-lightning rate went *up*, to the top of its observed range, and stayed there across both post-17:33 runs. Less deaf time means more listening time, and some of it gets spent misclassifying EMI as lightning. So §11.2's "rank by `INT_L`, not disturbers" needs a caveat: read `INT_L` *alongside* the disturber rate, because the two move against each other and `INT_L` alone can worsen for a good reason.

**Two methodology lessons, both learned by getting it wrong first:**

1. **Run the A′ control before believing an A/B result.** Phase B was a clean, large, plausible effect that survived a time-of-day check and a household-load check, and it was still wrong. One extra unattended hour was the difference between a documented finding and a documented mistake.
2. **Do not infer a subsystem's state from a proxy that measures one part of it.** HVAC state was first inferred from the upstairs supply-duct thermometer, which tracks only the upstairs air handler; the window it labelled "HVAC off" had the downstairs handler at ~288 W and the compressors at ~1,660 W. Whole-house power metering settled it directly.

### 11.4 Reproducing these measurements

Everything in §11.3 was gathered over WiFi with the node in place. Nothing needs physical access — which matters, because §11.3 is precisely about how touching the build changes the result.

**Set up a matching ESPHome, in a throwaway venv.** The node runs 2026.6.5; match it. Do not rely on a `pyenv` shim, which may not resolve.

```bash
python3 -m venv /tmp/esphome-venv
/tmp/esphome-venv/bin/pip install 'esphome==2026.6.5'
```

**Give it secrets without dirtying the repo.** `lightning-detector.yaml` needs a `secrets.yaml` beside it. Copy the config to a scratch directory and symlink the real secrets in:

```bash
mkdir -p /tmp/esphome-run && cp lightning-detector.yaml /tmp/esphome-run/
ln -s /path/to/your/esphome/secrets.yaml /tmp/esphome-run/secrets.yaml
```

⚠️ **Never run `esphome config`** — it renders the configuration with secrets *resolved*, printing the WiFi password and API encryption key to stdout. `esphome logs` does not.

**Run a survey.** The node must be at `logger: level: VERY_VERBOSE`:

```bash
cd /tmp/esphome-run
/tmp/esphome-venv/bin/esphome logs lightning-detector.yaml \
  | /path/to/tools/ambient-survey.py --stdin --minutes 60 --bucket 300
```

**One wrinkle worth knowing:** `esphome logs` does **not** die when the survey exits, so a naive pipe never terminates. Drive it through a FIFO and reap the writer explicitly:

```bash
mkfifo /tmp/s.fifo
esphome logs lightning-detector.yaml > /tmp/s.fifo & EPID=$!
ambient-survey.py --stdin --minutes 60 --bucket 300 < /tmp/s.fifo
kill $EPID; rm -f /tmp/s.fifo
```

**Correlating against the house.** The eliminations in §11.3 came from Home Assistant metrics in Prometheus, reachable through Grafana's datasource proxy — note the **uid** form of the path works where the numeric-id form 404s:

```
/api/datasources/proxy/uid/<datasource-uid>/api/v1/query_range
```

`hass_sensor_power_w` carries ~80 per-circuit power series and is the tool that ruled out the gable fan and the air handlers. **Caveat that bit once:** HA only records state *changes*, so an entity republishing an identical value leaves no trace. Event *rates* cannot be reconstructed from Prometheus — which is why the surveys have to be run live rather than mined from history afterwards.

## 12. Bring-up order

**Rev 2 has no mains, so the old safety rule does not apply.** It read: *never have USB and the IRM-02-5 powered at the same time*, because the `5V`/`VIN` pin ties straight to the USB rail on most dev boards and a live mains supply back-feeds into the laptop's USB port. **That rule returns in full if you ever build the §7.3 mains variant.** With a USB brick there is only ever one supply, and swapping between the brick and a laptop is safe.

1. **Bench-assemble both boxes** and connect them with the shortest patch cable.
2. **Measure 5 V at the ESP32 `5V` pin** with the intended brick and cable, **during WiFi activity** — not at idle. Above ~4.7 V under load, or fix the cable before going further (§7.4).
3. **Measure 3.3 V at the sensor VDD pin**, at the far end of the cable, after the LDO.
4. **Verify the tuning capacitance over serial** — see §12.1. This is the one check that cannot be done over WiFi, and bench bring-up on USB is the natural moment for it.
5. Confirm the sensor initialises and responds to the SEN-39002 emulator (expect disturbers, not lightning — §11.1).
6. **Run the platform-validity test** before trusting any measurement from the rebuild: survey, handle the build, survey again. §15 Phase 2. If the rates move, stop and fix the mechanics.
7. Only then mount it and start the §16 distance sweep.

### 12.1 Verifying the tuning capacitance (serial only)

The `Setting tune cap to N pF` line is emitted from the component's `setup()`, which runs **before WiFi and the API come up**. The ESPHome log stream — dashboard "Logs" button or `esphome logs` over the network — attaches only after the device has finished booting, and ESPHome does not replay boot-time logs to a late-connecting client. So this line is *never* visible over WiFi, no matter the log level. Rebooting with the log window open doesn't help either: the API drops and reattaches after `setup()` has already finished.

With `logger: level: VERY_VERBOSE` set, connect over USB:

```
esphome logs lightning-detector.yaml --device /dev/ttyUSB0
```

(In the dashboard, the Logs view lets you pick the serial port instead of the network.)

Look for `[as3935]` **`Setting tune cap to 72 pF`** — the component logs `capacitance * 8`, so `9` → `72`, matching the board label. **If it prints any other value, that's the genuine component bug** described in §8, and the PWF Arduino-sketch fallback applies.

Note the contrast for later: the *runtime* messages (`Noise was detected`, `Disturber was detected`, `Lightning has been detected!`) come from `loop()` and stream over WiFi normally. Only the one-shot `setup()` output needs serial — which is why the noise survey in §10 can be run headless, but this check can't.

## 13. Key learnings and design decisions

- **The WS90 already contains an AS3935** — the problem was data exposure, not the sensor.
- **RC beats ferrite here.** Because the sensor draws < 1 mA and cares about the 500 kHz band (where ferrite beads are nearly transparent), a series **100 Ω + bulk cap RC** filter is more effective than a bead. The bead only complements it at VHF.
- **MOV voltage rating:** use **150 VAC** for a 120 V US line. (275 VAC is a 230 V-line value and would clamp too high to protect a 120 V circuit — an earlier error, corrected.)
- **105 °C electrolytics** are mandatory for the attic thermal environment.
- **Non-metallic enclosure**, **vented (not sealed)** for attic heat.
- **`SI` = GND** selects SPI; **power the sensor at 3.3 V** to match ESP32 logic.
- **ESPHome `capacitance` is in 8 pF steps, not pF** — divide the board label by 8 (72 pF → 9). Valid range is 0–15; pF values fail validation outright.
- **`spi_mode: MODE1` is mandatory** and its absence is silent — the component defaults to Mode 0, every SPI byte comes back shifted one bit, and the interrupt register reads an impossible `2` that matches none of the component's branches. Nothing is logged and nothing is published. See §8.1.
- **Trust the sensor over the component.** Two of this build's dead ends (Mode 0, and the emulator's "missing" second DAC) were defects or wrong assumptions in *software/docs*, not hardware faults. Read the driver source before suspecting the wiring.
- **The emulator proves the plumbing, not the physics.** It reliably fires the IRQ (15/15 vs 0/5 sham) but the AS3935 always calls it a disturber, and nothing host-side changes that — see §11.1. Budget for a live-storm validation; there is no bench substitute.
- **Measure ambient `INT_L`, not disturbers, when choosing a site.** The bench produced 3–8 *lightning* classifications per minute from EMI alone, all at 1.0 km, all published to HA. Disturber rate is the obvious metric and the wrong one — false `INT_L` is what actually corrupts the data.
- **Use sham controls when correlating.** At ~16 ambient events/min a 2.5 s attribution window is ~49% likely to catch a coincidence, which is enough to invent a result that isn't there. A 400 ms window plus interleaved do-nothing trials made the difference between "the emulator sometimes works" and "it never does."
- **The per-strike path to Home Assistant has never worked, and nothing pointed at it.** The Storm Alert pulse is emitted correctly by the device and recorded by HA zero times in 34.7 hours (§8.4). Nothing failed loudly: no error, no dropped connection, and every other entity on the same node updating normally. **The project's core deliverable was broken for its entire life and only turned up because a metric was checked directly.** Verify the output path end to end, early, on anything event-driven.
- **Touching the breadboard changed its interference floor by two thirds, permanently.** The disturber rate held 63–85/min for thirteen hours, then dropped to ~26/min the moment the build was physically handled, and stayed there across two power cycles (§11.3). Nothing about the location, the supply or the house explains it. A platform this sensitive to being touched cannot measure anything else — which is §10.2, demonstrated rather than argued.
- **Run the A′ control before believing an A/B result.** The power-bank hour looked like proof that the wall wart conducted 63% of the disturbers: a large effect, well outside thirteen hours of spread, and it survived both a time-of-day check and a per-circuit household-load check. Restoring the wall wart left the rate unchanged, so the supply was never the variable. One extra unattended hour separated a finding from a mistake, and the mistake had already been written up.
- **Cutting disturbers can make false lightning look *worse*.** A disturber deactivates the AFE for ~1.5 s, so a quieter disturber rate hands back listening time, some of which gets spent misclassifying EMI as lightning. Read `INT_L` alongside the disturber rate, never alone — §11.2's figure of merit needs that caveat.
- **Use power metering, not a proxy, to say what is running.** Inferring HVAC state from the upstairs duct thermometer produced a confident and wrong conclusion; the downstairs air handler had been running the whole time. Per-circuit data also cleanly exonerated the attic gable fan, which proximity alone made the best suspect (§11.3).
- **Measure long enough to know the spread before believing a change.** The disturber rate held 63–85/min across twelve hourly runs spanning a full day. Without that band, 26.6/min would have been a single suggestive number; with it, the drop is unambiguous.
- **Corrections logged:** the Fair-Rite 5943003801 ferrite was mis-specced (a 2.4″ balun toroid) — do not use; the Murata 0603 bead or a small clip-on replaces it. The `capacitance`-in-pF instruction was also wrong (see above), and `calibration: false` was set unnecessarily in the YAML.

## 14. Deliverables

- `lightning-detector.yaml` — complete ESPHome configuration.
- `as3935-node-wiring.pdf` — printable point-to-point wiring set for the **rev 2** design (§16): system overview, main enclosure, sensor enclosure, wire list and bring-up checklist.
- `make-wiring-diagram.py` — regenerates that PDF (`python3 make-wiring-diagram.py`, needs `reportlab`). The rev 1 drawing had no generator in the repo and could not be revised; this one can.
- `sen39002-emulator-uno/` — PlatformIO project running the SEN-39002 emulator shield on a spare Arduino Uno R3, with its own [README](sen39002-emulator-uno/README.md).
- `tools/` — measurement instruments, with their own [README](tools/README.md).
  - `ambient-survey.py` — the site-survey instrument behind §11.3. Reads a serial port *or* a piped `esphome logs` stream (`--stdin`), so it works on a node already mounted. Counts `INT_NH`/`INT_D`/`INT_L`, interprets the distance *codes* (§8.2), pairs each `INT_L` with its energy, and buckets a timeline. Health-gated: a source producing nothing aborts, and a run parsing zero lines reports `MEANINGLESS` rather than a quiet site.
  - `emulator-trial.py` — the sham-controlled harness behind §11.1.
- `README.md` — this document.

## 15. Next steps, in dependency order

**Everything below the first item is blocked by it.** This is not a priority ranking, it is a dependency graph.

### Phase 1 — Rebuild on protoboard (blocking)

No measurement taken on the breadboard can be trusted (§10.2, §11.3), so this gates every remaining question. Requirements are in §16.

While the node is on USB for bench bring-up, take the one measurement that cannot be made over WiFi: **verify the tuning capacitance over serial** (§12.1). Note that whether a bad `TUN_CAP` contributed to the pre-rebuild numbers is **no longer answerable** — the register has been cold-cycled since, and whatever it held for those 34 hours is gone.

### Phase 2 — Prove the new platform is a valid instrument

Before trusting any number from it, run the test the old platform failed:

1. Survey for an hour.
2. Deliberately handle the build — press on it, flex the enclosure, reseat what is reseatable.
3. Survey again.

**If the rates hold, the platform is an instrument.** If they move, it is still furniture and the rebuild did not fix the problem. This check exists because the breadboard's floor dropped by two thirds on contact and nobody noticed for thirteen hours.

### Phase 3 — Redo the measurements that are currently meaningless

- **Re-survey the garage attic.** The location has never had a fair verdict, in either direction. §11.3's 0.6/min average is encouraging but uninterpretable.
- **Hunt the noise floor (`INT_NH`).** The least understood number in the project: ~zero on the bench, 100–275/min in the attic, unmoved by removing mains coupling and unrelated to the HVAC. Candidates: in-band AM/NDB carriers received better near the roofline, and the ESP32's own WiFi bursts. It is *continuous*, so it deafens the AFE in a way disturbers do not.
- **Rotation test.** Now finally meaningful: §10.1's null-bearing logic assumes a distant, stationary source, which was violated while sensor and ESP32 were bolted to the same breadboard. With the sensor in its own enclosure on a cable it can turn independently.
- **Tune for deployment.** `indoor: false` for attic AFE gain, and back `spike_rejection` off its bench floor of 1. Read `INT_L` *alongside* the disturber rate when judging, not instead of it (§11.3).

### Phase 4 — Make it actually deliver

- **Fix the per-strike path (§8.4).** On-device `on_press` incrementing a counter sensor. Pure software, blocked on nothing but sequencing — deferred deliberately to keep the measurement work clean.
- **Catch a real storm.** The only true validation (§11.1). Watch for `Lightning Distance` in the **5–40 km** range; `1` is the overhead bin where local EMI lands and **`63` is not a distance** but the out-of-range code (§8.2). Cross-check timestamps against lightningmaps.org and the WS90.
- Home Assistant automations and a dashboard card, once §8.4 makes per-strike events real.
- Roof-mount the WS90 (still at ground level).
- Optional, long-term: host a Blitzortung station for geolocated network data.

## 16. Hardware revision 2 — the spec

Decisions settled 2026-08-22. Wiring detail is in §7; this is the rationale and the build checklist.

### The architecture, and the one idea behind it

**Two enclosures, connected by a swappable Cat5 patch cable.**

The single most powerful lever available is distance: near-field magnetic coupling falls as **1/r³**, so 5 cm → 50 cm is roughly a 1000× reduction. Nothing else on the table comes close.

But **§11.3 never identified the interference source**, so committing to a fixed separation would be guessing. The patch cable turns that guess into a measurement: build once, then survey at 0.3 / 1 / 2 / 3 m and read the curve. If the rate is flat across all four, the ESP32 and supply were never the problem and they are eliminated properly for the first time.

The ESP32 goes in the **main** box, never the sensor box — its 300–500 mA WiFi bursts are precisely what the distance is buying separation from.

### Build checklist

| Requirement | Why | Ref |
|---|---|---|
| **Soldered joints throughout** | Solderless contacts are high-resistance and intermittent and degrade the filter where it matters. Prime suspect for the §11.3 step change. | §10.2 |
| **Sensor in its own small enclosure** | 1/r³. Also makes separation measurable and keeps the sensor box SELV-only. | §9 |
| **Cat5 patch cable on RJ45, T568B** | Certified pre-made cables so length is the only variable between sweep points. | §7.1 |
| **5 V down the cable, LDO at the sensor** | Regenerates 3.3 V centimetres from the pins; linear, so no switching node near the antenna. | §7.2 |
| **§7.2 passives in addition to the LDO** | LDO rejection is gone by 500 kHz. The two are complementary, neither is sufficient. | §7.2 |
| **`data_rate: 200kHz`** in the YAML | Default is 1 MHz. Makes cable reflections a non-issue; traffic is trivial. | §7.1 |
| **2–3 A USB brick, ≤1 m 20–24 AWG cable** | The IRM-02-5 browned out; a thin cable reproduces it. | §5, §7.4 |
| **Bulk cap physically at the ESP32 `5V` pin** | Burst reservoir the cable resistance cannot supply fast enough. | §7.2 |
| **Main box vented, 105 °C electrolytics** | ~52 °C attic; sealed boxes bake and 85 °C parts die in a couple of summers. | §9 |
| **Both boxes non-metallic, mechanically rigid** | Antenna must not be shielded; and §15 Phase 2 is a pass/fail test on rigidity. | §9 |

### Decisions taken, and what was traded away

- **USB brick over mains.** The two-box layout moved the supply away from the antenna, which removed the *EMI* argument for an industrial part and left only reliability. §9's thermal argument against cheap bricks still stands and is knowingly accepted: the failure mode is loud (node drops off WiFi, visible immediately in HA), attic access is a walk-out door, and the part costs a few dollars. **The brick is a consumable.** IRM-05-5 and IRM-10-5 are on hand if this proves wrong.
- **RJ45 despite the PoE hazard.** The jack carries 5 V and SPI; a live PoE port would put 48 V on those lines and destroy both ends. Accepted knowingly, because certified pre-made patch cables are what make the distance sweep a clean experiment — hand-terminated cables would introduce a variable per length. Label both ends.
- **Sensor enclosure sealed, main enclosure vented.** Different reasoning for each: the sensor box has no meaningful dissipation, the main box does.
- **Deferred:** whether the mounting *spot* should change. Out of scope for rev 2 — the enclosure is the same wherever it goes, and the location cannot be judged until the platform is trustworthy (§15 Phase 3).
