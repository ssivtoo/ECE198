#include <Arduino.h>
#include <Wire.h>
#include "rgb_lcd.h"

const int PIN_SOUND = A0;
const int PIN_LIGHT = A1;
const int PIN_POT   = A3;

rgb_lcd lcd;

void setup() {
  Serial.begin(115200);
  lcd.begin(16, 2);
  lcd.setRGB(0, 255, 0);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Bedside Monitor");
  lcd.setCursor(0, 1);
  lcd.print("Starting...");
  delay(1000);
  lcd.clear();
  lcd.setRGB(0, 0, 0);
}

void applyCommand(String cmd) {
  lcd.clear();
  lcd.setCursor(0, 0);

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
  } else if (cmd == "DRINK MORE") {
    lcd.setRGB(255, 165, 0);
    lcd.print("Please drink");
    lcd.setCursor(0, 1);
    lcd.print("more water");
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
    lcd.setRGB(0, 255, 0);
    lcd.print(cmd);
  }
}

void loop() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() > 0) {
      applyCommand(cmd);
    }
  }

  int lightRaw = analogRead(PIN_LIGHT);
  int soundRaw = analogRead(PIN_SOUND);
  float weight = analogRead(PIN_POT);

  Serial.print(lightRaw);
  Serial.print(",");
  Serial.print(soundRaw);
  Serial.print(",");
  Serial.println(weight);

  delay(500);
}
