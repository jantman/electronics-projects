# AS3935 Lightning Detector Node — Project Documentation

*Per-strike lightning detection for Home Assistant / ESPHome*
*Compiled July 2026; last updated 2026-09-13*

---

## Project status — read this first

**Working:** the sensor detects, over SPI, interrupt-driven, **on the rev 2 soldered build**. The measurement tooling in `tools/` is trustworthy and reproducible over serial and, through the ESPHome dashboard (`tools/ws-log-bridge.py`), over WiFi (§11.4).

**Hardware revision 2 is built and passed bench bring-up on 2026-09-13 (§12.2):** both boards soldered per §7.5, joined by a swappable patch cable, USB power. SPI, every register, the tuning capacitance, oscillator calibration and the emulator interrupt path all check out, and the bench read **zero ambient interrupts of any kind in ten minutes** — where the breadboard read 13–20/min, including 3–8 false lightning/min (§11.2). The mains supply was built and abandoned — see §5.

**§15 Phase 2 passed on 2026-09-13 (§11.7) — rev 2 is a valid instrument.** The breadboard was not (§10.2, §11.3): its interference floor dropped by two thirds the moment it was physically handled, and every number measured on it describes the breadboard at least as much as the attic. Rev 2 was moved to a quiet corner of the basement woodshop and read **zero interrupts of any kind** for an hour hands-off, nothing while it was pressed, flexed and had its cable reseated, and zero again for an hour afterwards. An emulator check between the two hours proved the sensor was alive, so the zeros are real. A first attempt on the electronics bench was inconclusive (§11.6); its disturbers most likely came from a window AC compressor ~1.2 m away. **§12 bring-up is complete** — the intended USB brick puts 4.823 V at the sensor board with WiFi active. **Next: fit the enclosures and the 22 AWG USB cable, check liveness and 5 V once, then install in the attic and survey for several days (§15).**

**Separately, and deliberately deferred: the per-strike path into Home Assistant does not work (§8.4).** Zero Storm Alert state changes across 34.7 hours and thousands of detections. It is the project's core deliverable and the diagnosis is complete, but it is **a distinct body of work from the hardware**, is not blocked by it and does not block it. It will be picked up once the hardware is finalised. Do not interleave it with the measurement work.

**Never validated:** the detector has never seen a real strike. Every `INT_L` recorded so far is believed false. The SEN-39002 emulator proves the interrupt path but is always classified a disturber (§11.1), so **there is no bench substitute for a live storm.**

**Current configuration is bench-tuned, not deployed** — `indoor: true` and `spike_rejection: 1` are leftovers from emulator work (§11.1). Every rate quoted in §11.3 is a worst case for that configuration, not for a tuned one. The two `reboot_timeout` values are bench settings too, marked `BENCH SETTING` in the YAML — notably `api: reboot_timeout: 0s`, so a node with no Home Assistant client attached does not reboot every 15 minutes in the middle of a survey. Restore both before deployment.

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
| MCU | **ESP32-DevKitC V4** (ESP32-WROOM-32D), 38-pin | WiFi. 19 pins per row, rows **1.0″ (10 holes)** apart — see §7.5. |
| PSU | **2–3 A USB brick** | See §5. The IRM-02-5 was built and browned out. |
| USB cable | **≤1 m, 20–24 AWG power conductors** | Not incidental — see §7.4. Thin/long cables reproduce the brownout. |
| Sensor-rail LDO | Microchip **MCP1700-3302E/TO** | 3.3 V, TO-92. **`E` = −40/+125 °C grade**, required for the attic. |
| Interconnect | **Cat5/Cat5e patch cables**, 0.3 / 1 / 2 / 3 m | Pre-made so length is the only variable (§16) |
| Connectors | 2 × **shielded RJ45 jack on a 9-way 0.1″ breakout** | Pins `1 2 3 4 5 6 7 8 SH` silkscreened. Wired T568B per §7.1. On both boards the header solders straight into the perf |
| Enclosure ×2 | Non-metallic | Main (vented) + sensor (small, sealed) — §9 |
| 5 V bulk cap | Nichicon **UPW** series, 470–1000 µF, 16–25 V, 105 °C | e.g. UPW1C471MPD. (Panasonic EEU-FR1C471 was out of stock.) |
| Sensor-rail bulk cap | Panasonic **EEU-FR1H470** | 47 µF, 50 V, 105 °C |
| Ceramic 100 nF | Kemet **C320C104K5R5TA** | X7R, closest to sensor |
| Ceramic 1 µF | Kemet **C330C105K5R5TA** | X7R, mid-band |
| R1, sensor rail | 100 Ω, ¼ W metal film | RC filter element (§7.2) |
| R2/R3/R4, series terminators | **68 Ω, ¼ W metal film** | 3 off, at the ESP32 end of SCLK/MOSI/CS — §7.1 |
| Ferrite bead | Murata **BLM18AG601SZ1D** | 0603, 600 Ω @ 100 MHz; optional/complementary |
| Bus wire | **Bare solid tinned copper, 22 AWG** | ~1 m. For the sensor board's four buses — §7.6 |
| Hookup wire | **Solid core, 24 AWG**, 6 colours, PVC or PTFE | ~2 m. Board links — §7.6 |
| Female header | 0.1″ 1×40 breakaway | 2 off, cut to 1×19 for the ESP32 |
| Male header | 0.1″ 1×40 breakaway | 8 pins for the SEN-39003 if it ships without one |


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
| 1 | white/orange | **5 V** | `5V` (via C1) | to LDO input (§7.2) |
| 2 | orange | GND | `GND` beside GPIO19 | PG |
| 3 | white/green | **SCLK** | **GPIO19** | SCLK |
| 6 | green | GND | `GND` beside GPIO19 | PG |
| 4 | blue | MOSI | **GPIO18** | MOSI |
| 5 | white/blue | MISO | **GPIO5** | MISO |
| 7 | white/brown | CS | **GPIO16** | CS |
| 8 | brown | IRQ | GPIO4 | IRQ |
| SH | *(none — jack shell)* | shield | `GND` beside GPIO19 | **not connected** |

**The ESP32 pins are not the default VSPI set (18/19/23), on purpose.** On the main board each series
resistor is soldered pin to pin between an ESP32 pin and the jack pin directly below it (§7.5), and
neither pin order can move — the jack's is fixed by the cable, the dev board's by the dev board. With
the original assignment no position lines up all three resistor lines: CS and SCLK were neighbours on
the ESP32 but are four pins apart on the jack, with MOSI between them. So the GPIOs were chosen to fit
the jack, and `lightning-detector.yaml` matches. The ESP32 routes SPI to any pin through its GPIO
matrix, which at these speeds costs nothing. Two boot-time side effects, both harmless: GPIO5 (now
MISO) is a strapping pin, but only for SDIO-slave timing, which this never uses; and CS moved off
GPIO5, which has a weak pull-up at reset, onto GPIO16, which floats until ESPHome drives it — so the
AS3935 may see noise on CS during boot, and ESPHome writes the configured registers in `setup()`,
after boot, anyway. A 10 kΩ pull-up from CS to 3V3 would remove even that, if it ever matters.

