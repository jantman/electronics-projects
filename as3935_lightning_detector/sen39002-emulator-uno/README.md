# SEN-39002 Lightning Emulator — Arduino Uno Driver

*Bench-test driver for the Playing With Fusion SEN-39002 "lightning emulator" shield, stacked on the Arduino Uno R3 it was designed for.*

Part of the [AS3935 lightning detector project](../README.md). This is a **standalone PlatformIO project** that runs on its own Uno — not on the ESP32 running ESPHome. Keeping the stimulus independent of the device under test is deliberate; see [§9 Why a separate board](#9-why-a-separate-board).

---

## 1. Purpose

Exercise the full detection path — AS3935 → SPI/IRQ → ESP32 → ESPHome → Home Assistant — on the bench, on demand, without waiting for a thunderstorm. Press a button or type a key, get a strike, watch it land in HA.

## 2. What you need

| Item | Notes |
|---|---|
| Playing With Fusion **SEN-39002** | The emulator shield. Headers must be soldered on (breakaway strip included in the package). |
| An **Arduino Uno R3** | The shield's native host. A Mega works too — same I²C and digital pins. |
| USB cable | Power and serial. The shield runs off the Uno's 5 V rail; no external supply. |
| The assembled AS3935 detector | Running the ESPHome config from the parent project. |

No jumper wires, no breadboard, no level shifter.

## 3. Wiring

**None. Stack the shield on the Uno.**

That is the whole job. Power, I²C (`A4`/`A5`), the three pushbuttons and the three LEDs all come through the shield headers. The Uno is a 5 V part and the shield was designed around it, so there is no logic-level question to answer and no rail to compensate for.

The shield's pin usage, for reference only — you do not wire any of it:

| Pin | Function |
|---|---|
| `A4` / `A5` | I²C SDA / SCL to both MCP4725 DACs |
| `D9` / `D7` / `D5` | FAR / MID / CLOSE pushbuttons (`INPUT_PULLUP`, pressed = LOW) |
| `D8` / `D6` / `D4` | FAR / MID / CLOSE LEDs (active LOW) |

## 4. How the shield actually works

Worth understanding, because it explains the range and the "distance" behavior.

The shield is **two MCP4725 12-bit I²C DACs** (addresses `0x62` and `0x64`) driving the large air-core solenoid on the board. **There is no RF oscillator.** The driver plays a decaying staircase into both DACs in lockstep:

```
{103, 73, 52, 37, 27, 20, 15, 11, 9, 7, 6, 5, 4, 4, 4, 3, 3, 3, 3, 3}
```

Those are raw 12-bit DAC codes — an exponential decay envelope. Each step change kicks the coil, and the resulting **near-field magnetic transient rings the AS3935's 500 kHz resonant loop antenna**. It is inductive coupling, not radiated RF, which is why the useful range is centimeters rather than meters.

### "Distance" is emulated by repetition count

This is the part that surprises people:

| Strike | Passes through the decay array |
|---|---|
| Far | 1 |
| Mid | 2 |
| Close | 3 |

Far, mid, and close are **not** different amplitudes or frequencies. They are 1, 2, or 3 replays of the *identical* burst. More total energy → the AS3935's internal algorithm computes a closer strike. That's the whole mechanism.

After the burst the DACs are powered down, then the driver waits one second. That pacing is deliberate: the AS3935 resolves roughly **one event per second**, and deactivates for ~1.5 s after classifying a disturber.

### The real profile is coarser than the array

PWFusion's MCP4725 library sends the low data nibble in the wrong place:

```cpp
Wire.write((output & 0x0FFF)>>4);  // D11..D4  -- correct
Wire.write(output & 0x000F);       // D3..D0   -- belongs in the UPPER nibble
```

The MCP4725's *Write DAC Register* command expects `D3..D0` in the **upper** nibble of that third byte; the lower four bits are don't-care. So the bottom 4 bits of every value are discarded and the DAC only resolves in steps of 16. What the coil actually sees is:

| | | | | | | | | |
|---|---|---|---|---|---|---|---|---|
| **requested** | 103 | 73 | 52 | 37 | 27 | 20 | 15 | 11 … |
| **actual** | 96 | 64 | 48 | 32 | 16 | 16 | 0 | 0 … |

— a six-step kick followed by thirteen steps of silence that still consume their I²C time.

**This is left alone on purpose.** PWFusion calibrated the profile and published the 4–10 cm working range against exactly this behavior, so the truncation is part of the calibration, not a defect to route around. `platformio.ini` pins the library to a specific commit for the same reason. If you ever want the untruncated profile, fork it and re-derive the working range empirically — don't assume PWFusion's distances still apply.

## 5. Build and flash

```bash
cd sen39002-emulator-uno

pio run                        # compile
pio run -t upload              # compile + flash
pio device monitor             # serial console @ 115200
pio run -t upload -t monitor   # all three
```

A genuine Uno R3 enumerates as `/dev/ttyACM0`; CH340-based clones show up as `/dev/ttyUSB0`. Ports are auto-detected — if you have several boards attached, uncomment `upload_port` / `monitor_port` in `platformio.ini`, or run `pio device list`.

**Verified:** clean build on PlatformIO Core 6.1.19, no warnings from this code or the PWFusion library under `-Wall -Wextra`. RAM 21.8% (446 / 2048 B), flash 17.5% (5650 / 32256 B).

### `platformio.ini` choices that are load-bearing

- **`lib_deps` pins PWFusion's MCP4725 library to a commit hash.** Not cosmetic — the library's nibble truncation *is* the calibration (§4). Don't unpin it, don't substitute Adafruit's MCP4725 library, don't "fix" it.
- **`monitor_filters` deliberately omits `send_on_enter`.** Commands are single characters; the monitor's default immediate-keystroke behavior is what they expect. Adding that filter would force you to press Enter after every strike.

## 6. Using it

Two equivalent controls: the **shield's three pushbuttons**, or the serial console. Open the monitor at 115200; every command is a single keypress, no Enter.

| Key | Button | Action |
|---|---|---|
| `f` | FAR | Far strike (1 pass) |
| `m` | MID | Mid strike (2 passes) |
| `c` | CLOSE | Close strike (3 passes) |
| `a` | — | Auto sequence: far, mid, then 4× close |
| `?` | — | Help |

The keyboard path exists so you can trigger strikes with both hands free while holding the coil at range. Opening the serial monitor resets the Uno (DTR), so you'll see the banner and LED sweep replay — that's normal.

For an unattended soak test, set `AUTOMATIC_TEST` to `1` in `src/main.cpp`; that's PWFusion's 50/50/50/100-strike sequence on a 10-second cycle.

### Startup check — read this before blaming the sensor

On boot the driver probes both DAC addresses:

```
DAC 0x62: OK
DAC 0x64: OK
```

**If either reports `NOT RESPONDING`, stop.** The shield isn't seated properly — that is not a detector problem. Chasing a silent AS3935 when the emulator never fired is the single easiest way to waste an afternoon. The startup LED sweep is the same check by eye.

### Suggested bench procedure

1. Bring up the detector per the parent project's **[§12 bring-up order](../README.md)**, on **USB only**.
2. Verify the AS3935 tuning capacitance over serial — parent **§12.1**. Do this first; a mistuned antenna makes everything downstream meaningless.
3. Flash this project to the Uno and open the monitor. Confirm both DACs report `OK`.
4. Position the emulator coil **~7 cm** from the AS3935's antenna. Keep phones and laptops ~30 cm away.
5. Press `f`, then `m`, then `c`. Watch the ESPHome log for `Lightning has been detected!` and check that **Lightning Distance** falls as you go far → close.
6. Press `a` and confirm Home Assistant renders the burst — this is the end-to-end path test.

### What to expect in Home Assistant

| Entity | Behavior |
|---|---|
| **Storm Alert** (binary sensor) | Pulses `on` for ~10 ms per strike |
| **Lightning Distance** | Updates per strike; should decrease far → mid → close |
| **Lightning Energy** | Updates per strike; relative magnitude only, not physical units |

Distances will **not** be 1:1 with the labels. The emulator is a coarse energy stimulus, not a calibrated distance source. What matters is that the three settings produce *distinguishable, ordered* readings.

## 7. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `DAC 0x62/0x64: NOT RESPONDING` | The shield isn't fully seated. Reseat it and check no header pin is bent under the board. |
| Nothing detected, DACs OK | Move closer — try 3–5 cm. Range is the main variable here; there is no amplitude control, by design (§4). |
| Still nothing at close range | Verify the AS3935 tuning capacitance first (parent §12.1). Then check `indoor: true` is set for bench testing. |
| Constant disturbers, no strikes | Expected indoors. Move away from noise sources; raise `noise_level` / `watchdog_threshold` / `spike_rejection`. Keep `mask_disturber: false` while testing so you can *see* them. |
| Detected, but distance never changes | The coil may be close enough to saturate the sensor. Back it off a few cm. |
| Strikes detected far more often than 1/sec | Not possible from this driver — it paces at 1/sec. Suspect real environmental noise. |
| Buttons fire twice | Shouldn't happen: the 1.1 s tail inside `emulate()` doubles as debounce. If it does, you're holding the button past that window. |

### ⚠️ Safety

The parent project's **one safety rule** applies whenever the detector is on USB:

> **Never have USB and the IRM-02-5 mains supply powered at the same time.** On most ESP32 dev boards the `5V`/`VIN` pin ties straight to the USB rail, so a live mains supply back-feeds into your laptop's USB port.

All emulator testing belongs in the USB-only phase, before the AC side is energized. The Uno itself is unaffected — it's a separate board on its own USB cable — but the *detector* it's aimed at is not.

## 8. Deviations from PWFusion's sketch

This driver is PWFusion's `SEN-39002_Lightning_Emulator.ino` with a short, deliberate list of changes. **The emulation itself — decay profile, 1/2/3-pass distance encoding, 30 µs step delay, 1 s pacing — is untouched.**

| # | Change | Why |
|---|---|---|
| 1 | **Serial labels fixed** | Upstream, only `case 3` printed anything, and it printed `"Far Strike"` while firing a **close** strike and lighting the **close** LED. All three cases now print, correctly labelled. |
| 2 | **Serial control added** | Single keypresses `f`/`m`/`c`/`a`/`?`. Lets you fire strikes with both hands on the coil. Pushbuttons still work identically. |
| 3 | **Blocking button wait removed** | Upstream spun in `while(digitalRead(5) & digitalRead(7) & digitalRead(9));`, leaving no room to poll serial. `loop()` is now non-blocking. |
| 4 | **DAC presence probe at boot** | An unseated shield otherwise looks exactly like a dead detector. |
| 5 | **`Serial.flush()` before each burst** | Serial is interrupt-driven; a TX interrupt mid-burst would jitter the I²C step timing the emulation depends on. Costs ~2 ms, buys an uninterrupted burst. |
| 6 | **`setOutput(0, true, true)` → `(0, false, true)`** | Behaviorally identical — the library `return`s on `powerDown` before it ever reads `writeNVmem` — but upstream's `true` reads as "write EEPROM on every strike", which it is not. |
| 7 | **`Wire.setClock(100000)` stated explicitly** | It's already the AVR default, but it's part of the calibration (§10), so it shouldn't be left implicit where someone might "optimize" it. |
| 8 | **Named constants for shield pins and pass counts** | Upstream used bare `4`/`5`/`6`/`7`/`8`/`9` literals. |

## 9. Why a separate board

Driving the emulator from the same ESP32 running the detector is a bad idea for three independent reasons:

1. **Pin conflicts.** The detector uses GPIO4 (IRQ) and GPIO5 (CS) — exactly the numbers the shield wants for `D4`/`D5`.
2. **Timing.** ESPHome's `loop()` plus WiFi would jitter the DAC output timing.
3. **Methodology.** The stimulus should not share a failure domain with the thing being measured. If both go quiet, you want to know which one broke.

The Uno makes this trivially easy — it's a physically separate board on its own USB cable, and the shield is the only thing attached to it.

## 10. Known quirks

### The I²C clock is part of the calibration

`src/main.cpp` pins the bus at **100 kHz**, and this is not boilerplate.

Each DAC write is a 4-byte I²C transfer — roughly **400 µs at 100 kHz** — and there are **two per step**. So the real step period is ~**800 µs**, and PWFusion's `delayMicroseconds(30)` accounts for only about **4%** of it. The bus clock, not the delay, sets the edge spacing that excites the coil.

PWFusion calibrated their profile on an Uno at the default 100 kHz. **Raising it to 400 kHz would compress the waveform** into something the AS3935 may not classify as lightning. Their sketch comment about changing "drive every 30 microseconds" is misleading.

### Conflicting range figures

Three different numbers are published for coil-to-antenna spacing:

| Source | Range |
|---|---|
| PWFusion user guide | 4–10 cm |
| PWFusion sketch comment | 7–15 cm |
| Parent project README | 5–15 cm |

Start at **~7 cm** and adjust from there.

## 11. Files

| Path | Purpose |
|---|---|
| `platformio.ini` | Build config — `env:uno`, atmelavr/arduino, pinned MCP4725 library |
| `src/main.cpp` | The complete driver |
| `.gitignore` | Excludes `.pio/` and `.vscode/` |

## 12. Credits and references

Derived from Playing With Fusion's MIT-licensed emulator sketch and MCP4725 library, both used essentially as published. The decay envelope, the 1/2/3-pass distance encoding, and the LED sweep are theirs; the serial control, DAC probe, non-blocking loop, and the corrections in §8 are this project's.

- [PWFusion_Lightning_Emulator](https://github.com/PlayingWithFusion/PWFusion_Lightning_Emulator) — original sketch and user guide PDF
- [PWFusion_MCP4725](https://github.com/PlayingWithFusion/PWFusion_MCP4725) — DAC library (required; pinned in `platformio.ini`)
- [SEN-39002 product page](https://www.playingwithfusion.com/productview.php?pdid=55)
- [AS3935 Lightning Sensor Quick Start Guide](https://www.playingwithfusion.com/docs/1221)
- [Parent project README](../README.md)
