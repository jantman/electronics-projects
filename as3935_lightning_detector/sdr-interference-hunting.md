# Hunting the 500 kHz interference source with an SDR

*Companion to the main [README](README.md). Written 2026-08-22.*

This document exists so that **if** the noise-floor problem survives the hardware rebuild, you can order parts and start work without re-deriving any of this. It covers what to buy, what not to buy, how to build the one part that actually matters, and how to run the hunt.

---

## 0. Read this before spending anything

**Do the protoboard rebuild first, then re-measure.** Everything we know about the noise floor (README §11.5) was measured on a solderless breadboard that README §11.3 disqualified as a measurement platform — its interference floor moved by two thirds when somebody touched it. The bimodal noise pattern may be an artefact of that platform and may simply vanish. Buying instruments to chase an artefact is a bad trade.

**Then try the free option.** The AS3935's antenna *is* a tuned 500 kHz loop with sharp nulls — you already own a direction finder for exactly this frequency. The README §15 Phase 3 rotation test costs nothing and may localise the source without any of this. It only becomes valid once the sensor is in its own enclosure on a cable (§16), because on the breadboard the sensor and the ESP32 rotate together.

**Reach for the SDR when:** the noise floor survives the rebuild, *and* rotation either shows no clear null or shows one you cannot explain. The SDR answers a question rotation cannot — *what* the signal actually is.

---

## 1. What we are hunting

From README §11.5, measured over 168 five-minute buckets:

| Property | Observation |
|---|---|
| **Bimodal** | Quiet cluster ~250–350 counts/bucket, loud mass ~900–1500, sparse valley between. A discrete source switching, not an ambient level drifting. |
| **Irregular** | 10–90 minute runs in each state, ~60/40 loud/quiet. No periodicity, no diurnal trend. |
| **Invisible to house power** | No correlation across 62 per-circuit power series; largest deltas are ~5% wobbles on multi-kW rollups. |
| **Not thermal** | Node temperature flat between states (55.2 °C vs 54.6 °C, ranges overlapping). |
| **Not mains-conducted** | A battery-powered hour barely moved it. |
| **Not present at the bench** | The indoor bench logged essentially zero noise interrupts. |

⚠️ **The limit of the "invisible to house power" result:** whole-house metering only excludes *large* loads. A 5 W device switching on and off is undetectable against a 5 kW aggregate — a PoE-powered device drawing through a switch is the obvious case. It means "not a big load", **not** "not in the house."

`INT_NH` matters more than the disturber rate it is often confused with: it is *continuous*, and while the noise floor sits above the threshold the AFE is effectively deaf.

---

## 2. What to buy

### The receiver — RTL-SDR Blog V4

**Get the V4. Not the V3, and not a "V5".**

There is no official RTL-SDR Blog V5 — listings using that name are mislabelled V4s or third-party units. The genuine "v5" is Nooelec's NESDR SMArt v5, a different product.

