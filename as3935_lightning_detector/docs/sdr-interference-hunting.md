# Hunting the 500 kHz interference source with an SDR

*Companion to the [project notebook](project-notebook.md); § references below are to it. Written 2026-08-22;
§2 and §4 revised 2026-10-10 for the RTL-SDR Blog V4's end of production and for the attic's
scheduled source (§11.11, [`attic-interference-hunt.md`](attic-interference-hunt.md)).*

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

### The receiver

> ⚠️ **Revised 2026-10-10. The RTL-SDR Blog V4 recommended here originally is end-of-line.**
> Its Rafael R828D tuner is out of production and, per RTL-SDR Blog, the last R828D chips
> they could obtain were all faulty in some way, so the V4 ended well before its expected end
> of 2026 ([announcement](https://www.rtl-sdr.com/rtl-sdr-blog-v4-end-of-line/),
> [Hackster](https://www.hackster.io/news/rtl-sdr-com-announces-the-end-of-the-line-for-its-popular-rtl-sdr-blog-v4-software-defined-radio-76f628f18e0d)).
> RTL-SDR Blog also warns that **most fake "Blog V4" listings put a V3-clone board inside a copied
> V4 case**. Treat a marketplace V4 at an odd price or lead time (seen on Amazon in Oct 2026: $80
> with 2-week shipping, $150 with a month) as suspect. Buy from the official store or its listed
> resellers, or not at all.

What is actually available, October 2026:

| Receiver | Price | How it reaches 500 kHz | Notes |
|---|---|---|---|
| **RTL-SDR Blog V3** | ~$38, next-day on Amazon | Direct sampling (Q-branch) | **In stable production**, per RTL-SDR Blog. No gain control on HF, and aliasing above ~14.4 MHz. Use the `rtl-sdr-blog` driver fork, which switches to the Q branch automatically below 24 MHz; stock drivers don't, so stock `rtl_power` can't use it on HF (§4). |
| **RTL-SDR Blog V4L ("Lite")** | $37.95, [official store](https://www.rtl-sdr.com/product/rtl-sdr-blog-v4l-lite-r828s-rtl2832u-1ppm-tcxo-sma-software-defined-radio-dongle-only/) | Built-in HF upconverter, as on the V4 | Successor built on the R828S tuner. Keeps the V4's adjustable HF gain and avoids aliasing, but its input is **diplexed, not triplexed**, so it filters strong out-of-band signals less well. Also "limited edition". **Needs librtlsdr ≥ 2.0.3** (V4L support landed upstream 2026-08-11): Arch's stock `rtl-sdr` 2.0.3 has it, **Debian trixie's 2.0.2 does not**. |
| Nooelec NESDR SMArt v5 | ~$55 bundle | Direct sampling | Reportedly the best direct-sampling RTL; its bundled antennas are no use here. No reason to prefer it over a V3. |
| Airspy HF+ Discovery | ~$169–227 | Native HF | Far better HF dynamic range and noise floor. It is the step up **only** if an RTL dongle overloads next to the source. Overkill otherwise. |

**For the attic hunt, buy the V3, and buy it now.** That source (§11.11) is a switching event close to the sensor, strong enough to trip it, so receiver sensitivity is not the constraint the original V4 reasoning assumed. It arrives tomorrow, rather than whenever the official store's V4L ships. It is in stable production, and its HF limits (no gain control, aliasing) only bite if it overloads. Either dongle needs the `rtl-sdr-blog` driver fork for unattended `rtl_power` logging (§4), so the driver does not decide between them. The V4L is the better HF receiver for the same money; get one later if the V3 actually overloads.

If the V3 does overload (a waterfall that whitens across the band during a burst, or AM stations everywhere), try these in order:
1. turn the loop to null the strongest station;
2. toggle RTL AGC;
3. fit an inline SMA attenuator (10–20 dB);
4. only then move to a V4L or an Airspy.

**The original V4 reasoning, kept for the record:** the V4's upconverter gave better HF sensitivity, adjustable HF gain and triplexed front-end filtering, and RTL-SDR Blog quoted 500 kHz as the lower limit for both the V3 and the V4. Those points still describe the V4L, minus the triplexer. They still matter for a weak, continuous source like the §11.5 noise floor, if it ever returns.

### The antenna — the part that actually decides this

**Do not buy an antenna bundle expecting it to help.** Those kits ship telescopic dipoles designed for VHF/UHF. At 500 kHz the wavelength is **600 metres**, so a 1 m whip is electrically tiny, couples poorly, and — fatally for this job — is **not directional**.

Directional at LF/MW means one thing: **a loop**.

**Which loop depends on what you are hunting.** The original ranking below was for the §11.5
noise floor, a weak, continuous signal where selectivity *at* 500 kHz was the point. The attic's
scheduled source (§11.11) is a **switching transient**: relay or SMPS edges are broadband,
spraying energy from hundreds of kHz to MHz. It does not have to be heard *at* 500 kHz. Any
quiet stretch of 0.5–2 MHz shows the same clicks at the same seconds, so an untuned, pre-made
loop is fine for it, and it is here in days rather than after an evening of winding.

For the attic source, best first:

1. **MLA-30+ active loop** (~$30–60). A cheap receive-only magnetic loop rated 500 kHz–30 MHz.
   Reviews note its thin loop gives an unusually deep null, which is what direction-finding
   uses ([review](https://www.electronics-notes.com/store-shop/ham-radio-reviews/mla-30plus-hf-loop-antenna-review.php),
   [roundup](https://www.rtl-sdr.com/reviews-of-the-low-cost-mla-30-wide-band-hf-magnetic-loop-antenna/)).
   It is weak on low-SNR signals, which does not matter here. Its amplifier is the overload
   risk, so it pairs with the V3 overload steps above. Check its output connector and get the
   adapter to SMA.
2. **A pocket AM radio** (~$15–25), between stations at the bottom of the AM band. Its ferrite rod
   is a sharp direction-finder, nulling when the rod points at the source. No laptop needed, so
   it is the fastest first look at a 20:10 burst.
3. **A near-field (H-field) probe set** (~$30), for the last few feet once a bearing points at a
   cabinet or wall.

Not recommended for this: the YouLoop (~$40, passive and untuned; it wants a low-MDS receiver,
and reviews call its MW reception on RTL dongles moderate), or anything bundled with the dongle.

For a weak, continuous source like the §11.5 noise floor, the original ranking still holds:

1. **Wind your own tuned loop.** Cheapest, tuned exactly on frequency, sharpest nulls. Section 3 below.
2. **A ferrite loopstick.** Same principle, far smaller, still sharply directional. Good if you want something pocketable to walk around with.
3. **A commercial MW loop** (e.g. Tecsun AN-200). Convenient, but they typically tune from ~530 kHz upward — just *above* your target.

### Shopping list

**For the attic source (revised 2026-10-10):**

| Item | Notes |
|---|---|
| RTL-SDR Blog V3 | Bare dongle, from RTL-SDR Blog or a listed reseller. See the receiver table above for why not a V4 |
| MLA-30+ active loop | Plus whatever adapter its output needs to reach SMA |
| Inline SMA attenuator, 10–20 dB | Only if the V3 overloads |
| Pocket AM radio | Optional, and the quickest first look |
| USB extension cable, 2–3 m | Keeps the dongle and loop away from the computer |

**For the original tuned-loop build (the §11.5 noise floor):**

| Item | Notes |
|---|---|
| RTL-SDR dongle | A V3 works. A V4L is better on HF, and so was the now-unavailable V4 |
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
# RTL-SDR Blog's driver fork -- it CONFLICTS with stock rtl-sdr. Still the right choice for a
# V3 (see below), and it knows the V4L too.
yay -S rtl-sdr-blog

# The kernel DVB driver grabs the dongle; block it
echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/blacklist-rtl.conf
sudo modprobe -r dvb_usb_rtl28xxu

rtl_test -t          # confirm the dongle enumerates
```

**Why the fork, for a V3: HF is direct sampling on the Q branch, and only the fork switches to it
by itself.** Checked against source, 2026-10-10:

- **`rtl-sdr-blog`** (the fork) enables Q-branch direct sampling automatically whenever a V3 is
  tuned below 24 MHz, so `rtl_power -f 450k:550k:1k ...` simply works.
- **Stock osmocom `rtl-sdr` 2.0.3** (Arch `extra`) never switches on its own. Worse, its
  `rtl_power -D` and `rtl_sdr -D` select direct-sampling mode **1, the I branch**, which on a V3
  hears nothing. Only `rtl_fm -E direct2` reaches Q. With stock drivers, `rtl_power` cannot use
  a V3 on HF at all.
- **SDR++ and GQRX** can set Q-branch direct sampling themselves (SDR++: the RTL-SDR source's
  direct-sampling option, Q; GQRX: device string `rtl=0,direct_samp=2`), so for interactive
  work either driver will do.

A **V4L** needs no direct sampling (it has an upconverter), but does need V4L support: the fork,
or stock librtlsdr ≥ 2.0.3 (upstream added it 2026-08-11). Stock 2.0.2 does not have it.

**On a Raspberry Pi (Debian trixie):** `apt install rtl-sdr` gives stock 2.0.2, which has neither
the V3's automatic Q-branch nor the V4L. For unattended `rtl_power` logging, build `rtl-sdr-blog`
from source (`cmake` / `make` / `make install`, per its README) and blacklist
`dvb_usb_rtl28xxu` as above.

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
