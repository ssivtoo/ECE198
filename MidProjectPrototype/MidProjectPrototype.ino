#include <Arduino.h>
#include <Wire.h>
#include <math.h>
#include "rgb_lcd.h"

// Pins
const int PIN_SOUND = A0; // Grove Sound
const int PIN_LIGHT = A1; // Grove Light

// LCD
rgb_lcd lcd;

// Simple EMA helper
struct EMA {
  float y = 0, a;
  EMA(float a_=0.05f): a(a_) {}
  float upd(float x){ y = a*x + (1-a)*y; return y; }
};

EMA soundMean(0.02f), soundMag(0.05f), lightMean(0.02f);
float noiseBase = 1.0f;   // baseline for noise magnitude
float lightBase = 1.0f;   // baseline for light avg

// Threshold multipliers (tune here)
const float NOISE_K = 2.5f; // > 2.5x baseline -> High noise
const float LIGHT_K = 1.5f; // > 1.5x baseline -> Bright light

void setup(){
  Serial.begin(115200);
  Wire.begin();

  lcd.begin(16,2);
  lcd.setRGB(0,64,128);
  lcd.setCursor(0,0); lcd.print("Bedside Proto");
  lcd.setCursor(0,1); lcd.print("Calibrating...");

  // 3s baseline calibration
  unsigned long t0 = millis();
  while(millis() - t0 < 3000){
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

void loop(){
  // Read sensors
  int sraw = analogRead(PIN_SOUND);
  int lraw = analogRead(PIN_LIGHT);

  soundMean.upd(sraw);
  float smag = soundMag.upd(fabsf(sraw - soundMean.y)); // noise magnitude (EMA of deviation)
  float lavg = lightMean.upd(lraw);                      // smoothed light level

  bool noiseHigh   = (smag  > NOISE_K * noiseBase);
  bool lightBright = (lavg  > LIGHT_K * lightBase);

  // LCD update each ~1s
  static unsigned long lastLcd = 0;
  unsigned long now = millis();
  if(now - lastLcd > 1000){
    lcd.clear();
    lcd.setCursor(0,0);
    lcd.print("L:"); lcd.print(lightBright ? "BR" : "OK");
    lcd.print("  N:"); lcd.print(noiseHigh ? "HI" : "OK");

    // percentages vs baseline
    int lperc = (int)(100.0f * lavg / lightBase);
    int nperc = (int)(100.0f * smag / noiseBase);
    lcd.setCursor(0,1);
    lcd.print("l:"); lcd.print(lperc); lcd.print("% n:"); lcd.print(nperc); lcd.print("%");

    // Serial debug
    Serial.print("Sraw="); Serial.print(sraw);
    Serial.print(" smag="); Serial.print(smag,1);
    Serial.print(" baseN="); Serial.print(noiseBase,1);
    Serial.print(" | Lraw="); Serial.print(lraw);
    Serial.print(" lavg="); Serial.print(lavg,1);
    Serial.print(" baseL="); Serial.print(lightBase,1);
    Serial.print(" | L:"); Serial.print(lightBright?"BR":"OK");
    Serial.print(" N:"); Serial.println(noiseHigh?"HI":"OK");

    lastLcd = now;
  }
}
