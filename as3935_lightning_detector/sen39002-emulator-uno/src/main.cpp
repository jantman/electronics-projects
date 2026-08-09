/***************************************************************************
 * SEN-39002 Lightning Emulator driver -- Arduino Uno R3
 *
 * Bench-test driver for the Playing With Fusion SEN-39002 "lightning
 * emulator" shield, used to exercise an AS3935 detector on demand instead
 * of waiting for a thunderstorm.
 *
 * Derived from PWFusion's SEN-39002_Lightning_Emulator.ino (MIT), which is
 * the reference implementation for this shield:
 *   https://github.com/PlayingWithFusion/PWFusion_Lightning_Emulator
 *
 * The emulation itself -- the decay profile, the 1/2/3-pass distance
 * encoding, the 30 us step delay, and the 1 s inter-strike pacing -- is
 * PWFusion's and is reproduced here UNCHANGED. See "WHAT WAS CHANGED"
 * below for the complete list of deviations.
 *
 * Build and flash with PlatformIO:
 *   pio run                       # compile
 *   pio run -t upload             # compile + flash
 *   pio device monitor            # serial console, 115200
 *   pio run -t upload -t monitor  # all three
 *
 * ---------------------------------------------------------------------
 * WIRING: none
 * ---------------------------------------------------------------------
 * The SEN-39002 is an Arduino shield. Stack it on the Uno R3 and that is
 * the entire wiring job -- power, I2C (A4/A5), the three pushbuttons and
 * the three LEDs all come through the shield headers. Nothing to jumper,
 * nothing to level-shift: the Uno is a 5 V part and the shield was
 * designed for it.
 *
 * ---------------------------------------------------------------------
 * HOW THE SHIELD WORKS
 * ---------------------------------------------------------------------
 * An MCP4725 12-bit I2C DAC drives the large air-core solenoid on the
 * board. There is no oscillator: the DAC plays a decaying staircase, and
 * each step change kicks the coil. The resulting near-field magnetic
 * transient rings the AS3935's 500 kHz resonant loop antenna -- which is
 * why the useful range is centimeters, not meters.
 *
 * ---------------------------------------------------------------------
 * THE TWO I2C ADDRESSES ARE ONE DAC, NOT TWO
 * ---------------------------------------------------------------------
 * This code writes every value to BOTH 0x62 and 0x64, which reads like two
 * DACs driven in lockstep. It isn't. Those are the two MCP4725 part
 * variants -- 0x62 is an MCP4725A1, 0x64 an MCP4725A2 -- and the shield
 * carries one of them, not both. PWFusion added the second address in
 * their 2024Feb25 revision ("Update to support additional I2C addresses")
 * so one sketch covers either variant, whichever a production run used.
 *
 * An I2C bus scan of this board (0x08-0x77) finds exactly one device, at
 * 0x64. Address 0x62 is absent, so those writes are NAKed and never reach
 * a chip. Expect exactly one of the two to respond; that is healthy.
 *
 * DO NOT "optimize away" the write to the absent address. It is part of
 * the step timing, and therefore part of the calibration:
 *
 *                     A1 board        A2 board (this one)
 *   write 0x62        ACK, ~430 us    NAK, ~183 us
 *   write 0x64        NAK, ~183 us    ACK, ~430 us
 *   + delay             30 us           30 us
 *   step period       ~644 us         ~644 us
 *
 * A NAKed transfer aborts after the address byte instead of sending its
 * three data bytes, so it is cheaper -- but far from free. The arrangement
 * is symmetric, so the same step rate comes out of either variant.
 *
 * Those figures are MEASURED on this board, not derived. Timing the gaps
 * between strike labels over serial for 19/38/57-step bursts gives a step
 * period of 644 us (least-squares slope; the intercept lands at 1122 ms
 * against 1120 ms of coded delays, which validates the model). Rebuilding
 * with the 0x62 write removed drops it to 461 us. So the NAKed write is
 * 183 us, or 28% of every step -- delete it and the whole staircase runs
 * 28% faster than what PWFusion calibrated against.
 *
 * "Distance" is emulated purely by REPETITION COUNT. Far/mid/close are
 * 1/2/3 passes through the identical decay burst; more total energy makes
 * the AS3935 compute a closer strike. Amplitude and frequency are the same
 * for all three.
 *
 * ---------------------------------------------------------------------
 * DAC RESOLUTION: the profile is coarser than it looks
 * ---------------------------------------------------------------------
 * PWFusion's MCP4725 library sends the low data nibble right-justified:
 *
 *   Wire.write((output & 0x0FFF)>>4);  // D11..D4  -- correct
 *   Wire.write(output & 0x000F);       // D3..D0   -- wrong nibble
 *
 * The MCP4725 "Write DAC Register" command wants D3..D0 in the UPPER
 * nibble of that byte; the lower four bits are don't-care. So the bottom
 * 4 bits of every value are discarded and the DAC only ever resolves in
 * steps of 16. What the coil actually sees is:
 *
 *   requested: 103  73  52  37  27  20  15  11  9  7  6  5  4 ...
 *   actual:     96  64  48  32  16  16   0   0  0  0  0  0  0 ...
 *
 * i.e. a six-step kick followed by thirteen steps of silence that still
 * consume their I2C time.
 *
 * This is left ALONE deliberately. PWFusion calibrated the profile and
 * published the 4-10 cm working range against this exact behavior, so the
 * truncation is part of the calibration, not a defect to route around.
 * Correcting the nibble would emit a materially different waveform than
 * the vendor's reference. If you ever do want the untruncated profile,
 * change it here in a fork and re-derive the working range empirically --
 * do not assume PWFusion's distances still apply.
 *
 * ---------------------------------------------------------------------
 * WHAT WAS CHANGED vs. PWFusion's sketch
 * ---------------------------------------------------------------------
 * 1. Serial labels fixed. Upstream, only `case 3` printed anything, and
 *    it printed "Far Strike" while firing a CLOSE strike and lighting the
 *    CLOSE LED. All three cases now print, correctly labelled.
 * 2. Serial control added. Single keypresses f/m/c/a/? drive the shield
 *    from the keyboard, so you can trigger strikes with both hands free
 *    while holding the coil at range. The three pushbuttons still work
 *    exactly as before.
 * 3. Blocking button wait removed. Upstream spun in
 *    `while(digitalRead(5) & digitalRead(7) & digitalRead(9));`, which
 *    left no room to poll the serial port. loop() is now non-blocking.
 * 4. DAC presence probe at boot, so a shield that is not seated reports
 *    itself instead of looking like a dead sensor downstream. It expects
 *    exactly one of the two addresses to answer -- see THE TWO I2C
 *    ADDRESSES above -- and only complains when neither does.
 * 5. Serial.flush() before each burst -- see the comment in emulate().
 * 6. setOutput(0, true, true) -> setOutput(0, false, true) for the
 *    power-down calls. Behaviorally identical (the library returns on
 *    powerDown before it ever examines writeNVmem) but upstream's `true`
 *    reads as "write EEPROM on every strike", which it is not.
 * 7. Named constants for the shield's pins and pass counts.
 *
 * The emulation timing and DAC values are untouched.
 **************************************************************************/

