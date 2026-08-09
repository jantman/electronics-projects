/***************************************************************************
 * SEN-39002 Lightning Emulator driver for ESP32
 *
 * Bench-test driver for the Playing With Fusion SEN-39002 "lightning
 * emulator" shield, wired point-to-point to an ESP32 on a breadboard
 * instead of stacked on an Arduino Uno.
 *
 * Derived from PWFusion's SEN-39002_Lightning_Emulator.ino (MIT).
 *   https://github.com/PlayingWithFusion/PWFusion_Lightning_Emulator
 *
 * The PWFusion_MCP4725 library is NOT required -- the two DAC writes it
 * performs are inlined below, so this is a single self-contained file.
 *
 * ---------------------------------------------------------------------
 * HOW THE SHIELD WORKS
 * ---------------------------------------------------------------------
 * Two MCP4725 12-bit I2C DACs (0x62 and 0x64) drive the large air-core
 * solenoid on the board. There is no oscillator: the DACs play a decaying
 * staircase, and each step change kicks the coil. The resulting near-field
 * magnetic transient rings the AS3935's 500 kHz resonant loop antenna --
 * which is why the useful range is centimeters, not meters.
 *
 * "Distance" is emulated purely by REPETITION COUNT. Far/mid/close are
 * 1/2/3 passes through the identical decay burst; more total energy makes
 * the AS3935 compute a closer strike. Amplitude and frequency are the same
 * for all three.
 *
 * ---------------------------------------------------------------------
 * WIRING (5 wires minimum)
 * ---------------------------------------------------------------------
 *   ESP32            SEN-39002 (Uno shield header)
 *   -----            -----------------------------
 *   GPIO21  ------>  SDA
 *   GPIO22  ------>  SCL
 *   3V3     ------>  3.3V   \  see POWER note below -- BOTH shield power
 *   3V3     ------>  5V     /  pins are fed from 3.3 V, not 5 V
 *   GND     ------>  GND
 *
 * Optional physical buttons (set USE_BUTTONS to 1, 3 more wires):
 *   GPIO13  ------>  D9   (FAR pushbutton)
 *   GPIO14  ------>  D7   (MID pushbutton)
 *   GPIO27  ------>  D5   (CLOSE pushbutton)
 *
 * The shield's LEDs (D8/D6/D4) are intentionally left unconnected -- they
 * are only cosmetic, and on an ESP32 those pin NUMBERS land on GPIO 6-11,
 * which are wired to the SPI flash. Do not connect them by number.
 *
 * ---------------------------------------------------------------------
 * POWER: why everything runs at 3.3 V
 * ---------------------------------------------------------------------
 * PWFusion's user guide lists "Power: 5.0V, 3.3V, and all GND pins" as the
 * shield pins used on an Uno, but publishes no schematic, so the internal
 * split between the two rails is unknown. Their sketch header states:
 *
 *   "VDD should match voltage of IO, and can be between 3.3 and 5V"
 *
 * Feeding BOTH shield power pins from the ESP32's 3.3 V rail satisfies
 * that (VDD == IO == 3.3 V) and removes any I2C logic-level question -- a
 * 5 V-powered MCP4725 wants VIH = 0.7 * VDD = 3.5 V, which a 3.3 V ESP32
 * cannot guarantee. Do not mix a 5 V shield rail with 3.3 V ESP32 I2C
 * without a level shifter.
 *
 * The cost of the lower rail is a weaker coil drive. That is compensated
 * in software by AMPLITUDE_SCALE below rather than by mixing voltage
 * domains -- see that comment.
 **************************************************************************/

#include <Wire.h>

// ---- Pin map -------------------------------------------------------------
// I2C. ESP32 defaults; change if your board differs.
static const int PIN_SDA = 21;
static const int PIN_SCL = 22;

// Set to 1 to also accept the shield's three pushbuttons.
// Set to 0 for serial-only control (5 wires total).
#define USE_BUTTONS 0

// Safe ESP32 GPIOs: not flash (6-11), not strapping (0/2/12/15),
// and all support INPUT_PULLUP (unlike input-only 34-39).
static const int PIN_BTN_FAR = 13;
static const int PIN_BTN_MID = 14;
static const int PIN_BTN_CLOSE = 27;

// ---- MCP4725 -------------------------------------------------------------
static const uint8_t DAC_A = 0x62;  // "A1 version" on the shield
static const uint8_t DAC_B = 0x64;  // "A2 version"

static const uint8_t MCP4725_DAC_SET = 0x40;  // write DAC register (volatile)
static const uint8_t MCP4725_DAC_OFF = 0x10;  // fast-mode write, PD=1k pulldown

// ---- Emulation profile ---------------------------------------------------
// PWFusion's calibrated decay envelope, in raw 12-bit DAC codes. Their
// comment: "as calibrated, this profile works from around 7cm and 15cm from
// inductor to inductor" (the user guide says 4-10 cm; start ~7 cm).
// Note only the first 19 entries are used, matching the original sketch.
static const uint16_t OUT_ARRAY[20] = {103, 73, 52, 37, 27, 20, 15, 11, 9, 7,
                                       6,   5,  4,  4,  4,  3,  3,  3, 3, 3};
static const uint8_t OUT_ARRAY_USED = 19;

// PWFusion calibrated the profile above on a 5 V Arduino. At a 3.3 V rail the
// same DAC code produces a proportionally smaller output voltage, so scale by
// 5.0/3.3 to emit the same ABSOLUTE drive. There is enormous headroom -- the
// peak code is 103 of 4095 (2.5% of full scale) -- so this cannot clip.
// Raise it if the sensor will not trigger; lower it to simulate more distance.
static float amplitude_scale = 1.5f;

