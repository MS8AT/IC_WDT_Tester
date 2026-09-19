#include <Arduino.h>

#define AUTOSERIAL_BACKGROUND_TASK 0
#include "Auto_Serial.h"
#include "RelayResetBench.h"

void setup() {
  StartTaskSerial(115200);
  RelayBenchSetup();
}

void loop() {
  RelayBenchLoop();
  delay(1);
}