- **Plain UTP is what this is designed around.** A shield bonded at *both* ends makes a ground loop, and it would do nothing against magnetic coupling anyway — hence the single-point bond above.
- **`data_rate: 200kHz` is set** in the YAML. `as3935_spi` inherits the standard SPI device schema, so this is settable; it **defaults to 1 MHz**. The traffic is a handful of single-byte register reads per event, so 200 kHz is far more than enough, and it makes reflections a non-issue *for sampling* — you read the line microseconds after an edge that settles in tens of nanoseconds. It does **not** remove the ringing itself; see below.
- **IRQ over a long cable is safe.** The component *level-reads* the pin in `loop()` rather than edge-triggering, so added cable capacitance cannot cost you an interrupt.
- ⚠️ **This is not Ethernet.** The jack carries 5 V and SPI. Plugging it into a live PoE switch port puts 48 V onto those lines and destroys both the ESP32 and the sensor. Accepted knowingly in exchange for certified pre-made cables — which the §16 distance sweep needs, since hand-terminated cables would add a variable per length. Label both ends.

#### The jack breakout, and how to not wire it backwards

The RJ45 parts are **shielded jacks on a 9-way 0.1″ breakout**: pins 1–8 plus **SH**, the metal
shell. This is the connector most likely to be wired mirrored, so:

- **The order you see depends on which way up the header is — not on which side you look from.**
  The jack and the silkscreen are on the *same* face. With the header at the top (latch slot at the
  bottom of the opening) the pins read `1 2 3 4 5 6 7 8 SH` left to right, as printed. Turn the part
  half a turn so the header is at the bottom and the same pins read `SH 8 7 6 5 4 3 2 1`. An earlier
  revision of this section explained the difference as front versus back of the PCB; that was wrong,
  though the two orders it gave were right. **Wire to the printed number, never to a position.**
- The jack is **top-entry**: the cable goes in *perpendicular* to the breakout PCB.
  - **On both boards** the right-angle header solders straight into the perf, so the breakout stands
    on edge, header down, with the jack facing off the board edge and out through the enclosure wall.
    That is the header-down view: SH is at the USB end of the main board's J1 and at the top of the
    sensor board's J2 (§7.5). The nine header joints are the electrical connection, not the
    mechanical one — the wall, or a bracket on the breakout's own mounting holes, must take the force
    of plugging a cable in.
  - Standing, the breakout blocks the **three rows or columns behind its pins** from the top. Anything
    that has to go in there from the top goes in before the breakout does.
  - Mounting holes are 3.00 mm in from each side and 28.00 mm apart — use the breakout itself as the
    drill template rather than trusting a dimension off a drawing.

**SH is bonded to ground at the main board only, and left floating at the sensor.** With UTP the
plug has no shield contact so SH is electrically dead either way; bonding one end costs nothing and
means that if a shielded patch cable is ever fitted by accident, the shield is grounded at exactly
one end instead of forming a loop around the whole run.

#### Series termination: fit 68 Ω, do not wait for a symptom

`R2`/`R3`/`R4` on the main board are **68 Ω ¼ W metal film, fitted from the start** — not the wire
links an earlier revision of this section called for. The reasoning, because the earlier advice was
wrong in an instructive way:

- **Only the lines the ESP32 *drives* get one.** Series termination works at the *source*: it makes
  `Z_out + R ≈ Z_line` so the wave returning from the far end is absorbed rather than re-reflected.
  The ESP32 drives SCLK, MOSI and CS. MISO and IRQ are driven by the AS3935 three metres away, so a
  resistor on those at *this* end sits at the receiver and damps nothing.
- **What makes the cable electrically long is the edge rate, not the clock rate.** The ESP32's edges
  stay a few nanoseconds however slowly you clock it. Cat5 propagates at ~5 ns/m, so the round trip is
  ~10 ns at 1 m and ~30 ns at 3 m — long compared with the edge at three of the four §16 sweep points.
  Dropping to 200 kHz removes the *timing* consequence of the ringing, not the ringing.
- **The consequence lands exactly where this design is trying to be careful.** Unterminated, the
  ESP32's ~30 Ω output launches ~2.5 V into a ~100 Ω line; that doubles at the AS3935's
  high-impedance input, and the ESD clamps that catch it dump the excess **into the sensor's local
  3.3 V rail**, on every clock edge, centimetres from the pins. The whole two-box architecture, the
  LDO at the far end and C4 at the pin exist to keep that rail quiet.
- **68 Ω** ≈ `Z_line − Z_out` ≈ 100 − 30. Cost at 200 kHz is a ~10 ns rise against a 5 µs bit period.
  It is a clean match only for SCLK, whose pair partner is its own ground return (pins 3 and 6); MOSI
  and CS return through whatever ground is nearest, so for those 68 Ω is an approximation.
- ⚠️ **Why "fit them only if the sweep misbehaves" was bad advice.** At 200 kHz the overshoot does not
  corrupt data, so the distance sweep would look clean either way. The guidance was watching for a
  symptom this fault does not produce.

**Open question — the other direction.** By the same argument MISO and IRQ want series resistors at
*their* driver, i.e. on the sensor board at the AS3935's own pins, and the §7.5 layout has no
positions for them. Two things make this lower priority: the overshoot then lands on the *ESP32's*
rail, metres from the antenna, where injected clamp current does not threaten anything; and
low-power sensor outputs are often weak enough (100–500 Ω) to be self-damping, in which case a
resistor is unwanted. **Unresolved** — it needs the AS3935 datasheet's output drive figure, which has
not been checked. Worth settling before the sensor board is soldered, since adding two positions
afterwards means re-laying it.

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

### 7.5 Protoboard layout

`as3935-protoboard-layout.pdf` (regenerate with `python3 make-protoboard-layout.py`) is the physical
plan: which hole every part and every wire goes in, on **0.1″ perforated board with isolated pads**.
Five pages — placement and wiring for each board, then build order and the traps. §7.1–§7.4 say what
connects to what; this says where it sits.

Both boards are the perf actually in hand, and they are written two different ways:

- The **sensor board** is a **1-18 × A-X** board — 24 columns lettered **A–X** across the long side,
  18 rows numbered from the bottom — and its coordinates are written the way the board prints them: letter,
  then number (`Q10`). Nothing has to be counted. Seen from the component side it reads **A1 at the
  bottom left and X18 at the top right**, and the drawing is drawn that way up. The letters assume the
  board uses all 24 of A–X; some boards skip I to avoid confusion with 1, and on one of those every
  column from I on would be one letter off.
- The **main board** is **27 columns × 17 rows**, unlettered, with coordinates counted `(col, row)`
  from hole (1,1) at the top-left. Everything below is duplicated in the PDF; it is here so a clone without a
PDF viewer still has it.

⚠️ **Isolated pads, not stripboard.** Every row in this layout is drawn as bare board with buses added
where wanted. On stripboard the rows are *already* connected and the layout is wrong without track cuts.

On both boards the RJ45 breakout's own right-angle header solders straight into one run of **nine
holes**, so the breakout stands on edge with the jack facing off the board — and the three rows or
columns behind it are then out of reach from the top. Wire to the numbers silkscreened on the
breakout (§7.1), not to a position.

#### Sensor board

