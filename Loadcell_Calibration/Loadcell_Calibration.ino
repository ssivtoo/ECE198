#include "HX711.h"

// Wiring:
// Load Cell DOUT -> Pin 3
// Load Cell SCK  -> Pin 2
const int LOADCELL_DOUT_PIN = 3;
const int LOADCELL_SCK_PIN = 2;
const int PIN_BTN_TARE = 4;

HX711 scale;

void setup() {
  Serial.begin(115200);
  pinMode(PIN_BTN_TARE, INPUT);

  Serial.println("HX711 Calibration Sketch");
  Serial.println("------------------------");
  Serial.println("1. Remove all weight from the scale.");

  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);
  scale.set_scale(); // Set scale to 1 (raw mode)
  scale.tare();      // Reset scale to 0

  Serial.println("Scale tared. Waiting 3 seconds...");
  delay(3000);
  Serial.println("2. Place a KNOWN WEIGHT on the scale now.");
  Serial.println("   Press Button on D4 to Tare if needed.");
}

void loop() {
  // Check for tare button
  if (digitalRead(PIN_BTN_TARE) == HIGH) {
    Serial.println("Taring...");
    scale.tare();
    Serial.println("Scale reset to 0.");
    delay(1000); // Debounce
  }

  // Read the raw average of 10 readings
  float rawReading = scale.get_units(1);

  
  Serial.println(rawReading);
  

  delay(500);
}
