# SEN-39002 Lightning Emulator — ESP32 Driver

*Bench-test driver for the Playing With Fusion SEN-39002 "lightning emulator" shield, wired to an ESP32 instead of stacked on an Arduino Uno.*

Part of the [AS3935 lightning detector project](../README.md). This is a **standalone PlatformIO project** that runs on a **second, separate ESP32** — not the one running ESPHome. Keeping the stimulus independent of the device under test is deliberate; see [§9 Why a separate ESP32](#9-why-a-separate-esp32).

---

## 1. Purpose

Exercise the full detection path — AS3935 → SPI/IRQ → ESP32 → ESPHome → Home Assistant — on the bench, on demand, without waiting for a thunderstorm. Type a key, get a strike, watch it land in HA.

## 2. What you need

| Item | Notes |
|---|---|
| Playing With Fusion **SEN-39002** | The emulator shield. Headers must be soldered on (breakaway strip included in the package). |
| An **ESP32 dev board** | Any; `esp32dev` / DevKit V1 assumed. Separate from the detector's ESP32. |
| Breadboard + 5 jumpers | 8 if you want the physical pushbuttons. |
| USB cable | Power and serial for the emulator ESP32. |
| The assembled AS3935 detector | Running the ESPHome config from the parent project. |

No Arduino Uno required, and **no Arduino libraries to install** — the DAC operations are inlined in `src/main.cpp`.

## 3. How the shield actually works

Worth understanding, because it explains every design choice below.

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

## 4. Wiring

### 4.1 Minimum — 5 wires

| ESP32 | SEN-39002 | Purpose |
|---|---|---|
| GPIO21 | `SDA` | I²C data |
| GPIO22 | `SCL` | I²C clock |
| `3V3` | `3.3V` | Board power |
| `3V3` | **`5V`** | Board power — **3.3 V into the 5 V pin, on purpose** |
| `GND` | `GND` | |

### 4.2 Optional pushbuttons — 3 more wires

Only if you want physical buttons instead of keyboard control. Set `USE_BUTTONS` to `1` in `src/main.cpp`.

| ESP32 | SEN-39002 | Button |
|---|---|---|
| GPIO13 | `D9` | Far |
| GPIO14 | `D7` | Mid |
| GPIO27 | `D5` | Close |

Those GPIOs are chosen to avoid the SPI flash pins (6–11), the strapping pins (0/2/12/15), and the input-only 34–39 range that has **no internal pullup** (the buttons rely on `INPUT_PULLUP`).

### 4.3 Do not wire the LEDs

The shield's LEDs are on `D8`/`D6`/`D4`. Taken as GPIO *numbers* on an ESP32, `D8`/`D6` land inside **GPIO 6–11, which is wired to the SPI flash** — driving those will break the boot. The LEDs are purely cosmetic; the serial output tells you what fired. Leave them unconnected.

## 5. Why everything runs at 3.3 V

**Both** shield power pins — including the one silkscreened `5V` — are fed from the ESP32's 3.3 V rail. This is intentional.

PWFusion's user guide lists *"Power: 5.0V, 3.3V, and all GND pins"* as the shield pins used on an Uno, but **publishes no schematic**, so the internal split between those two rails is unknowable. Their sketch header, however, states:

> `VDD should match voltage of IO, and can be between 3.3 and 5V`

Running the whole board at 3.3 V satisfies that (VDD == IO == 3.3 V) and removes the I²C logic-level hazard entirely:

> A 5 V-powered MCP4725 wants **V<sub>IH</sub> = 0.7 × VDD = 3.5 V**. A 3.3 V ESP32 cannot guarantee that. Mixing a 5 V shield rail with 3.3 V ESP32 I²C is the one configuration here that produces flaky, hard-to-diagnose behavior. **Don't do it without a level shifter.**

### Compensating for the weaker rail — in software

A 3.3 V rail means the same DAC code produces proportionally less output voltage. Rather than mixing voltage domains, that is corrected with `amplitude_scale`:

```cpp
static float amplitude_scale = 1.5f;   // ~= 5.0 / 3.3
```

There is enormous headroom — PWFusion's peak code is **103 out of 4095**, about 2.5% of full scale — so this cannot clip. Trim it live with `+` / `-` if your range isn't cooperating.

## 6. Build and flash

```bash
cd sen39002-emulator-esp32

pio run                        # compile
pio run -t upload              # compile + flash
pio device monitor             # serial console @ 115200
pio run -t upload -t monitor   # all three
```

If you have several boards attached, uncomment `upload_port` / `monitor_port` in `platformio.ini`, or run `pio device list` to see what's present.

**Verified:** clean build on PlatformIO Core 6.1.19, no warnings under `-Wall -Wextra`. RAM 6.2%, flash 25.0%.

### `platformio.ini` choices that are load-bearing

- **`lib_deps` is empty.** The two MCP4725 operations are inlined, so `PWFusion_MCP4725` is not a dependency.
- **`monitor_filters` deliberately omits `send_on_enter`.** Commands are single characters; the monitor's default immediate-keystroke behavior is what they expect. Adding that filter would force you to press Enter after every strike.

## 7. Using it

Open the serial monitor at 115200. Every command works as a single keypress — no Enter.

| Key | Action |
|---|---|
| `f` | Far strike (1 pass) |
| `m` | Mid strike (2 passes) |
| `c` | Close strike (3 passes) |
| `a` | Auto sequence: far, mid, close, then 3× close |
| `+` | Amplitude × 1.25 |
| `-` | Amplitude ÷ 1.25 |
| `?` | Help |

### Startup check — read this before blaming the sensor

On boot the driver probes both DAC addresses:

```
DAC 0x62: OK
DAC 0x64: OK
```

**If either reports `NOT RESPONDING`, stop.** That is emulator wiring or power — not a detector problem. Chasing a silent AS3935 when the emulator never fired is the single easiest way to waste an afternoon.

### Suggested bench procedure

1. Bring up the detector per the parent project's **[§12 bring-up order](../README.md)**, on **USB only**.
2. Verify the AS3935 tuning capacitance over serial — parent **§12.1**. Do this first; a mistuned antenna makes everything downstream meaningless.
3. Flash and start this emulator on its **second** ESP32.
4. Confirm both DACs report `OK`.
5. Position the emulator coil **~7 cm** from the AS3935's antenna. Keep phones and laptops ~30 cm away.
6. Press `f`, then `m`, then `c`. Watch the ESPHome log for `Lightning has been detected!` and check that **Lightning Distance** falls as you go far → close.
7. Press `a` and confirm Home Assistant renders the burst — this is the end-to-end path test.

### What to expect in Home Assistant

| Entity | Behavior |
|---|---|
| **Storm Alert** (binary sensor) | Pulses `on` for ~10 ms per strike |
| **Lightning Distance** | Updates per strike; should decrease far → mid → close |
| **Lightning Energy** | Updates per strike; relative magnitude only, not physical units |

Distances will **not** be 1:1 with the labels. The emulator is a coarse energy stimulus, not a calibrated distance source. What matters is that the three settings produce *distinguishable, ordered* readings.

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `DAC 0x62/0x64: NOT RESPONDING` | Wiring or power. Check SDA/SCL aren't swapped, and that **both** shield power pins are fed. |
| Nothing detected, DACs OK | Move closer (try 3–5 cm) and raise amplitude with `+`. |
| Still nothing at close range | Verify the AS3935 tuning capacitance first (parent §12.1). Then check `indoor: true` is set for bench testing. |
| Constant disturbers, no strikes | Expected indoors. Move away from noise sources; raise `noise_level` / `watchdog_threshold` / `spike_rejection`. Keep `mask_disturber: false` while testing so you can *see* them. |
| Detected, but distance never changes | Amplitude may be saturating the sensor. Lower it with `-` or back the coil off a few cm. |
| Strikes detected far more often than 1/sec | Not possible from this driver — it paces at 1/sec. Suspect real environmental noise. |

### ⚠️ Safety

The parent project's **one safety rule** applies whenever the detector is on USB:

> **Never have USB and the IRM-02-5 mains supply powered at the same time.** On most ESP32 dev boards the `5V`/`VIN` pin ties straight to the USB rail, so a live mains supply back-feeds into your laptop's USB port.

All emulator testing belongs in the USB-only phase, before the AC side is energized.

## 9. Why a separate ESP32

Driving the emulator from the same ESP32 running the detector is a bad idea for four independent reasons:

1. **Pin conflicts.** The detector uses GPIO4 (IRQ) and GPIO5 (CS) — exactly the numbers the shield wants for `D4`/`D5`.
2. **Flash pins.** `D6`–`D9` map onto GPIO 6–11.
3. **Timing.** ESPHome's `loop()` plus WiFi would jitter the DAC output timing.
4. **Methodology.** The stimulus should not share a failure domain with the thing being measured. If both go quiet, you want to know which one broke.

## 10. Known quirks

### The I²C clock is part of the calibration

`platformio.ini` and the driver pin the bus at **100 kHz**, and this is not boilerplate.

Each DAC write is a 4-byte I²C transfer — roughly **400 µs at 100 kHz** — and there are **two per step**. So the real step period is ~**800 µs**, and PWFusion's `delayMicroseconds(30)` accounts for only about **4%** of it. The bus clock, not the delay, sets the edge spacing that excites the coil.

PWFusion calibrated their profile on an Uno at the default 100 kHz. **Raising it to 400 kHz would compress the waveform** into something the AS3935 may not classify as lightning. Their sketch comment about changing "drive every 30 microseconds" is misleading.

### Upstream bug in PWFusion's sketch

Their original `SEN-39002_Lightning_Emulator.ino` mislabels its serial output:

```cpp
case 3:
  digitalWrite(4, LOW);          // pin 4 = CLOSE LED
  Serial.println("Far Strike");  // ...but prints "Far Strike"
```

`close = 3`, so case 3 is a **close** strike lighting the **close** LED while printing "Far Strike" — and it's the only case that prints anything. **This driver does not have that bug**; it labels all three correctly. Noted in case you cross-reference the original.

### Conflicting range figures

Three different numbers are published for coil-to-antenna spacing:

| Source | Range |
|---|---|
| PWFusion user guide | 4–10 cm |
| PWFusion sketch comment | 7–15 cm |
| Parent project README | 5–15 cm |

Start at **~7 cm** and adjust. With `amplitude_scale` available at runtime, exact spacing matters less than it does with the stock sketch.

### Arch Linux: PEP 668 pip noise

On Arch, every `espressif32` build prints:

```
Installing Arduino Python dependencies
error: externally-managed-environment
```

**This is cosmetic and the build is unaffected.** The platform wants `wheel`, `PyYAML`, and `intelhex`; the first two are typically already present, and `intelhex` produces Intel HEX output that the ESP32 flash path never uses — `upload_protocol = esptool` runs `esptool.py` against the `.bin`. The firmware builds and flashes correctly regardless.

## 11. Files

| Path | Purpose |
|---|---|
| `platformio.ini` | Build config — `env:esp32dev`, espressif32/arduino |
| `src/main.cpp` | The complete driver; no external libraries |
| `.gitignore` | Excludes `.pio/` and `.vscode/` |

## 12. Credits and references

Derived from Playing With Fusion's MIT-licensed emulator sketch. The decay envelope and the 1/2/3-pass distance encoding are theirs; the ESP32 port, serial control, amplitude scaling, DAC probe, and inlined I²C are this project's.

- [PWFusion_Lightning_Emulator](https://github.com/PlayingWithFusion/PWFusion_Lightning_Emulator) — original sketch and user guide PDF
- [PWFusion_MCP4725](https://github.com/PlayingWithFusion/PWFusion_MCP4725) — DAC library (not required here)
- [SEN-39002 product page](https://www.playingwithfusion.com/productview.php?pdid=55)
- [AS3935 Lightning Sensor Quick Start Guide](https://www.playingwithfusion.com/docs/1221)
- [Parent project README](../README.md)