#include <Arduino.h>
#include <Wire.h>
#include <PWFusion_MCP4725_12DAC.h>

// ---- DAC -----------------------------------------------------------------
// Two addresses, ONE chip: the shield carries either an MCP4725A1 (0x62) or
// an MCP4725A2 (0x64). Writing both covers either variant, and the NAK from
// the absent one is part of the step timing -- see the header.
static const uint8_t DAC_ADD = 0x62;      // MCP4725A1 variant
static const uint8_t DAC_ADD_ALT = 0x64;  // MCP4725A2 variant

PWFusion_MCP4725 dac0(DAC_ADD);
PWFusion_MCP4725 dac1(DAC_ADD_ALT);

// ---- Shield pin map ------------------------------------------------------
// Fixed by the shield's PCB -- these are not configurable.
// Pushbuttons are INPUT_PULLUP (pressed = LOW); LEDs are active LOW
// (HIGH = off), which is why every "off" write below is HIGH.
static const uint8_t PIN_PB_CLOSE = 5, PIN_LED_CLOSE = 4;
static const uint8_t PIN_PB_MID = 7, PIN_LED_MID = 6;
static const uint8_t PIN_PB_FAR = 9, PIN_LED_FAR = 8;

// ---- Emulation profile ---------------------------------------------------
// PWFusion's calibrated decay envelope, in raw 12-bit DAC codes. Their
// comment: "as calibrated, this profile works from around 7cm and 15cm from
// inductor to inductor" (the user guide says 4-10 cm; start ~7 cm). Only the
// first 19 entries are used, matching the original sketch. Note that the low
// 4 bits of each value never reach the DAC -- see DAC RESOLUTION above.
static const uint16_t out_array[20] = {103, 73, 52, 37, 27, 20, 15, 11, 9, 7,
                                       6,   5,  4,  4,  4,  3,  3,  3, 3, 3};