Seen from the component side the board reads **A1 at the bottom left and X18 at the top right**, and
the drawing is drawn that way up. **J2**, the RJ45 breakout, stands on edge in **column A** with its
jack facing off the A edge; the power chain runs along the **top three rows**; and **M1**, the
SEN-39003, stands on its header in **column S** — the nearest column that puts its loop antenna past
the X edge, clear of every pad. Rows 1–7 are empty: room for the nylon standoffs.

| Ref | Part | Holes |
|---|---|---|
| J2 | RJ45 breakout, 9-way right-angle header | A8 … A16, SH at A16, jack off the A edge |
| R1 | 100 Ω ¼ W metal film | E18 – H18 |
| C2 | 47 µF 50 V, EEU-FR1H470 | + J18, − J16 |
| U1 | MCP1700-3302E, TO-92 | GND M16, VIN M17, VOUT M18 |
| C3 | 1 µF X7R | + O18, − O16 |
| C4 | 100 nF X7R | + R17, − R16 |
| M1 | SEN-39003 on an 8-pin header | S10 … S17, soldered direct |

M1's header, as confirmed on the part — antenna to the right, top to bottom: VDD S17 · GND S16 · CS S15 · SI S14 · IRQ S13 · SCK S12 · MISO S11 · MOSI S10.
J2's, header down with SH at the top: SH A16 · 8 IRQ A15 · 7 CS A14 · 6 GND A13 · 5 MISO A12 · 4 MOSI A11 · 3 SCLK A10 · 2 GND A9 · 1 5 V A8.

**U1 is a TO-92 whose pins read GND, VIN, VOUT** — flat face toward you, leads down, left to right.
That is *not* the 78xx order, and it puts VIN in the middle, where a bus running along a row cannot
reach it past GND. So U1 stands with its leads down column M and its flat face toward C3: GND drops
straight into PG at M16, VOUT sits on BUS-B at M18, and only VIN needs a wire — W-S4, from
the end of BUS-A into M17. Turned round, it would put 5 V on its ground pin.

Buses — bare 22 AWG laid *across the back* of the pads and soldered to each, not threaded through, so
every hole stays free for a component lead as well:

| Bus | Net | Run |
|---|---|---|
| BUS-A | 5 V filtered | row 18, H–K |
| BUS-B | 3.3 V | row 18, M–R |
| BUS-C | **PG** power ground | row 16, F–O |
| BUS-D | **SG** sensor ground | row 16, Q–R |

Hole L18 stays empty between BUS-A and BUS-B: that gap is the input/output isolation. P16 is the gap
between PG and SG, and W-S9 bridges it — the only place the two grounds meet.

| Ref | Net | From | To |
|---|---|---|---|
| W-S1 | 5 V in | A8 | E18 |
| W-S2 | GND pin 2 → PG | A9 | G16 |
| W-S3 | GND pin 6 → PG | A13 | F16 |
| W-S4 | 5 V → U1 VIN | K18 | M17 |
| W-S5 | 3.3 V → C4 / VDD | R18 | R17 |
| W-S6 | VDD link | R17 | S17 |
| W-S7 | sensor GND → SG | S16 | R16 |
| W-S8 | SI strap → SG | S14 | Q16 |
| W-S9 | **SG–PG tie** | O16 | Q16 |
| W-S10 | SCLK | A10 | S12 |
| W-S11 | MOSI | A11 | S10 |
| W-S12 | MISO | A12 | S11 |
| W-S13 | CS | A14 | S15 |
| W-S14 | IRQ | A15 | S13 |
| — | SH | A16 | *nothing — bonded at the main board only* |

**Two grounds, one tie.** PG carries the cable's return, the bulk cap and the LDO reference; SG carries
only the sensor's GND pin, its 100 nF and the SI strap. They meet at W-S9 and nowhere else. Bridge them
anywhere else and you have wrapped a ground loop around the LDO and the 100 nF stops being local —
which is the entire reason §7.2 puts a regulator out there at all. *Where* along PG you tie is not
critical: at 350 µA the drop along the bus is nanovolts. That there is exactly one tie is.

**C3 references PG, C4 references SG.** C3 is the MCP1700's stability capacitor, so it belongs to the
regulator; C4 is the sensor's decoupling, so it belongs to the sensor. Swapping them defeats the split
as surely as a second tie would.

**C4 sits one hole from VDD and one from GND.** That loop is the point of the part. Do not move it to
make room for something else. It sits right at M1's edge, so keep it low enough to clear the breakout.

- **Columns B–D are out of reach from the top** once J2 is in — the breakout stands just behind its
  pins. Nothing is placed there; the wires that cross them run on the back.
- **The antenna overhangs the X edge, on purpose.** With the header in column S the loop is clear of
  every pad. Keep T–X under M1 empty, and keep the box wall and its screws clear of the antenna.
- **Solder the SEN-39003 header straight into the perf, no socket.** Solderless contacts on this rail
  are the prime suspect for the §11.3 step change, and the board is calibrated per unit, so it is not
  something you swap casually anyway. Nylon hardware only near the antenna: a steel screw beside a
  500 kHz loop is a shorted turn.

#### Main board

The dev board lies **lengthwise** with the USB end overhanging the left edge — a 90° clockwise rotation
of the usual portrait pinout drawing, so the portrait *left* column becomes the top row read
bottom-to-top. **J1**, the RJ45 breakout, solders its right-angle header straight into the **bottom
row**, so it stands on edge with the jack facing off the board. With 17 rows there is no room for a
resistor footprint between the two headers, so everything between them is soldered **pin to pin on
the back**, straight down one column — which is what forced the GPIO choice in §7.1.

| Ref | Part | Holes |
|---|---|---|
| A1 | ESP32-DevKitC V4 (WROOM-32D) | female headers, row 4 cols 2–20 and row 14 cols 2–20 |
| C1 | 470–1000 µF 16–25 V 105 °C | + (3,3), − (5,3) — stripe at (5,3), body overhangs the top edge |
| J1 | RJ45 breakout, 9-way right-angle header | row 17 cols 7–15, **SH at col 7** (the USB end), jack off the bottom edge |
| R2 | SCLK series, 68 Ω ¼ W | (13,14) – (13,17), pin to pin on the back |
| R3 | MOSI series, 68 Ω ¼ W | (12,14) – (12,17), pin to pin on the back |
| R4 | CS series, 68 Ω ¼ W | (9,14) – (9,17), pin to pin on the back |

Row 4 (top), cols 2→20: `5V CMD D3 D2 13 GND 12 14 27 26 25 33 32 35 34 VN VP EN 3V3`.
Row 14 (bottom), cols 2→20: `CLK SD0 SD1 15 2 0 4 16 17 5 18 19 GND 21 RX0 TX0 22 23 GND`.

J1, row 17, **SH at the left**: SH (7,17) · 8 IRQ (8,17) · 7 CS (9,17) · 6 GND (10,17) ·
5 MISO (11,17) · 4 MOSI (12,17) · 3 SCLK (13,17) · 2 GND (14,17) · 1 5 V (15,17). Directly above in
row 14 sit GPIO4, GPIO16, GPIO17 (unused), GPIO5, GPIO18, GPIO19, GND and GPIO21 (unused) — so IRQ,
CS, MISO, MOSI, SCLK and cable pin 2 each fall straight down their own column.

