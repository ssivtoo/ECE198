#include <Arduino.h>
#include <Wire.h>
#include "rgb_lcd.h"


// Pins
const int PIN_SOUND = A0;       // Grove Sound
const int PIN_LIGHT = A1;       // Grove Light
const int PIN_POT = A3;

rgb_lcd lcd;

void setup() {
  Serial.begin(115200);

  // LCD setup (16x2 Grove RGB LCD)
  lcd.begin(16, 2);
  lcd.setRGB(0, 255, 0);  // green = OK
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Bedside Monitor");
  lcd.setCursor(0, 1);
  lcd.print("Starting...");

  delay(1000);
  lcd.clear();
  lcd.setRGB(0, 0, 0);
}

void loop() {

  // check if PC sent us a command (e.g. "DRINK WATER" or "OK")
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() > 0) {
      lcd.clear();
      lcd.setCursor(0, 0);

      // Map the short codes from Python to nicer LCD messages / colors
      if (cmd == "NOISY") {
        lcd.setRGB(255, 0, 0);
        lcd.print("Too noisy");
        lcd.setCursor(0, 1);
        lcd.print("Check patient");
      } else if (cmd == "TOO BRIGHT") {
        lcd.setRGB(255, 0, 0);
        lcd.print("Too bright");
        lcd.setCursor(0, 1);
        lcd.print("Dim the lights");
      } else if (cmd == "REFILL NOW") {
        lcd.setRGB(255, 0, 0);
        lcd.print("Water bottle");
        lcd.setCursor(0, 1);
        lcd.print("REFILL NOW");
      } else if (cmd == "NURSE CHECK") {
        lcd.setRGB(255, 0, 0);
        lcd.print("Hydration issue");
        lcd.setCursor(0, 1);
        lcd.print("NURSE CHECK");
      } else if (cmd == "DRINK WATER") {
        lcd.setRGB(255, 165, 0);  // orange reminder
        lcd.print("You should");
        lcd.setCursor(0, 1);
        lcd.print("drink now");
      } else if (cmd == "LOW WATER") {
        lcd.setRGB(255, 165, 0);
        lcd.print("Low water lvl");
        lcd.setCursor(0, 1);
        lcd.print("Check bottle");
      } else if (cmd == "OK") {
        lcd.setRGB(0, 0, 0);
        lcd.print("Environment");
        lcd.setCursor(0, 1);
        lcd.print("OK");
      } else {
        // fallback: show raw text
        lcd.setRGB(0, 255, 0);
        lcd.print(cmd);
      }
    }
  }


  int lightRaw = analogRead(PIN_LIGHT);
  int soundRaw = analogRead(PIN_SOUND);
  float weight = analogRead(PIN_POT);  // get weight reading

  // simple CSV-style output: light,noise,weight
  Serial.print(lightRaw);
  Serial.print(",");
  Serial.print(soundRaw);
  Serial.print(",");
  Serial.println(weight);

  // check if PC sent us a command (e.g. "DRINK WATER" or "OK")
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() > 0) {
    }
  }

  delay(500);  // small delay so it doesn't spam too fast
}