**Why the V4 over direct-sampling designs**, from the [V4 datasheet](https://www.rtl-sdr.com/wp-content/uploads/2024/12/RTLSDR_V4_Datasheet_V_1_0.pdf):

> Now uses a built in upconverter instead of using a direct sampling circuit... improved sensitivity, and adjustable gain on HF. **Like the V3, the lower tuning range remains at 500 kHz**

That last clause is the one that settles the "but the Nooelec says 100 kHz" question. RTL-SDR Blog quote 500 kHz for **both** their direct-sampling V3 *and* their upconverter V4 — so the difference between a vendor claiming 100 kHz and one claiming 500 kHz is mostly how conservatively each specs the same underlying limit, not a difference in what the hardware hears.

Meanwhile the V4 measurably improves what matters:

- **Better sensitivity on HF.** The datasheet reports MDS "significantly improved on the HF bands thanks to the upconverter design."
- **Adjustable gain on HF.** Direct sampling bypasses the tuner entirely, so you get no gain control at all.
- **Front-end filtering.** The R828D's triplexed input isolates HF from VHF/UHF, improving out-of-band isolation by 28–43 dB. That matters when hunting next to the AM broadcast band.

And you do not need coverage below 500 kHz: the AS3935's antenna is a *resonant* loop tuned to 500 kHz, so a source at 200 kHz couples into it poorly and is not your problem.

**Two caveats:**

- **The V4 needs RTL-SDR Blog's driver fork.** Stock libusb/Zadig drivers will not give you proper gain control. On Arch this is the `rtl-sdr-blog` AUR package — install it *instead of* the stock `rtl-sdr`, since they conflict.
- **The V4 includes a broadcast-AM notch filter** ("only attenuate by a few dB"). The AM band starts at 530 kHz and your target is 500 kHz, so it sits just below — but know it exists if you see unexpected attenuation.

**Buy the bare dongle if you can.** See below for why the bundled antenna is not useful here.

### The antenna — the part that actually decides this

**Do not buy an antenna bundle expecting it to help.** Those kits ship telescopic dipoles designed for VHF/UHF. At 500 kHz the wavelength is **600 metres**, so a 1 m whip is electrically tiny, couples poorly, and — fatally for this job — is **not directional**.

Directional at LF/MW means one thing: **a loop**. Options, best first:

1. **Wind your own tuned loop.** Cheapest, tuned exactly on frequency, sharpest nulls. Section 3 below.
2. **A ferrite loopstick.** Same principle, far smaller, still sharply directional. Good if you want something pocketable to walk around with.
3. **A commercial MW loop** (e.g. Tecsun AN-200). Convenient, but they typically tune from ~530 kHz upward — just *above* your target.

### Shopping list

| Item | Notes |
|---|---|
| RTL-SDR Blog V4 | Bare dongle preferred over an antenna bundle |
| Enamelled magnet wire, ~26–22 AWG, 30 m | For the loop. Any gauge in range works. |
| Variable capacitor, ~365 pF (AM broadcast type) | **The critical part** — it absorbs all the design error. Salvageable from any old AM radio. |
| Wooden or plastic cross-frame, 30–40 cm | Non-metallic. Scrap plywood is fine. |
| Small length of coax + SMA connector | To feed the SDR from the coupling loop |

---

## 3. Building the loop

### How a loop finds direction

A small loop responds to the magnetic field threading it, which gives it a figure-8 pattern:

- **Maximum** when the loop is *edge-on* to the source — the source lies in the plane of the loop.
- **Null** when the loop *faces* the source — the source lies along the loop's axis, perpendicular to its plane.

This is the same effect as rotating an AM radio and hearing a station fade: the internal ferrite rod is the coil's axis, and the station disappears when the rod points at it.

**Use the null, not the peak.** The null is far sharper and therefore far more precise.

⚠️ **A null gives you a bearing *line*, not a direction** — the source could be at either end of it. Resolve the 180° ambiguity by taking bearings from two well-separated positions and seeing where they cross.

### Dimensioning it

Resonance is `f = 1 / (2π√(LC))`. For 500 kHz with a 365 pF variable capacitor at mid-scale you want roughly:

```
L = 1 / ((2πf)² C) = 1 / ((2π × 500e3)² × 365e-12) ≈ 278 µH
```

A square loop of 30–40 cm per side with **25–40 turns** lands in that region. **You do not need to hit it precisely** — that is the entire reason for the variable capacitor. Wind something in the right neighbourhood, then tune for peak signal at 500 kHz.

### Feeding the SDR

Do not connect the coax directly across the tuned winding — that loads it and destroys the Q you are relying on for selectivity. Use **link coupling**:

- Wind the main loop (25–40 turns) and connect the variable capacitor across its ends. This is the tuned circuit.
- Wind a separate **1–3 turn pickup loop** alongside it, at the base.
- Feed the coax from the pickup loop to the SDR's SMA.

The pickup loop transforms impedance and keeps the tuned circuit lightly loaded.

### Confirming it works

Point it at a known AM broadcast station first. If you can peak and null a station you can hear on a normal radio, the loop and the tuning both work. Only then trust what it tells you at 500 kHz.

---

## 4. Software setup

Arch, roughly:

```bash
# The V4 needs the RTL-SDR Blog driver fork -- it CONFLICTS with stock rtl-sdr
yay -S rtl-sdr-blog

# The kernel DVB driver grabs the dongle; block it
echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/blacklist-rtl.conf
sudo modprobe -r dvb_usb_rtl28xxu

rtl_test -t          # confirm the dongle enumerates
```

For interactive work, **SDR++** or **GQRX** — either gives you a waterfall to look at 500 kHz directly.

---

## 5. Method

### 5.1 Look first

Tune to 500 kHz with a waterfall and a span of a few hundred kHz. You are asking one question: **is there anything there, and does it come and go?**

Distinguish:

- **A discrete carrier** (a narrow vertical line) — a transmitter. NDBs occupy 190–535 kHz and AM broadcast starts at 530 kHz, so a carrier near 500 kHz is plausible and would be *continuous*, not switching.
- **Broadband hash** that appears and disappears — much more consistent with §11.5's bimodal pattern, and more likely a switching supply or motor.

The bimodality is the strongest clue you have. Whatever you find should **toggle**, in runs of tens of minutes.

### 5.2 Correlate before you chase

This is the step that turns a suspicion into a fact, and it is worth the wait.

`rtl_power` logs band power to CSV over time:

```bash
rtl_power -f 450k:550k:1k -i 60 -e 12h -g 40 sdr-500khz.csv
```

Run it beside the sensor for several hours **while `tools/ambient-survey.py` is also running**. Then correlate the SDR's 500 kHz band power against the survey's per-bucket noise counts.

**If they track each other, you have found the signal responsible** and can start direction-finding it. If they do not, the noise floor is being driven by something the SDR cannot see there, and you should stop and rethink rather than wander the house.

The bucket-parsing approach used for README §11.5 is a worked example of this correlation — the survey prints a `t+N.Nm  L.. D.. N..` timeline that is straightforward to align against timestamped CSV.

### 5.3 Then direction-find

1. Rotate the loop for a **null** and note the bearing.
2. Move to a well-separated second position and repeat.
3. Where the two bearing lines cross is your source. If they cross outside the house, stop looking indoors.

Nulls sharpen as you get closer. If the bearing swings wildly over a short distance, you are close.

### 5.4 Keep your own instrument out of the measurement

The laptop and its charger are themselves excellent 500 kHz noise sources (README §10.1 ranks them highly). Run the laptop on battery, keep it as far from the loop as the USB cable allows, and re-check any promising bearing with the laptop moved — a "source" that follows you around the house is your own kit.

---

## 6. What a result looks like

- **Best case:** a toggling signal at 500 kHz that correlates with the survey's loud/quiet buckets, with a bearing that triangulates to a specific device. Unplug it and confirm the noise floor drops — then confirm again by plugging it back in. **Run the A′ control.** README §11.3 is a standing reminder of what happens when you skip it.
- **Also a result:** the SDR sees nothing at 500 kHz that correlates. That points back at the build itself rather than the environment, and is worth knowing.
- **Also a result:** bearings that triangulate off-property. Then it is a neighbour's device or a broadcast source, neither of which you can fix — and the answer becomes shielding, relocation, or accepting a higher `noise_level` setting.