| Ref | Net | From | To | Side |
|---|---|---|---|---|
| W-M1 | C1+ → 5V | (3,3) | (2,4) | back |
| W-M2 | C1− → GND | (5,3) | (7,4) | back |
| W-M3 | IRQ, no resistor | (8,14) | (8,17) | back, pin to pin |
| W-M4 | MISO, no resistor | (11,14) | (11,17) | back, pin to pin |
| W-M5 | GND → cable pin 2 | (14,14) | (14,17) | back; soldered to (14,15) on the way |
| W-M6 | cable pin 6 stub | (10,17) | (10,15) | back |
| W-M7 | SH stub | (7,17) | (7,15) | back |
| W-M8 | ground hop | (7,15) | (14,15) | **component side**, tapped at (10,15) |
| W-M9 | 5 V to cable | (3,3) | (15,17) | back, via (21,3) and (21,17) |

- **J1's orientation is set by the jack, not by preference.** Header down with the jack facing off the
  edge, the pins read `SH 8 … 1` (§7.1), so SH lands at the USB end. Check it overhangs the edge
  before soldering. It stands ~30 mm tall; allow for that in the enclosure (§9), and let the wall take
  the plug force, not the nine header joints.
- **Everything between the headers is pin to pin on the back.** R2/R3/R4 and W-M3/W-M4/W-M5 lie flat
  between the ESP32 joint and the jack joint below it. Cols 11–14 are four parallel runs 2.54 mm
  apart: insulated wire for the links, short straight leads on the resistors.
- **W-M8 is on the component side because it has to be.** Those six runs wall off the back of rows
  15–16, so cable pin 6 (col 10) and SH (col 7) cannot reach ground at col 14 without crossing them.
  W-M8 hops over the top instead. **Fit it before J1** — afterwards the breakout stands over row 16
  and it is out of reach.
- **5 V goes round the end of the header, not between its pins.** W-M9 runs along row 3, down col 21
  and back along row 17. Every shorter way to row 17 squeezes between two header joints a millimetre
  apart. It is long; at ~1 mA that costs nothing.
- **Three cable grounds, one ESP32 pin.** Pins 2, 6 and SH all meet at the GND at (14,14), directly
  beside GPIO19 — so the SCLK pair (3,6) returns right next to its driver. C1 keeps the top-row GND at
  (7,4) to itself. SH is bonded here and left floating at the sensor (§7.1).
- **Socket the ESP32, unlike the sensor.** Dev boards die, and this one is metres from the antenna.
  Keep BOOT and EN reachable. **Measure its header row spacing first** — drawn at 10 holes (1.0″); if
  yours is 0.9″, only the top header and C1 move (top row → row 5, C1 → (3,4)/(5,4)). Use the dev
  board itself as the jig.
- **C1 is as tight as the DevKitC allows.** Five pins between `5V` and its nearest ground: ~27 mm of
  loop however you arrange it. Keep W-M1 and W-M2 short.
- **R2/R3/R4 are 68 Ω** — reasoning in §7.1.

#### Traps

- **The wiring pages are X-ray views** — drawn as if you could see through the board from the
  component side, because that is how you place parts. Flip the board to solder and left/right swap.
- **A bare RJ45 jack does not fit 0.1″ perf** — its pins are off-grid. The breakout's 9-way header
  does, and on both boards it solders straight in, standing on edge. The three rows or columns
  behind it are then out of reach from the top, so anything there goes in first.
- **Crossings are fine, except over a bus.** Point-to-point links are insulated and run on the solder
  side; they cross each other freely. The four sensor-board buses are *bare*.
- **Rigidity is a measurement, not a feeling.** §11.3: the breadboard's noise floor fell by two thirds
  the moment the build was handled. §15 Phase 2 is survey → handle the box → survey again.

### 7.6 Wire

`as3935-node-wiring.pdf` page 6 has this as a printable table. The short version:

**Gauge is electrically irrelevant on both boards.** Past the RJ45 the whole sensor rail draws under
1 mA; the longest run on either board is about 90 mm, so even 30 AWG would add ~30 mΩ — 15 µV at
500 µA. R1 drops 0.1 V *on purpose*, six thousand times more. The only current worth the name is the
300–500 mA WiFi burst through C1's two links, which are ~10 mm long and would be fine in 30 AWG too.
**The one place gauge ever mattered in this project is the USB cable (§7.4), and that is a cable you
buy, not one you build.** Everything below is chosen on mechanical grounds.

| Where | What | Length | Why |
|---|---|---|---|
| Sensor-board buses | **bare solid tinned copper, 20–22 AWG** | ~1 m | must lie straight across a row of pads |
| Links, both boards | **insulated solid, 24 AWG** (26 also fine) | ~2 m | must enter a 1 mm hole unaided |
| USB brick → ESP32 | none — it plugs into the micro-USB | — | grommet and strain relief only |

- ⚠️ **The stranded silicone hookup wire already on hand (16/18/20/24 AWG) is the wrong wire for
  this.** It is excellent wire — for something else. Stranded will not enter a 0.1″ hole without being
  tinned first, and a tinned end is a solid end with worse geometry. Silicone insulation is thick and
  soft, so at 2.54 mm pitch it crowds neighbouring holes and will not hold a route. And a bus has to
  be a straight bare bar soldered to eight pads in a row: stranded cannot be made straight. Keep it
  for the mains variant (§7.3) and for anything that has to flex.
- **Not 30 AWG Kynar wire-wrap**, tempting as it is. It is the classic perfboard wire and genuinely
  nicer to route, and it is also fragile — and §11.3 is this project's warning about builds that move.
  Rigidity is pass/fail here (§15 Phase 2), so spend the extra bulk on 24 AWG solid.
- Colour discipline: with J1 and J2 both soldered straight in there are no pigtails, so every wire on
  both boards uses one plain code — red 5 V, orange 3.3 V, black ground, blue SPI, green IRQ. The
  T568B colours only matter inside the patch cable.

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
- **`logger: level: VERBOSE`** — the level this project needs, and enough. Everything it reads is an `ESP_LOGV` call site, which is VERBOSE: the `INT_NH`/`INT_D`/`INT_L` lines, `read_register_`, the §12.1 tune-cap line, and the `'Lightning Distance' >> … km` publishes that `ambient-survey.py` parses. VERY_VERBOSE adds only api/scheduler chatter, which is what saturated `loop()` in §8.4. ⚠️ **At VERBOSE and above, ESPHome prints the WiFi password in plain text** (`[V][wifi]: Password: '…'`) every time it connects to WiFi — at boot and on each reconnect. Treat any saved raw log from this node as containing it; `tools/ws-log-bridge.py` redacts it.

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

**On verifying capacitance:** note that the `Setting tune cap to N pF` line is computed in software (`capacitance * 8`) and printed *before* the write — it confirms what ESPHome intended, not what the chip stored. It is still worth checking, but it is not proof. Set `logger: level: VERBOSE` (or higher) and confirm the log line reads **`Setting tune cap to 72 pF`** (the component logs `capacitance * 8`, so 9 → 72). If it prints anything other than your label value, that's a genuine bug — fall back to PWF's Arduino SPI sketch bridged to MQTT.