// Passes through the decay array. This is what encodes "distance".
static const uint8_t PASSES_FAR = 1;
static const uint8_t PASSES_MID = 2;
static const uint8_t PASSES_CLOSE = 3;

// ---- DAC primitives ------------------------------------------------------

static void dacWrite(uint8_t addr, uint16_t code) {
  if (code > 4095) code = 4095;
  Wire.beginTransmission(addr);
  Wire.write(MCP4725_DAC_SET);
  Wire.write((uint8_t)(code >> 4));           // D11..D4
  Wire.write((uint8_t)((code & 0x0F) << 4));  // D3..D0, left-justified
  Wire.endTransmission();
}

static void dacOff(uint8_t addr) {
  Wire.beginTransmission(addr);
  Wire.write(MCP4725_DAC_OFF);
  Wire.write(0x00);
  Wire.endTransmission();
}

static uint16_t scaledCode(uint16_t base) {
  return (uint16_t)(base * amplitude_scale + 0.5f);
}

// ---- Strike emulation ----------------------------------------------------

static void emulate(uint8_t passes, const char *label) {
  Serial.printf("-> %s strike (%u pass%s, amplitude x%.2f)\n", label, passes,
                passes == 1 ? "" : "es", amplitude_scale);

  for (uint8_t p = 0; p < passes; p++) {
    for (uint8_t i = 0; i < OUT_ARRAY_USED; i++) {
      uint16_t code = scaledCode(OUT_ARRAY[i]);
      dacWrite(DAC_A, code);
      dacWrite(DAC_B, code);
      // Note: this delay is NOT what sets the step rate. Each dacWrite is a
      // 4-byte I2C transfer (~400 us at 100 kHz) and there are two per step,
      // so the real step period is ~800 us and this delay is ~4% of it. The
      // bus clock is therefore part of the calibration -- see Wire.setClock().
      delayMicroseconds(30);
    }
  }

  delay(20);
  dacOff(DAC_A);
  dacOff(DAC_B);

  // The AS3935 resolves roughly one event per second, and deactivates for
  // ~1.5 s after classifying a disturber. Pace accordingly.
  delay(1000);
}

// ---- Setup / loop --------------------------------------------------------

static void printHelp() {
  Serial.println();
  Serial.println("SEN-39002 lightning emulator -- ESP32 driver");
  Serial.println("  f  far strike     (1 pass)");
  Serial.println("  m  mid strike     (2 passes)");
  Serial.println("  c  close strike   (3 passes)");
  Serial.println("  a  auto sequence  (far, mid, close, then 3 close)");
  Serial.println("  +  amplitude x1.25   -  amplitude /1.25");
  Serial.println("  ?  this help");
  Serial.println();
  Serial.println("Hold the emulator coil ~7 cm from the AS3935 antenna.");
  Serial.println("Keep phones and laptops ~30 cm away.");
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  delay(200);

  Wire.begin(PIN_SDA, PIN_SCL);
  // PWFusion calibrated on an Uno at the default 100 kHz. Because the I2C
  // transaction time dominates the step period (see emulate()), raising this
  // to 400 kHz would compress the waveform and change the stimulus. Leave it.
  Wire.setClock(100000);

  dacOff(DAC_A);
  dacOff(DAC_B);

#if USE_BUTTONS
  pinMode(PIN_BTN_FAR, INPUT_PULLUP);
  pinMode(PIN_BTN_MID, INPUT_PULLUP);
  pinMode(PIN_BTN_CLOSE, INPUT_PULLUP);
#endif

  // Confirm both DACs actually ACK before trusting any test result.
  for (uint8_t addr : {DAC_A, DAC_B}) {
    Wire.beginTransmission(addr);
    uint8_t err = Wire.endTransmission();
    Serial.printf("DAC 0x%02X: %s\n", addr,
                  err == 0 ? "OK" : "NOT RESPONDING -- check wiring/power");
  }

  printHelp();
}

void loop() {
  if (Serial.available()) {
    switch (Serial.read()) {
      case 'f': emulate(PASSES_FAR, "FAR"); break;
      case 'm': emulate(PASSES_MID, "MID"); break;
      case 'c': emulate(PASSES_CLOSE, "CLOSE"); break;
      case 'a':
        emulate(PASSES_FAR, "FAR");
        emulate(PASSES_MID, "MID");
        emulate(PASSES_CLOSE, "CLOSE");
        for (int i = 0; i < 3; i++) emulate(PASSES_CLOSE, "CLOSE");
        break;
      case '+':
        amplitude_scale *= 1.25f;
        Serial.printf("amplitude x%.2f\n", amplitude_scale);
        break;
      case '-':
        amplitude_scale /= 1.25f;
        Serial.printf("amplitude x%.2f\n", amplitude_scale);
        break;
      case '?': printHelp(); break;
      default: break;  // swallow newlines
    }
  }

#if USE_BUTTONS
  if (!digitalRead(PIN_BTN_FAR)) {
    emulate(PASSES_FAR, "FAR");
  } else if (!digitalRead(PIN_BTN_MID)) {
    emulate(PASSES_MID, "MID");
  } else if (!digitalRead(PIN_BTN_CLOSE)) {
    emulate(PASSES_CLOSE, "CLOSE");
  }
  // The 1 s pace delay inside emulate() doubles as button debounce.
#endif
}