static const uint8_t OUT_ARRAY_USED = 19;

// Passes through the decay array. This is what encodes "distance".
static const int PASSES_FAR = 1;
static const int PASSES_MID = 2;
static const int PASSES_CLOSE = 3;

// Set to 1 for PWFusion's unattended soak test instead of interactive use.
#define AUTOMATIC_TEST 0

// ---- Strike emulation ----------------------------------------------------

void emulate(int j_count, int requestedStrikes) {
  for (int a = 0; a < requestedStrikes; a++) {
    switch (j_count) {
      case PASSES_FAR:
        digitalWrite(PIN_LED_FAR, LOW);
        Serial.println(F("-> FAR strike (1 pass)"));
        break;
      case PASSES_MID:
        digitalWrite(PIN_LED_MID, LOW);
        Serial.println(F("-> MID strike (2 passes)"));
        break;
      case PASSES_CLOSE:
        digitalWrite(PIN_LED_CLOSE, LOW);
        Serial.println(F("-> CLOSE strike (3 passes)"));
        break;
      default:
        return;
    }

    // Drain the UART before the burst. Serial is interrupt-driven, and a
    // TX interrupt firing mid-burst would jitter the I2C step timing that
    // the whole emulation depends on. Flushing costs ~2 ms here and buys
    // an uninterrupted burst.
    Serial.flush();

    for (int j = 0; j < j_count; j++) {
      for (uint8_t i = 0; i < OUT_ARRAY_USED; i++) {
        dac0.setOutput(out_array[i], false, false);  // set new command value
        dac1.setOutput(out_array[i], false, false);  // set new command value
        // This delay is NOT what sets the step rate. One of these two calls
        // reaches a real chip (a 4-byte transfer, ~430 us at 100 kHz) and
        // the other NAKs on the absent variant's address (~183 us), so the
        // measured step period is 644 us and this delay is under 5% of it.
        // The bus clock is therefore part of the calibration -- see the
        // Wire.setClock() call in setup().
        delayMicroseconds(30);
      }
    }
    delay(20);

    // Power down both DACs (1k pull-down). writeNVmem is false: the library
    // returns on powerDown before reading it, so this is identical to
    // upstream's `true` without implying an EEPROM write.
    dac0.setOutput(0, false, true);
    dac1.setOutput(0, false, true);

    // The AS3935 resolves roughly one event per second, and deactivates for
    // ~1.5 s after classifying a disturber. Pace accordingly.
    delay(1000);

    digitalWrite(PIN_LED_CLOSE, HIGH);
    digitalWrite(PIN_LED_MID, HIGH);
    digitalWrite(PIN_LED_FAR, HIGH);
    delay(100);
  }
}

// ---- Setup ---------------------------------------------------------------

static void printHelp() {
  Serial.println();
  Serial.println(F("SEN-39002 lightning emulator -- Arduino Uno driver"));
  Serial.println(F("  f  far strike     (1 pass)"));
  Serial.println(F("  m  mid strike     (2 passes)"));
  Serial.println(F("  c  close strike   (3 passes)"));
  Serial.println(F("  a  auto sequence  (far, mid, then 4 close)"));
  Serial.println(F("  ?  this help"));
  Serial.println();
  Serial.println(F("The shield's FAR/MID/CLOSE pushbuttons do the same thing."));
  Serial.println(F("Hold the emulator coil ~7 cm from the AS3935 antenna."));
  Serial.println(F("Keep phones and laptops ~30 cm away."));
  Serial.println();
}

// Probes one candidate address. Returns true if a chip answered. Exactly one
// of the two is expected to answer -- see THE TWO I2C ADDRESSES in the header
// -- so "absent" on a single address is normal, not a fault.
static bool probeDac(uint8_t addr, const __FlashStringHelper *variant) {
  Wire.beginTransmission(addr);
  bool present = (Wire.endTransmission() == 0);
  Serial.print(F("  0x"));
  Serial.print(addr, HEX);
  Serial.print(F(" ("));
  Serial.print(variant);
  Serial.println(present ? F("): present") : F("): absent"));
  return present;
}

