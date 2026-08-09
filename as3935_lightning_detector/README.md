# AS3935 Lightning Detector Node — Project Documentation

*Per-strike lightning detection for Home Assistant / ESPHome*
*Compiled: July 2026*

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

```
120 VAC ──► fuse (line) ──► MOV (L–N) ──► Mean Well IRM-02-5 (5 V)
                                              │
                                        5 V rail + bulk cap
                                              │
                                     ESP32 dev board (WiFi)
                                        │ 3.3 V LDO out
                                        │
                              RC filter (100 Ω + caps)
                                        │
                              SEN-39003 (AS3935) ── SPI + IRQ ── ESP32 GPIOs
```

- **Detection:** Playing With Fusion SEN-39003 (AS3935), SPI, interrupt-driven.
- **Compute/network:** ESP32 dev board on WiFi (PoE was not feasible at the site).
- **Power:** Mean Well IRM-02-5 mains module, with local filtering and mains protection.
- **Firmware:** ESPHome native `as3935_spi` component → per-strike events into Home Assistant.

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
- Arduino-shield lightning emulator; generates RF mimicking near/medium/far strikes at ~5–15 cm.
- **Needs an Arduino Uno (or compatible) to drive it** (runs PWF's `Lightning_Emulator.ino`).

### Power supply — Mean Well IRM-02-5
- Encapsulated PCB-mount AC-DC, 5 V / 400 mA / 2 W, rated **−30 to +85 °C**.
- The +85 °C rating suits the hot attic. **400 mA is tight for an ESP32 on WiFi** (TX bursts approach ~500 mA), so the 5 V bulk capacitor is essential as a transient reservoir, not just a filter.

## 6. Bill of materials (final, DigiKey part numbers)

| Function | Part | Notes |
|---|---|---|
| Sensor | Playing With Fusion **SEN-39003** | Pre-calibrated AS3935 breakout |
| Tester | Playing With Fusion **SEN-39002** | Emulator shield (needs an Arduino) |
| MCU | ESP32 dev board | WiFi |
| PSU | Mean Well **IRM-02-5** | 5 V / 400 mA, −30/+85 °C |
| 5 V bulk cap | Nichicon **UPW** series, 470–1000 µF, 16–25 V, 105 °C | e.g. UPW1C471MPD. (Panasonic EEU-FR1C471 was out of stock.) |
| Sensor-rail bulk cap | Panasonic **EEU-FR1H470** | 47 µF, 50 V, 105 °C |
| Ceramic 100 nF | Kemet **C320C104K5R5TA** | X7R, closest to sensor |
| Ceramic 1 µF | Kemet **C330C105K5R5TA** | X7R, mid-band |
| Series resistor | 100 Ω, ¼ W metal film | RC filter element |
| Ferrite bead | Murata **BLM18AG601SZ1D** | 0603, 600 Ω @ 100 MHz; optional/complementary |
| Fuse | Littelfuse **0215.250MXP** | 250 mA, 250 VAC, 5×20 mm, ceramic, time-lag |
| Fuse holder | Littelfuse **345621** | Panel mount, 12.7 mm hole |
| MOV | Littelfuse **V150LA10AP** | **150 VAC** (correct for 120 V line), 14 mm |

**Do NOT use:** Fair-Rite **5943003801** — this was mis-specced earlier; it is a 2.4″ FT-240 balun/power toroid, absurdly oversized for a sub-milliamp rail. The Murata 0603 bead replaces it. If a no-solder option is still wanted, a **small-bore (3–5 mm) clip-on ferrite** with **2–3 turns** of the 3.3 V wire looped through it works fine — bore size and turns matter far more than material (generic NiZn is fine here).

## 7. Wiring

### 7.1 SPI + interrupt (SEN-39003 → ESP32)

| SEN-39003 | ESP32 | Purpose |
|---|---|---|
| VDD | 3V3 | **Power at 3.3 V, not 5 V**, to match logic levels |
| GND | GND | |
| SCLK | GPIO18 | SPI clock |
| MISO | GPIO19 | SPI data in |
| MOSI | GPIO23 | SPI data out |
| CS | GPIO5 | Chip select |
| IRQ | GPIO4 | Strike interrupt |
| SI | **GND** | Selects SPI (GND = SPI, VDD = I²C) |

**Gotcha:** `SI` must be tied to GND. Left floating, the sensor won't respond.

### 7.2 Power and sensor-rail filter

Chain: IRM-02-5 (5 V) → ESP32 `5V/VIN` → onboard 3.3 V LDO → filter → sensor VDD.

- **5 V bulk cap (C1)** mounts physically at the ESP32 `5V`/`GND` pins — the WiFi-transient reservoir.
- **Filter topology:** `3.3 V → 100 Ω (+ optional bead) → node → [47 µF ∥ 1 µF ∥ 100 nF] → sensor VDD`
- The 100 nF sits closest to the sensor pins; the 47 µF furthest.
- ~50 mV drop across the 100 Ω at the sensor's sub-1 mA draw; sensor sees ~3.25 V (well above its 2.4 V floor).

### 7.3 AC mains side

`cord → fuse (Line only) → MOV across L–N (after the fuse) → IRM-02-5`

- Fuse in the **Line** conductor only, ahead of everything.
- **MOV across Line–Neutral, downstream of the fuse** (electrically the T2 / AC-L node), so the fuse also protects against the MOV's end-of-life short. Land the MOV lead at a junction on the fused-line run — *not* on the upstream side of the fuse, which would leave the MOV unfused.
- **Ground:** capped off, not bonded — the IRM-02-5 is a 2-wire isolated supply and the enclosure is plastic, so `−Vo` is the (floating) DC common, not earth.
- Sleeve every AC terminal; keep ≥ 6 mm from any DC wiring.

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

**Known rough edge:** the ESPHome AS3935 component has a reputation for writing the capacitance register incorrectly. A large share of those reports are probably just the pF-vs-8 pF-steps confusion above rather than a component defect — but verify anyway. Set `logger: level: VERY_VERBOSE` and confirm the log line reads **`Setting tune cap to 72 pF`** (the component logs `capacitance * 8`, so 9 → 72). If it prints anything other than your label value, that's a genuine bug — fall back to PWF's Arduino SPI sketch bridged to MQTT.

⚠️ **This check requires a serial connection — it is not visible over WiFi at any log level.** The line is printed from `setup()`, before the API is up. See **§12.1** for the procedure and the reason.

## 9. Enclosure

- **Non-metallic** (plastic project box on hand) — the AS3935's 500 kHz loop antenna must not be shielded/detuned. Confirm no metal faceplate or conductive coating.
- **Attic use inverts the usual sealing logic:** it's sheltered from rain, so do **not** seal airtight — a sealed box bakes the electronics. **Vent it** (a few screened holes for convection) so internal temp ≈ ambient.
- Use a box long enough to put the **sensor at one end** (ideally on a short pigtail, with its three decoupling caps right at the sensor) and the **ESP32 + PSU at the other**, for physical separation from noise.
- Sensor PCB on **nylon standoffs**; keep its antenna clear of box screws and the ESP32's antenna end.
- Mount the fuse holder through the box wall for external fuse access.

## 10. Mounting location

**Chosen: the garage / breakfast / laundry attic** (over the single-story wing).

Site-selection priority for the AS3935: low *continuous* EMI, distance from large metal masses, install/tuning access, then thermal. Height is irrelevant (500 kHz is not line-of-sight).

- **Garage-side attic (chosen):** easy access, easy power/network, and its noise sources (washer/dryer, garage-door opener, microwave) are *intermittent* — friendlier to the AS3935's disturber rejection than a continuous source. Check for a continuous garage fridge/freezer compressor or EV charger near the spot.
- **Main 2-story attic (rejected):** the furnace/HVAC (especially a variable-speed ECM blower) is a *continuous* broadband EMI source, plus metal ductwork. The DTV antenna and 900 MHz Ecowitt gateway antenna are **not** RF interferers (spectrally far from 500 kHz) — only metal masses to clear by 2–3 ft — but the HVAC plus harder access made this the worse choice.
- **Master-bedroom wing attic:** inaccessible → out.

**Placement within the attic:** low near the ceiling joists (cooler; away from any foil radiant barrier), in the corner farthest from the laundry appliances and garage-door opener. The build can be relocated to try several spots.

**Thermal:** both accessible attics peak ~125 °F (52 °C); 2-year data confirms that as the high. The AS3935 and ESP32 are rated to 85 °C — fine. Electrolytics are **105 °C-rated** (every ~10 °C over rating roughly halves electrolytic life; at 52 °C ambient plus self-heating, 105 °C parts last years where 85 °C parts fail in a couple of summers).

**Empirical site survey:** run the node in each candidate spot for a day (spanning HVAC/laundry cycles) and log the AS3935 noise-floor / disturber interrupt rate to rank spots from data rather than theory.

## 11. Testing

- **SEN-39002 emulator:** stack on an Arduino Uno, flash `Lightning_Emulator.ino`, hold ~5–15 cm from the sensor, trigger near/far strikes, and confirm distance/energy/Storm-Alert events appear in the ESPHome log and HA. Keep phones/laptops ~1 ft away.
- **Quick "is it alive" check:** a piezo BBQ igniter clicked ~10–30 cm away throws broadband RF the AS3935 usually registers — no Arduino needed.
- **Real-world validation:** during an actual storm, cross-check the per-strike log against lightningmaps.org (Blitzortung) and the WS90's aggregate count.
- **Disturber spam** is expected indoors; raise `noise_level` / `watchdog_threshold` / `spike_rejection` or set `mask_disturber: true`, and move away from noise sources.

## 12. Bring-up order (and the one safety rule)

**Never have USB and the IRM-02-5 powered at the same time.** On most ESP32 dev boards the `5V`/`VIN` pin ties straight to the USB rail, so a live mains supply back-feeds into the laptop's USB port. Unplug mains before plugging in USB.

1. Bench-test the DC side on **USB only** (mains disconnected).
2. **Verify the tuning capacitance — over serial, and only in this step.** See §12.1 below; this is the one check that *cannot* be done over WiFi, and this USB-only phase is the only time it's safe to do.
3. Confirm the sensor initializes and responds to the SEN-39002 emulator.
4. **Unplug USB**, then energize the AC side.
5. Measure **5.0 V** at the ESP32 `5V` pin before connecting it.
6. Re-verify the sensor on mains power. Disturbers that appear *only* on mains mean the filter needs more work — not a different mounting location.

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
- **Corrections logged:** the Fair-Rite 5943003801 ferrite was mis-specced (a 2.4″ balun toroid) — do not use; the Murata 0603 bead or a small clip-on replaces it. The `capacitance`-in-pF instruction was also wrong (see above), and `calibration: false` was set unnecessarily in the YAML.

## 14. Deliverables

- `lightning-detector.yaml` — complete ESPHome configuration.
- `as3935-node-wiring.pdf` — 4-page printable wiring set (AC mains, DC power/filter, SPI/IRQ, wire list + bring-up checklist), drawn as point-to-point connections.
- `README.md` — this document.

## 15. Future work / on the horizon

- Roof-mount the WS90 (still at ground level).
- Build the minimal ESPHome **noise-survey** config for the empirical attic site comparison.
- Home Assistant **automations and a dashboard card** for the per-strike events.
- Optional: revisit hosting a Blitzortung station as a longer-term project for geolocated network data.
