#include "HX711.h"
#include <Arduino.h>

// Pins
const int PIN_SOUND = A0;       // Grove Sound
const int PIN_LIGHT = A1;       // Grove Light
const int LOADCELL_DOUT_PIN = 3;
const int LOADCELL_SCK_PIN  = 2;

// Load Cell
HX711 scale;

void setup() {
  Serial.begin(115200);

  // HX711 setup
  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);
  // Optional: set your calibration factor here if you already know it
  // scale.set_scale(924.0f);
  scale.tare();  // zero the scale
}

void loop() {
  int soundRaw = analogRead(PIN_SOUND);
  int lightRaw = analogRead(PIN_LIGHT);
  float weight = scale.get_units(1);  // get weight reading

  // simple CSV-style output: sound,light,weight
  Serial.print(lightRaw);
  Serial.print(",");
  Serial.print(soundRaw);
  Serial.print(",");
  Serial.println(weight);

  delay(100);  // small delay so it doesn't spam too fast
}