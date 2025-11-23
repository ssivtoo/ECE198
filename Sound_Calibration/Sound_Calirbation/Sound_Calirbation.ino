#include <Arduino.h>

const int PIN_SOUND = A0;   // Grove sound sensor on A0

float filteredValue = 0.0f;
const float alpha = 0.1f;    // 0..1, smaller = smoother but slower
bool filterInitialized = false;

void setup() {
  Serial.begin(115200);     // Open Serial Monitor at 115200 baud
  while (!Serial) {
    ; // wait for USB serial (needed on some boards like Uno R4)
  }
  
  // Initialize filter with first reading so it starts from a sensible value
  int initialRaw = analogRead(PIN_SOUND);
  filteredValue = initialRaw;
  filterInitialized = true;

  Serial.println("Sound raw analog readings:");
}

void loop() {
  int raw = analogRead(PIN_SOUND);  // 0–1023 on Uno, 0–4095 on Uno R4

  // Exponential moving average filter
  if (!filterInitialized) {
    filteredValue = raw;
    filterInitialized = true;
  } else {
    filteredValue = alpha * raw + (1.0f - alpha) * filteredValue;
  }

  // Print as CSV: raw,filtered for easy plotting
  Serial.print(raw);
  Serial.print(",");
  Serial.println((int)filteredValue);

  delay(10);                        // ~100 samples per second
}