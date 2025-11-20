#include "HX711.h"
#include "rgb_lcd.h"
#include <Arduino.h>
#include <Wire.h>
#include <math.h>

// Pins
const int PIN_SOUND = A0; // Grove Sound
const int PIN_LIGHT = A1; // Grove Light
const int LOADCELL_DOUT_PIN = 3;
const int LOADCELL_SCK_PIN = 2;

// LCD
rgb_lcd lcd;

// Load Cell
HX711 scale;

// Simple EMA helper
struct EMA {
  float y = 0, a;
  EMA(float a_ = 0.05f) : a(a_) {}
  float upd(float x) {
    y = a * x + (1 - a) * y;
    return y;
  }
};

EMA soundMean(0.02f), soundMag(0.05f), lightMean(0.02f);
float noiseBase = 1.0f; // baseline for noise magnitude
float lightBase = 1.0f; // baseline for light avg

// Threshold multipliers (tune here)
const float NOISE_K = 2.5f; // > 2.5x baseline -> High noise
const float LIGHT_K = 1.5f; // > 1.5x baseline -> Bright light

void setup() {
  Serial.begin(115200);
  Wire.begin();

  lcd.begin(16, 2);
  lcd.setRGB(0, 64, 128);
  lcd.setCursor(0, 0);
  lcd.print("Bedside Proto");
  lcd.setCursor(0, 1);
  lcd.print("Calibrating...");

  // HX711 Setup
  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);
  scale.set_scale(924.f); // Calibration factor - adjust as needed
  scale.tare();           // Reset scale to 0

  // 3s baseline calibration
  unsigned long t0 = millis();
  while (millis() - t0 < 3000) {
    int s = analogRead(PIN_SOUND);
    int l = analogRead(PIN_LIGHT);
    soundMean.upd(s);
    soundMag.upd(fabsf(s - soundMean.y));
    lightMean.upd(l);
  }
  noiseBase = max(1.0f, soundMag.y);
  lightBase = max(1.0f, lightMean.y);

  lcd.clear();
}

void loop() {
  // Read sensors
  int sraw = analogRead(PIN_SOUND);
  int lraw = analogRead(PIN_LIGHT);
  float weight = scale.get_units(1); // Read 1 average

  soundMean.upd(sraw);
  float smag = soundMag.upd(
      fabsf(sraw - soundMean.y));   // noise magnitude (EMA of deviation)
  float lavg = lightMean.upd(lraw); // smoothed light level

  bool noiseHigh = (smag > NOISE_K * noiseBase);
  bool lightBright = (lavg > LIGHT_K * lightBase);

  // LCD update each ~1s
  static unsigned long lastLcd = 0;
  unsigned long now = millis();
  if (now - lastLcd > 1000) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("L:");
    lcd.print(lightBright ? "BR" : "OK");
    lcd.print(" W:");
    lcd.print((int)weight);

    lcd.setCursor(0, 1);
    lcd.print("N:");
    lcd.print(noiseHigh ? "HI" : "OK");

    // Serial Output: light,sound,weight sample output: 601,71,-442.49
    Serial.print((int)lavg);
    Serial.print(",");
    Serial.print((int)smag); // Sending magnitude as sound level
    Serial.print(",");
    Serial.println(weight);

    lastLcd = now;
  }
}