⚠️ **This check requires a serial connection — it is not visible over WiFi at any log level.** The line is printed from `setup()`, before the API is up. See **§12.1** for the procedure and the reason.

### ⚠️ 8.4 The per-strike path to Home Assistant does not work

**This is the project's core deliverable failing, and it is not a sensor problem.** Verified 2026-08-20.

> **Deferred by decision, not by oversight.** This is tracked as a **separate body of work** from the hardware revision, to be picked up once the hardware is finalised. It is neither blocked by the rebuild nor blocking it, and mixing the two would muddy the measurement work. The diagnosis below is complete; only the fix is outstanding.

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

- Contents: SEN-39003, MCP1700 LDO, the §7.2 passives, and J2, the RJ45 breakout. That is all.
- **J2 is soldered to the perf**, standing ~30 mm tall on its header with the jack facing off the board's A edge, so the board mounts with that edge against a wall and the jack through a cutout. The wall must take the plug force, not the header joints. The SEN-39003's antenna overhangs the opposite, X edge: keep the far wall and any screws clear of it.
- **Sealed is fine** — it dissipates essentially nothing, so unlike the main box there is no bake risk, and an attic is dry.
- Sensor PCB on **nylon standoffs**, antenna clear of the box screws and of the RJ45 jack's metal shell.
- **Mechanically rigid.** §11.3 is a warning here: if flexing the box moves the noise floor, the build is furniture rather than an instrument. §15 Phase 2 tests exactly this.

### Main enclosure

- Contents: ESP32-DevKitC V4, C1 at its `5V`/`GND` pins, R2/R3/R4, the RJ45 breakout (J1), USB entry.
- **J1 is soldered to the perf**, standing ~30 mm tall on its header with the jack facing off the board's bottom edge, so the board mounts with that edge against a wall and the jack through a cutout. The wall — or a bracket on J1's own mounting holes — must take the force of plugging a cable in; the nine header joints are not a mechanical mount.
- **The USB brick's own cable plugs into the dev board's micro-USB.** There is no soldered supply wire in this box; the grommet and strain relief are the whole of the mechanical work.
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

**Run a survey.** The node must be at `logger: level: VERBOSE` or higher (§8):

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

**Or skip the local ESPHome entirely.** `tools/ws-log-bridge.py` takes the same stream from the ESPHome dashboard, needs no `secrets.yaml` on the workstation, and exits when the survey closes the pipe — no FIFO. Validated against serial on 2026-09-13 (§12.2); setup on a fresh machine is in `tools/README.md`.

**Correlating against the house.** The eliminations in §11.3 came from Home Assistant metrics in Prometheus, reachable through Grafana's datasource proxy — note the **uid** form of the path works where the numeric-id form 404s:

```
/api/datasources/proxy/uid/<datasource-uid>/api/v1/query_range
```

`hass_sensor_power_w` carries ~80 per-circuit power series and is the tool that ruled out the gable fan and the air handlers. **Caveat that bit once:** HA only records state *changes*, so an entity republishing an identical value leaves no trace. Event *rates* cannot be reconstructed from Prometheus — which is why the surveys have to be run live rather than mined from history afterwards.

### 11.5 The noise floor: characterised, but not explained

`INT_NH` is the one interference class that is **continuous** — while the measured noise floor sits above the `NF_LEV` threshold the AFE is effectively deaf, which makes it more corrosive than the disturber rate it is usually mistaken for. The bench logged essentially zero noise interrupts; the attic runs at 100–275/min. Analysis of the 168 five-minute buckets from §11.3:

**It is bimodal.** Not a drifting ambient level. The distribution has a quiet cluster at ~250–350 counts per bucket and a loud mass at ~900–1500, with a sparse valley between. Something discrete is switching.

**It is irregular.** Runs of 10–90 minutes in each state, roughly 60/40 loud to quiet, with no periodicity and no diurnal trend. Not a duty-cycled appliance, and not a simple day/night propagation effect.

**Nothing in the house tracks it.** Mean power was compared across all 62 usable per-circuit series between loud and quiet buckets. The largest deltas are ~5% wobbles on multi-kW rollups; no circuit switches with the noise state. Node temperature is flat too (55.2 °C loud vs 54.6 °C quiet, ranges fully overlapping), which rules out a thermally-driven intermittent contact.

**Also ruled out:** mains-conducted coupling (the power-bank hour barely moved it — 138/min against a 181 mean, well inside the observed range) and the HVAC.

⚠️ **The limitation of that negative result matters.** Whole-house metering can only exclude *large* loads. A 5 W device switching on and off is invisible against a 5 kW aggregate — a PoE-powered device drawing through a switch is the obvious example. "Not in the power data" means "not a big load", **not** "not in the house."

**What would actually resolve it:** an SDR covering ~500 kHz with a loop antenna, listening next to the sensor. That is a direct measurement of what is in the band, rather than more inference from proxies. The §15 Phase 3 rotation test would give a bearing. **[`sdr-interference-hunting.md`](sdr-interference-hunting.md)** is the standalone guide: what to buy, what not to buy, how to build the loop, and how to run the hunt — including correlating `rtl_power` output against the survey buckets before chasing anything.