void setup() {
  Serial.begin(115200);
  Serial.println(F("Playing With Fusion: SEN-39002, Lightning Emulator Shield"));

  dac0.begin();  // both call Wire.begin()
  dac1.begin();

  // PWFusion calibrated the profile on an Uno at the Wire default of
  // 100 kHz. Because the I2C transaction time dominates the step period
  // (see emulate()), raising this to 400 kHz would compress the waveform
  // into something the AS3935 may not classify as lightning. Stated
  // explicitly rather than left to the default so it does not get "tuned".
  Wire.setClock(100000);

  // DAC output off and pulled low
  dac0.setOutput(0, false, true);
  dac1.setOutput(0, false, true);

  delay(100);  // give the Arduino time to start up

  pinMode(PIN_PB_FAR, INPUT_PULLUP);
  pinMode(PIN_LED_FAR, OUTPUT);
  digitalWrite(PIN_LED_FAR, HIGH);
  pinMode(PIN_PB_MID, INPUT_PULLUP);
  pinMode(PIN_LED_MID, OUTPUT);
  digitalWrite(PIN_LED_MID, HIGH);
  pinMode(PIN_PB_CLOSE, INPUT_PULLUP);
  pinMode(PIN_LED_CLOSE, OUTPUT);
  digitalWrite(PIN_LED_CLOSE, HIGH);

  // Confirm the DAC actually ACKs before trusting any test result. A shield
  // that is not fully seated looks exactly like a detector that is not
  // working, and that mix-up costs an afternoon.
  Serial.println(F("Probing for the shield's MCP4725:"));
  uint8_t found = 0;
  if (probeDac(DAC_ADD, F("MCP4725A1"))) found++;
  if (probeDac(DAC_ADD_ALT, F("MCP4725A2"))) found++;
  if (found == 0) {
    Serial.println(F("  !! NO DAC FOUND -- the shield is not seated."));
    Serial.println(F("  !! Fix this first; nothing downstream will fire."));
  } else {
    Serial.println(F("  DAC found. One variant present is correct."));
  }

  // Startup LED sweep, as upstream: a visible "the shield is alive" signal.
  const uint8_t su_tim = 50;
  for (uint8_t su_cnt = 0; su_cnt < 4; su_cnt++) {
    digitalWrite(PIN_LED_CLOSE, LOW);
    delay(su_tim);
    digitalWrite(PIN_LED_CLOSE, HIGH);
    digitalWrite(PIN_LED_MID, LOW);
    delay(su_tim);
    digitalWrite(PIN_LED_MID, HIGH);
    digitalWrite(PIN_LED_FAR, LOW);
    delay(su_tim);
    digitalWrite(PIN_LED_FAR, HIGH);
    digitalWrite(PIN_LED_MID, LOW);
    delay(su_tim);
    digitalWrite(PIN_LED_MID, HIGH);
  }
  digitalWrite(PIN_LED_CLOSE, LOW);
  delay(su_tim);
  digitalWrite(PIN_LED_CLOSE, HIGH);

  printHelp();
}

// ---- Loop ----------------------------------------------------------------

static void handleKey(int key) {
  switch (key) {
    case 'f': emulate(PASSES_FAR, 1); break;
    case 'm': emulate(PASSES_MID, 1); break;
    case 'c': emulate(PASSES_CLOSE, 1); break;
    case 'a':
      emulate(PASSES_FAR, 1);
      emulate(PASSES_MID, 1);
      emulate(PASSES_CLOSE, 4);
      break;
    case '?': printHelp(); break;
    default: break;  // swallow newlines and stray characters
  }
}

void loop() {
#if AUTOMATIC_TEST
  // emulate(distance, number of strikes) -- modify to customize a soak test
  emulate(PASSES_FAR, 50);
  emulate(PASSES_MID, 50);
  emulate(PASSES_CLOSE, 50);
  emulate(PASSES_FAR, 100);
  delay(10000);
#else
  // Non-blocking, so the pushbuttons and the serial port both stay live.
  // The 1.1 s tail inside emulate() doubles as button debounce.
  if (!digitalRead(PIN_PB_CLOSE)) {
    emulate(PASSES_CLOSE, 1);
  } else if (!digitalRead(PIN_PB_MID)) {
    emulate(PASSES_MID, 1);
  } else if (!digitalRead(PIN_PB_FAR)) {
    emulate(PASSES_FAR, 1);
  } else if (Serial.available()) {
    handleKey(Serial.read());
  }
#endif
}