**But re-measure on the protoboard first.** Every number above came from the platform §11.3 disqualified. The bimodality may not survive the rebuild, and buying instruments to chase an artefact would be a poor trade. (Rev 2 has logged **one** `INT_NH` in over four hours of surveys on the bench and in the woodshop — at the emulator's power-up, §11.7 — but the attic is where the floor lived.)

### 11.6 Rev 2 on the bench: a first Phase 2 attempt, inconclusive — 2026-09-13

After the §12.2 bring-up the node moved to the USB brick. **In the same power-down both boards were handled and the 1 ft patch cable was swapped for a 5 ft one** — three changes at once, which is most of what this section has to teach. Surveys then ran over WiFi through `tools/ws-log-bridge.py` with the laptop disconnected. The sensor board stayed within a few inches of its earlier spot throughout. Config unchanged: bench-tuned, `logger: VERBOSE`.

| Window | Supply, cable | Conditions | Disturbers | Lightning | Noise |
|---|---|---|---|---|---|
| 12:13–12:23 (10 min, serial) | laptop USB, 1 ft | **before handling.** Shop lights on, operator present, AC compressor running | **0** | 0 | 0 |
| 13:05:40–13:40:40 | brick, 5 ft | **after handling.** Lights on, operator present, reading | **49 = 1.4/min** — 5, 6, 5, 6, **12**, 9, 6 per 5 min; peak 13:25:40–13:30:40 | 0 | 0 |
| 13:40:40–14:00:40 | brick, 5 ft | operator left at ~13:39 and the shop lights went off with them | **2 in 20 min** | 0 | 0 |
| 14:00:40–14:06:16 | brick, 5 ft | operator and lights back at ~14:04, bench LEDs ~14:05 | 2 | 0 | 0 |
| 14:07:17–14:22:18 | brick, 5 ft | lights on, operator present, reading | **5 = 0.33/min** — at 14:10:36, 14:11:38, 14:13:24, 14:14:01, 14:22:15 | 0 | 0 |

The window AC ~1.2 m away cycled on and off all afternoon; its compressor stopped at ~12:31:50 and its integration does not expose compressor state. Also within reach: the first-floor air handler and a condensate pump.

What it shows, and what it does not:

- **False lightning stayed at zero in every window, including after handling.** The §11.2 figure of merit is clean throughout, and disturbers never reach Home Assistant.
- **The rate is driven by something that varies on a scale of tens of minutes and is not visible from the bench.** The drop at 13:40 looked like the lights or the operator — but 14:07–14:22 had the same spot, the same lights and the same operator doing the same thing as 13:05–13:40, at a quarter of the rate. Candidates that switch on that timescale: the window AC (circuit 16B), the first-floor air handler, the condensate pump.
- **It does not look like the breadboard's failure.** The breadboard's floor stepped on contact and *stayed* stepped (§11.3). Here the rate rose after handling and then fell away over the following hour with nothing touched — an environmental signature. But the design cannot exclude that handling raised the build's *susceptibility* with the room deciding how much of it showed, and with three simultaneous changes the 0 → 1.4/min step cannot be pinned on handling, the 5 ft cable or the brick.
- **A quiet ten minutes proves nothing here.** The rate swung about five-fold between windows half an hour apart; the "before" leg was only ten minutes long.

**Verdict: Phase 2 neither passed nor failed.** Redone in a quieter spot the same day, and passed — §11.7, which also matches this afternoon against the window AC's compressor cycles.

### 11.7 Rev 2 in the woodshop: Phase 2 passed — 2026-09-13

Both boards moved together to the woodshop workbench, a quiet corner of the basement away from the window AC, the air handler and the condensate pump, about 4 ft (1.2 m) apart. **Nothing else changed:** the same Samsung 2 A brick, the same 5 ft patch cable, the same bench-tuned config at `logger: VERBOSE`. Every window was surveyed over WiFi through `tools/ws-log-bridge.py`, keeping the raw stream for per-event timestamps.

| Window | What | Lightning | Disturbers | Noise |
|---|---|---|---|---|
| 14:50:45–15:51:05 (60 min) | hands off, after the move | **0** | **0** | **0** |
| 17:51:12–17:54:40 | liveness check: emulator Uno powered up, 14 button presses, then the build pressed, flexed and its cable reseated | 0 | 15 | 1 |
| 17:54:59–18:55:05 (60 min) | hands off, after handling | **0** | **0** | **0** |

The liveness window, event by event:

- **17:51:29 disturber, 17:51:33 noise** — as the Uno powered up, with its boot LED sweep and DAC probe. Plausible attribution, not proven. It is the first `INT_NH` rev 2 has logged anywhere.
- **17:51:59–17:52:20: 14 disturbers, evenly ~1.6 s apart** — one per button press (the operator counted 14 or 15). All disturbers, as §11.1 predicts for the emulator.
- **17:52:20 to the end: nothing**, including the press, flex and reseat at ~17:53–17:54:30.

The node never rebooted: uptime ran unbroken from 482 s to 15,062 s across all three windows. WiFi held at −62 dB.

In the house during the surveys: the central AC compressors (AC Circuits 6 and 8, just outside the electronics shop wall) ran continuously. The window AC compressor started at 15:00:30 and ran the last ~50 min of the first hour, and all of the second. The basement lights (~850 W) switched several times. The woodshop circuits were idle.

What it shows:

- **Phase 2 passes.** Two hands-off hours at zero bracket a handling step, and the handling itself produced nothing — where the breadboard's floor moved for good on contact (§11.3), and meter leads on the sensor board produced ~210 disturbers/min (§12.2).
- **The liveness check is what makes the zeros mean anything.** The survey's health gate proves the log stream, not the sensor; a quiet room and a cable pulled loose in the move produce the same output. On the bench the room's own disturbers proved the sensor was alive. Somewhere quiet, only a deliberate stimulus can.
- **§11.6's disturbers were most likely the window AC.** Circuit 16B's current (§11.4) against that afternoon's buckets: 13:05–13:25 was short-cycling, with starts at 13:06 and 13:19, at 5–6 per 5 min. The peak bucket, 12 in 13:25:40–13:30:40, contains a stop and a restart. The long run from 13:30 decayed from 9 to 6 to ~0.1/min, and the first event of 14:07–14:22 came about a minute after the 14:10 restart. The central AC ran continuously and the air handlers held flat at ~288 and ~270 W, so neither can explain a change over tens of minutes. **Against it:** the 12:16:30 restart produced nothing (before the build was handled and the cable and supply changed); the 13:40 drop coincides with the operator and lights leaving; and with no per-event timestamps for 13:05–13:40 the match is by bucket only. In the woodshop the same compressor started and ran with nothing at all, which fits proximity (~1.2 m on the bench) mattering — but one start is not a test.
- **What it does not show:** anything about the attic. It says the build is stable, in one quiet spot, over one evening, still at `indoor: true` and `spike_rejection: 1`. The attic survey is the next measurement.

⚠️ **Circuit 16B's power entity is dead** — 0 W since 2026-07-28 — so it reads as "the AC was off all afternoon". Its current entity (`hass_sensor_current_a`, `sensor.emporia_energy_outlets16b_current`) works: ~10–12 A with the compressor running, ~1–2 A without. The circuit also feeds a sink pump.

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

With `logger: level: VERBOSE` or higher set, connect over USB. (The line is an `ESP_LOGV` call; an earlier version of this section said VERY_VERBOSE was required, which overstated it.)

```
esphome logs lightning-detector.yaml --device /dev/ttyUSB0
```

(In the dashboard, the Logs view lets you pick the serial port instead of the network.)

Look for `[as3935]` **`Setting tune cap to 72 pF`** — the component logs `capacitance * 8`, so `9` → `72`, matching the board label. **If it prints any other value, that's the genuine component bug** described in §8, and the PWF Arduino-sketch fallback applies.

Note the contrast for later: the *runtime* messages (`Noise was detected`, `Disturber was detected`, `Lightning has been detected!`) come from `loop()` and stream over WiFi normally. Only the one-shot `setup()` output needs serial — which is why the noise survey in §10 can be run headless, but this check can't.

### 12.2 Rev 2 bench bring-up — 2026-09-13

Both boards soldered per §7.5, first power-up. **Every check passed** — the 5 V check on the second attempt, once the node was moved to the intended brick.

Conditions: on the bench, **laptop USB** power, a 1 ft (~0.3 m, the shortest §16 sweep point) Cat6 patch cable, `logger: VERBOSE`, the bench-tuned config (`indoor: true`, `spike_rejection: 1`). A window air conditioner about 1.2 m away with its compressor running, and LED bench lighting.

| Check | Result |
|---|---|
| Main board alone, sensor unplugged | Boots and joins WiFi. Every AS3935 register reads `255` and calibration fails: with nothing on the bus MISO idles high. **This is the signature of "chip not answering"** — keep it for comparison. |
| §12 step 2 — 5 V at the ESP32 `5V` pin, WiFi active | 4.65–4.79 V, and the same at J1 pins 1–2, so the W-M9 run to the jack drops nothing measurable. **Marginal** against §7.4's ~4.7 V — but on laptop USB and an arbitrary cable, which is not what step 2 specifies. **On the intended brick (Samsung 2 A): 4.823 V at the sensor board with WiFi active — pass.** The sensor draws under 1 mA, so the Cat cable drops nothing measurable and the sensor board's 5 V is the ESP32's `5V` pin. |
| §12 step 3 — 3.3 V at the sensor VDD | **3.333 V.** |
| SPI | Mode 1 and 200 kHz confirmed from the boot log; pins 19/5/18/16/4. Every register reads back as configured: `REG0x00 = 0x24` (indoor gain), `REG0x01 = 0x22` (noise level 2, watchdog 2), `REG0x02 = 0xC1` (spike rejection 1, one strike). |
| §12 step 4 — tuning capacitance | **The chip's own `TUN_CAP` reads back `9` = 72 pF**, as the read-before-write on a warm boot. That is stronger evidence than the §12.1 log line, which is computed and printed in software before the write. The cold-boot read of `0` was not captured (that capture was garbled — `tools/README.md`, "The serial port resets the node"); it would only have demonstrated the §8.3 OR behaviour, which cannot bite while `capacitance:` never changes. |
| Oscillator calibration | Successful. |
| §12 step 5 — emulator, `emulator-trial.py` defaults | **CLOSE 4/5, MID 5/5, FAR 5/5, SHAM 0/5**, every response a disturber — then 15/15 in a second run. The same result as the breadboard's 15/15 against 0/5 (§11): the interrupt path works. Latency 32–227 ms, the same spread as the breadboard's 34–226 ms, so that spread belongs to the host logging pipeline, not the sensor. |
| Ambient, 10 min, hands off | **Zero interrupts of any kind** — no noise-floor, disturber or lightning — with the AC compressor running throughout. Zero again in every emulator baseline since. |

**Against the breadboard.** §11.2 recorded 13–20 ambient interrupts/min on the bench under the same `spike_rejection: 1`, including 3–8 false `INT_L`/min. Rev 2 read none in ten minutes. Whether it sat on exactly the same spot was not recorded, so this is strong evidence rather than a controlled comparison — §15 Phase 2 is the test that makes it one.

Found along the way:

- **Probing the sensor board is a disturber source.** With meter leads on the sensor board to measure VDD, the chip reported **105 disturbers in about 30 s** (~210/min); with the probes off, zero. Never measure on the sensor board during a survey, and don't mistake a probe-induced flood for a fault.
- **Every serial tool here reboots the ESP32 when it opens the port** (DTR/RTS and the DevKitC auto-reset). Harmless to the sensor, which keeps power and registers, but it is why a sensor cold boot has to be caught by holding EN. Details in `tools/README.md`.
- **The WiFi log path can go through the ESPHome dashboard**, with no local ESPHome install or secrets: `tools/ws-log-bridge.py`, validated side by side against serial — 15 disturbers counted on each.

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
- **Rev 2 is dramatically quieter on first measurement** — zero ambient interrupts in ten minutes on the bench, against the breadboard's 13–20/min including 3–8 false lightning/min (§12.2). Strong evidence, not yet a controlled result (§11.6).
- **Change one thing at a time in Phase 2.** The first attempt handled the build, lengthened the cable and changed the supply in a single power-down. When the rate then moved, nothing could be attributed to anything (§11.6).
- **A quiet ten minutes is not a rate.** The bench's ambient disturber rate swung about five-fold over half an hour with nothing visible changing. Baselines need an hour, and per-event timestamps so bursts can be matched against the house.
- **Meter leads on the sensor board are a disturber source** — ~210/min while probing VDD, zero once they came off (§12.2).
- **Prove the sensor is alive before believing a zero.** Rev 2 read zero interrupts for an hour in the woodshop — exactly what a cable pulled loose in the move would also produce. A minute of emulator presses while watching the stream turned that zero into evidence (§11.7). The same goes for telemetry: circuit 16B's power entity read 0 W all afternoon because it had been dead for six weeks, while its current entity held the compressor's whole cycle history.
- **Keep the detector away from compressor motors.** The bench's disturbers most likely came from a window AC compressor ~1.2 m away: they peaked across its starts and faded through long runs (§11.7). Circumstantial, but nothing else in the house switched on the right timescale.
- **Read what a node is running from its own boot log, not from git history.** On 2026-09-13 a GPIO conflict was predicted from the commit history — the image was assumed to predate the pin change — and it was false: the node had already been rebuilt from the current YAML. `dump_config` settled it in seconds.

## 14. Deliverables

- `lightning-detector.yaml` — complete ESPHome configuration.
- `as3935-node-wiring.pdf` — printable point-to-point wiring set for the **rev 2** design (§16), six pages: system overview, main enclosure, sensor enclosure drawn part by part, **connector and board pinouts** (the RJ45 breakout in both orientations and the ESP32-DevKitC V4 pin map), the wire schedule, and the wire specification plus bring-up checklist.
- `sdr-interference-hunting.md` — standalone guide for the §11.5 noise-floor investigation, *if* it survives the rebuild. Which dongle and why (RTL-SDR Blog V4, with the reasoning against direct-sampling alternatives), why the bundled antennas are useless at 600 m wavelength, how to wind and tune a 500 kHz direction-finding loop, driver setup, and a method that correlates before it chases.
- `as3935-protoboard-layout.pdf` — hole-by-hole placement and point-to-point wiring for both boards on 0.1″ perf board (§7.5): placement and wiring pages for each, then build order and the traps. Wire references match the schedule in the wiring PDF.
- `make-protoboard-layout.py` — regenerates that PDF (`python3 make-protoboard-layout.py`, needs `reportlab`).
- `DRAWING-VERSION` — one hand-bumped line, read by both generators and printed centred in every page footer of both PDFs. The two documents are only usable together, so a printout of each should carry the same stamp; if they differ, one is stale. It is a **date**, not a revision number — every page already carries *revision 2*, which is the hardware revision (§16), and a second small integer beside it just invites the wrong comparison. Bump it whenever either drawing changes and regenerate **both**.
- `make-wiring-diagram.py` — regenerates the wiring PDF (`python3 make-wiring-diagram.py`, needs `reportlab`). The rev 1 drawing had no generator in the repo and could not be revised; this one can.
- `sen39002-emulator-uno/` — PlatformIO project running the SEN-39002 emulator shield on a spare Arduino Uno R3, with its own [README](sen39002-emulator-uno/README.md).
- `tools/` — measurement instruments, with their own [README](tools/README.md).
  - `ambient-survey.py` — the site-survey instrument behind §11.3. Reads a serial port *or* a piped `esphome logs` stream (`--stdin`), so it works on a node already mounted. Counts `INT_NH`/`INT_D`/`INT_L`, interprets the distance *codes* (§8.2), pairs each `INT_L` with its energy, and buckets a timeline. Health-gated: a source producing nothing aborts, and a run parsing zero lines reports `MEANINGLESS` rather than a quiet site.
  - `emulator-trial.py` — the sham-controlled harness behind §11.1.
  - `ws-log-bridge.py` — streams the node's logs from the ESPHome dashboard's websocket to stdout, for `ambient-survey.py --stdin` where ESPHome is not installed locally. Validated side by side against serial (§12.2).
- `README.md` — this document.

## 15. Next steps, in dependency order

**Everything below the first item is blocked by it.** This is not a priority ranking, it is a dependency graph.

### Phase 1 — Rebuild on protoboard (blocking)

**Done 2026-09-13 — see §12.2.** The tuning capacitance came back as the chip's own register reading 72 pF.

No measurement taken on the breadboard can be trusted (§10.2, §11.3), so this gates every remaining question. Requirements are in §16; the hole-by-hole layout for both boards is in §7.5 and `as3935-protoboard-layout.pdf`, and what wire to buy is in §7.6.

While the node is on USB for bench bring-up, take the one measurement that cannot be made over WiFi: **verify the tuning capacitance over serial** (§12.1). Note that whether a bad `TUN_CAP` contributed to the pre-rebuild numbers is **no longer answerable** — the register has been cold-cycled since, and whatever it held for those 34 hours is gone.

### Phase 2 — Prove the new platform is a valid instrument

**Passed, in the woodshop, 2026-09-13 (§11.7).** Zero interrupts of any kind for an hour hands-off, nothing during handling, zero for an hour after, and an emulator check between the hours proving the sensor was alive. The first attempt, on the electronics bench, was inconclusive (§11.6); its disturbers most likely came from the window AC compressor.

The procedure that passed, for re-use:

1. **Move both boards to a quiet spot, together**, changing nothing but the location.
2. **Survey for an hour** over WiFi (`tools/ws-log-bridge.py`), saving the raw stream so every event has a timestamp (`tools/README.md`).
3. **Prove the sensor is alive**: fire the SEN-39002 emulator with its shield buttons while watching the stream. A zero from a quiet spot means nothing until this is done.
4. **Handle the build, and only that** — press on it, flex it, reseat the cable in its jacks.
5. **Survey for another hour**, the same way.

**Before the attic, fit the final hardware all at once:** the enclosures (§9) and the 22 AWG micro-USB cable, with the brick on a short mains extension beside the main box so the USB run stays short (§7.4). Then check liveness with the emulator again, and 5 V at the ESP32 `5V` pin with WiFi active, once. Doing all of that *before* the attic baseline means nothing changes partway through it.

Cable length and supply are separate one-variable experiments afterwards; cable length is the §16 distance sweep.

### Phase 3 — Redo the measurements that are currently meaningless

- **Re-survey the garage attic.** The location has never had a fair verdict, in either direction. §11.3's 0.6/min average is encouraging but uninterpretable. Survey for several days, so the rate is seen through daily heat cycles, and run the emulator liveness check at install (§15 Phase 2 step 3) — if the attic is as quiet as the woodshop, a zero will need that proof again.
- **Hunt the noise floor (`INT_NH`).** Characterised in §11.5 and still unexplained: bimodal, irregular, invisible to whole-house power metering, unmoved by removing mains coupling, uncorrelated with temperature. **Re-measure on the protoboard before investing in it** — the bimodality may be an artefact of the disqualified platform. If it survives, the next instrument is an SDR covering ~500 kHz with a loop antenna, listening beside the sensor — see [`sdr-interference-hunting.md`](sdr-interference-hunting.md).
- **Rotation test.** Now finally meaningful: §10.1's null-bearing logic assumes a distant, stationary source, which was violated while sensor and ESP32 were bolted to the same breadboard. With the sensor in its own enclosure on a cable it can turn independently.
- **Tune for deployment.** `indoor: false` for attic AFE gain, and back `spike_rejection` off its bench floor of 1. Read `INT_L` *alongside* the disturber rate when judging, not instead of it (§11.3).

### Phase 4 — Make it actually deliver

- **Catch a real storm.** The only true validation (§11.1). Watch for `Lightning Distance` in the **5–40 km** range; `1` is the overhead bin where local EMI lands and **`63` is not a distance** but the out-of-range code (§8.2). Cross-check timestamps against lightningmaps.org and the WS90.
- Roof-mount the WS90 (still at ground level).
- Optional, long-term: host a Blitzortung station for geolocated network data.

### Separate track — the Home Assistant per-strike path

**Deliberately not part of the phases above.** §8.4 is a complete diagnosis of a real defect, it is not blocked by the hardware work, and it does not block it. Interleaving the two muddies the measurement campaign, which is why it keeps being deferred on purpose rather than forgotten.

Pick it up **once the hardware is finalised**, as its own body of work:

- Fix the per-strike path (§8.4).
- Home Assistant automations and a dashboard card, once per-strike events actually arrive.
- Optionally settle *why* the pulse vanishes — HA-side logs are in Loki. Interesting rather than necessary, since any fix routes around it.

## 16. Hardware revision 2 — the spec

Decisions settled 2026-08-22. Wiring detail is in §7, the physical protoboard layout in §7.5, the wire specification in §7.6; this is the rationale and the build checklist.

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
| **Solid wire on the boards, not the stranded silicone** | Buses must be straight bare bar; links must enter a 0.1″ hole. Gauge is electrically irrelevant here. | §7.6 |
| **Cable shield bonded at the main board only** | Single-point: bonding both ends would loop the whole run. | §7.1 |
| **68 Ω series terminators fitted on SCLK/MOSI/CS** | Unterminated, clamp current from the far-end overshoot lands in the sensor's local 3.3 V rail. Not a symptom the sweep would show. | §7.1 |
| **SPI on GPIO 19/18/5/16, IRQ on 4 — not the VSPI defaults** | Each resistor must sit pin to pin over its jack pin; only this assignment lines them up. `lightning-detector.yaml` matches. | §7.1, §7.5 |
| **Bulk cap physically at the ESP32 `5V` pin** | Burst reservoir the cable resistance cannot supply fast enough. | §7.2 |
| **Main box vented, 105 °C electrolytics** | ~52 °C attic; sealed boxes bake and 85 °C parts die in a couple of summers. | §9 |
| **Both boxes non-metallic, mechanically rigid** | Antenna must not be shielded; and §15 Phase 2 is a pass/fail test on rigidity. | §9 |

### Decisions taken, and what was traded away

- **USB brick over mains.** The two-box layout moved the supply away from the antenna, which removed the *EMI* argument for an industrial part and left only reliability. §9's thermal argument against cheap bricks still stands and is knowingly accepted: the failure mode is loud (node drops off WiFi, visible immediately in HA), attic access is a walk-out door, and the part costs a few dollars. **The brick is a consumable.** IRM-05-5 and IRM-10-5 are on hand if this proves wrong.
- **RJ45 despite the PoE hazard.** The jack carries 5 V and SPI; a live PoE port would put 48 V on those lines and destroy both ends. Accepted knowingly, because certified pre-made patch cables are what make the distance sweep a clean experiment — hand-terminated cables would introduce a variable per length. Label both ends.
- **Sensor enclosure sealed, main enclosure vented.** Different reasoning for each: the sensor box has no meaningful dissipation, the main box does.
- **Deferred:** whether the mounting *spot* should change. Out of scope for rev 2 — the enclosure is the same wherever it goes, and the location cannot be judged until the platform is trustworthy (§15 Phase 3).
