#include <Arduino.h>
#include <WiFi.h>
#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "secrets.example.h"
#endif
#include <ctype.h>
#include <string.h>
#include <time.h>
#include "soc/gpio_reg.h"
#include "soc/io_mux_reg.h"
#include "soc/soc.h"



const char* TZ_INFO = "CET-1CEST,M3.5.0,M10.5.0/3";

constexpr uint8_t GPIO13_PIN = 13;
constexpr uint8_t WIFI_LED_PIN = 2;
constexpr uint32_t WIFI_LED_FAST_MS = 125;
constexpr uint32_t WIFI_LED_SLOW_MS = 500;
constexpr uint32_t WIFI_ATTEMPT_WINDOW_MS = 5000;
constexpr uint8_t RESET_PIN = 25;
// GPIO12 is a boot strap: leave it undriven so flash stays at 3.3V.
constexpr uint8_t GPIO33_PIN = 33;
constexpr uint8_t GPIO13_ON_LEVEL = HIGH;
constexpr uint8_t GPIO13_OFF_LEVEL = LOW;
constexpr uint8_t RESET_ACTIVE_LEVEL = LOW;
constexpr uint8_t RESET_INACTIVE_LEVEL = HIGH;

constexpr unsigned long SERIAL_BAUDRATE = 115200;
constexpr unsigned long RESET_DURATION_MS = 1000;
constexpr unsigned long GPIO33_DEBOUNCE_MS = 40;
constexpr unsigned long WIFI_RECONNECT_INTERVAL_MS = 10000;
constexpr unsigned long NTP_CHECK_INTERVAL_MS = 1000;
constexpr size_t COMMAND_BUFFER_SIZE = 32;
constexpr uint8_t EVENT_HISTORY_SIZE = 10;
constexpr size_t DATETIME_BUFFER_SIZE = 20;

char commandBuffer[COMMAND_BUFFER_SIZE] = {};
size_t commandLength = 0;
bool discardCurrentCommand = false;

bool resetActive = false;
bool relayOnAfterReset = false;
unsigned long resetStartTimeMs = 0;
unsigned long resetDurationMs = RESET_DURATION_MS;
uint8_t gpio33StableState = LOW;
uint8_t gpio33RawState = LOW;
unsigned long gpio33LastRawChangeMs = 0;

struct Gpio33Event {
  uint32_t number;
  uint8_t oldState;
  uint8_t newState;
  bool ntpTimeAvailable;
  time_t unixTime;
  bool relayOn;
  bool externalResetActive;
  char dateTime[DATETIME_BUFFER_SIZE];
  uint32_t uptimeMs;
};

Gpio33Event eventHistory[EVENT_HISTORY_SIZE] = {};
uint8_t eventHistoryWriteIndex = 0;
uint8_t eventHistoryCount = 0;
uint32_t nextEventNumber = 1;
bool eventHistoryPrintPending = false;

bool wifiWasConnected = false;
bool wifiAttemptActive = false;
enum class WifiLedMode : uint8_t { Waiting, Connecting, Connected };
WifiLedMode wifiLedMode = WifiLedMode::Waiting;
bool wifiLedOn = false;
uint32_t wifiLedChangedAtMs = 0;
bool ntpSynchronized = false;
unsigned long lastWifiAttemptMs = 0;
unsigned long lastNtpCheckMs = 0;

const char* levelName(uint8_t level) {
  return level == HIGH ? "HIGH" : "LOW";
}

bool equalsIgnoreCase(const char* left, const char* right) {
  while (*left != '\0' && *right != '\0') {
    char leftChar = *left++;
    char rightChar = *right++;
    if (leftChar >= 'a' && leftChar <= 'z') leftChar -= 'a' - 'A';
    if (rightChar >= 'a' && rightChar <= 'z') rightChar -= 'a' - 'A';
    if (leftChar != rightChar) return false;
  }
  return *left == '\0' && *right == '\0';
}

void trimCommand(char* text) {
  size_t length = strlen(text);
  while (length > 0 && isspace(static_cast<unsigned char>(text[length - 1]))) {
    text[--length] = '\0';
  }
  size_t start = 0;
  while (isspace(static_cast<unsigned char>(text[start]))) ++start;
  if (start > 0) memmove(text, text + start, strlen(text + start) + 1);
}

void getUptimeString(uint32_t uptimeMs, char* output, size_t outputSize) {
  const uint32_t totalSeconds = uptimeMs / 1000UL;
  snprintf(output, outputSize, "%02lu:%02lu:%02lu.%03lu",
    static_cast<unsigned long>(totalSeconds / 3600UL),
    static_cast<unsigned long>((totalSeconds / 60UL) % 60UL),
    static_cast<unsigned long>(totalSeconds % 60UL),
    static_cast<unsigned long>(uptimeMs % 1000UL));
}

bool getDateTimeString(char* output, size_t outputSize, time_t currentTime = time(nullptr)) {
  if (currentTime < 1700000000) return false;
  struct tm localTimeInfo {};
  localtime_r(&currentTime, &localTimeInfo);
  snprintf(output, outputSize, "%02d.%02d.%04d %02d:%02d:%02d",
    localTimeInfo.tm_mday, localTimeInfo.tm_mon + 1,
    localTimeInfo.tm_year + 1900, localTimeInfo.tm_hour,
    localTimeInfo.tm_min, localTimeInfo.tm_sec);
  return true;
}

void printEventTime(const Gpio33Event& event) {
  if (event.ntpTimeAvailable) {
    Serial.print(event.dateTime);
    return;
  }
  char uptimeText[20] = {};
  getUptimeString(event.uptimeMs, uptimeText, sizeof(uptimeText));
  Serial.print("🕒 ⏳ | ⏱ ");
  Serial.print(uptimeText);
}

void printUnixTime(time_t unixTime, bool valid) {
  if (valid) Serial.printf("%lld", static_cast<long long>(unixTime));
  else Serial.print("null");
}

void printEventJson(const Gpio33Event& event, bool replay = false) {
  Serial.print("JSON {\"unix_time\":");
  printUnixTime(event.unixTime, event.ntpTimeAvailable);
  Serial.printf(",\"schema\":1,\"source\":\"ic_wdt_tester\",\"subsystem\":\"WDT\","
    "\"signal\":\"EN\",\"wdt_triggered\":null,\"type\":\"%s\",\"replay\":%s,\"event_id\":%lu,\"uptime_ms\":%lu,"
    "\"time_valid\":%s,\"gpio\":33,\"old\":\"%s\",\"new\":\"%s\","
    "\"relay_on\":%s,\"reset_active\":%s}\n",
    replay ? "gpio_history" : "gpio_change", replay ? "true" : "false",
    static_cast<unsigned long>(event.number), static_cast<unsigned long>(event.uptimeMs),
    event.ntpTimeAvailable ? "true" : "false", levelName(event.oldState), levelName(event.newState),
    event.relayOn ? "true" : "false", event.externalResetActive ? "true" : "false");
}

void printHelp() {
  Serial.println("HELP | STS (STATUS) | ON | OFF | RESET");
  Serial.println("ON: GPIO13 HIGH, WDT relay enabled (boot default)");
  Serial.println("OFF: GPIO13 LOW until ON, RESET or tester reboot; cancels pending relay ON");
  Serial.println("RESET: relay OFF, GPIO25 LOW for 1000 ms, GPIO25 INPUT (Hi-Z), relay ON");
  Serial.println("RESET100: external RESET GPIO25 LOW for 100 ms, then INPUT (Hi-Z)");
  Serial.println("RST: reboot this tester; relay ON after boot; RAM history cleared");
  Serial.println("STS: GPIO13, reset, GPIO33, WiFi, NTP, uptime; no output changes");
  Serial.println("STS: also IP, RSSI, local time, Unix time and JSON schema=1");
  Serial.println("JSON: human text then pipe + JSON object; schema=1; types=status,gpio_change,gpio_history");
  Serial.println("HISTORY: last 10 GPIO33 changes with time; no output changes");
  Serial.println("RESETDIAG: GPIO25 pad/latch/config and GPIO33 levels; read-only");
  Serial.println("Commands: case-insensitive, one per line (CR/LF), max 31 chars");
  Serial.println("GPIO2 LED: waiting slow blink, connecting fast blink, WiFi connected steady ON");
}

void printStatus() {
  const unsigned long uptimeMs = millis();
  const bool connected = WiFi.status() == WL_CONNECTED;
  const bool relayOn = digitalRead(GPIO13_PIN) == GPIO13_ON_LEVEL;
  const time_t unixTime = time(nullptr);
  char dateTime[DATETIME_BUFFER_SIZE] = {};
  const bool timeValid = ntpSynchronized && getDateTimeString(dateTime, sizeof(dateTime), unixTime);
  const String ip = connected ? WiFi.localIP().toString() : "";
  const int rssi = connected ? WiFi.RSSI() : 0;
  const uint8_t resetLevel = digitalRead(RESET_PIN);
  const uint8_t inputRaw = digitalRead(GPIO33_PIN);
  Serial.printf("STS GPIO13=%s RESET=%s GPIO33=%s WIFI=%s NTP=%s UPTIME_MS=%lu\n",
    relayOn ? "ON" : "OFF",
    resetActive ? "ACTIVE" : "IDLE", levelName(gpio33StableState),
    connected ? "CONNECTED" : "DISCONNECTED",
    timeValid ? "SYNCED" : "WAIT", uptimeMs);
  Serial.println(connected ? "📶 ✅" : "📶 ❌");
  Serial.printf("🌐 IP: %s\n", connected ? ip.c_str() : "—");
  if (connected) Serial.printf("📶 RSSI: %d dBm\n", rssi);
  else Serial.println("📶 RSSI: —");
  Serial.println(timeValid ? "🕒 NTP ✅" : "🕒 NTP ⏳");
  if (timeValid) Serial.printf("🕒 %s\n", dateTime);
  else Serial.println("🕒 —");
  Serial.print("UNIX_TIME=");
  printUnixTime(unixTime, timeValid);
  Serial.println();
  Serial.printf("GPIO25=%s GPIO33_RAW=%s EVENTS=%lu HISTORY=%u/%u | ",
    levelName(resetLevel), levelName(inputRaw), static_cast<unsigned long>(nextEventNumber - 1),
    static_cast<unsigned>(eventHistoryCount), static_cast<unsigned>(EVENT_HISTORY_SIZE));
  Serial.print("JSON {\"unix_time\":");
  printUnixTime(unixTime, timeValid);
  Serial.printf(",\"schema\":1,\"source\":\"ic_wdt_tester\",\"subsystem\":\"WDT\",\"type\":\"status\",\"uptime_ms\":%lu,\"time_valid\":%s,\"local_time\":",
    uptimeMs, timeValid ? "true" : "false");
  if (timeValid) Serial.printf("\"%s\"", dateTime);
  else Serial.print("null");
  Serial.printf(",\"relay_on\":%s,\"reset_active\":%s,\"relay_on_after_reset\":%s,"
    "\"gpio12\":\"%s\",\"gpio25\":\"%s\",\"reset_gpio\":25,\"reset_drive\":\"%s\",\"gpio33\":\"%s\",\"gpio33_raw\":\"%s\","
    "\"wifi_connected\":%s,\"ip\":",
    relayOn ? "true" : "false", resetActive ? "true" : "false", relayOnAfterReset ? "true" : "false",
    levelName(digitalRead(12)), levelName(resetLevel), resetActive ? "LOW" : "HI_Z",
    levelName(gpio33StableState), levelName(inputRaw), connected ? "true" : "false");
  if (connected) Serial.printf("\"%s\",\"rssi_dbm\":%d", ip.c_str(), rssi);
  else Serial.print("null,\"rssi_dbm\":null");
  Serial.printf(",\"ntp_synced\":%s,\"events_total\":%lu,\"history_count\":%u}\n",
    timeValid ? "true" : "false", static_cast<unsigned long>(nextEventNumber - 1),
    static_cast<unsigned>(eventHistoryCount));
}

void printResetDiagnostics() {
  const uint32_t mask = 1UL << RESET_PIN;
  const uint32_t mux = REG_READ(IO_MUX_GPIO25_REG);
  const unsigned function = (mux & MCU_SEL_M) >> MCU_SEL_S;
  const unsigned inputEnabled = (mux & FUN_IE) != 0;
  const unsigned outputEnabled = (REG_READ(GPIO_ENABLE_REG) & mask) != 0;
  Serial.printf("RESETDIAG ACTIVE=%u EXPECTED=%s PAD=%s LATCH=%s OE=%u IE=%u MUX=%u PAD_VALID=%u EN_RAW=%s EN_STABLE=%s ELAPSED_MS=%lu\n",
    static_cast<unsigned>(resetActive), levelName(resetActive ? RESET_ACTIVE_LEVEL : RESET_INACTIVE_LEVEL),
    levelName(digitalRead(RESET_PIN)), levelName((REG_READ(GPIO_OUT_REG) & mask) ? HIGH : LOW),
    outputEnabled, inputEnabled, function, static_cast<unsigned>(inputEnabled && function == PIN_FUNC_GPIO),
    levelName(digitalRead(GPIO33_PIN)), levelName(gpio33StableState),
    resetActive ? static_cast<unsigned long>(millis() - resetStartTimeMs) : 0UL);
}

void printEventHistory() {
  // A table must not delay the release of an active external RESET pulse.
  if (resetActive) {
    eventHistoryPrintPending = true;
    return;
  }
  eventHistoryPrintPending = false;
  Serial.printf("📋 GPIO33 | 🔢 %lu | 🧾 %u/%u\n",
    static_cast<unsigned long>(nextEventNumber - 1),
    static_cast<unsigned>(eventHistoryCount), static_cast<unsigned>(EVENT_HISTORY_SIZE));
  const uint8_t firstIndex = eventHistoryCount == EVENT_HISTORY_SIZE ? eventHistoryWriteIndex : 0;
  for (uint8_t row = 0; row < eventHistoryCount; ++row) {
    const uint8_t index = static_cast<uint8_t>((firstIndex + row) % EVENT_HISTORY_SIZE);
    const Gpio33Event& event = eventHistory[index];
    Serial.print("UNIX_TIME=");
    printUnixTime(event.unixTime, event.ntpTimeAvailable);
    Serial.print(" | WDT/EN GPIO33 ");
    Serial.printf("#%lu  %s -> %s | ", static_cast<unsigned long>(event.number),
      levelName(event.oldState), levelName(event.newState));
    printEventTime(event);
    Serial.print(" | ");
    printEventJson(event, true);
  }
}

void releaseResetLine() {
  // No pull-up and no driven HIGH: the target board owns the released level.
  pinMode(RESET_PIN, INPUT);
}

void startResetPulse(unsigned long durationMs = RESET_DURATION_MS, bool cycleRelay = false) {
  if (cycleRelay) {
    digitalWrite(GPIO13_PIN, GPIO13_OFF_LEVEL);
    relayOnAfterReset = true;
    Serial.println("🔴 GPIO13");
  }
  resetActive = true;
  resetDurationMs = durationMs;
  resetStartTimeMs = millis();
  digitalWrite(RESET_PIN, RESET_ACTIVE_LEVEL);
  pinMode(RESET_PIN, OUTPUT);
  if (resetDurationMs == 100) Serial.println("RESET100 START");
  Serial.println("🔄 GPIO25 ⬇️");
}

void handleReset() {
  if (!resetActive) return;
  if (static_cast<unsigned long>(millis() - resetStartTimeMs) < resetDurationMs) return;
  releaseResetLine();
  resetActive = false;
  if (resetDurationMs == 100) Serial.println("RESET100 DONE");
  Serial.println("🔄 GPIO25 INPUT (Hi-Z)");
  if (relayOnAfterReset) {
    relayOnAfterReset = false;
    digitalWrite(GPIO13_PIN, GPIO13_ON_LEVEL);
    Serial.println("🟢 GPIO13");
  }
  if (eventHistoryPrintPending) printEventHistory();
}

void handleCommand(const char* command) {
  if (equalsIgnoreCase(command, "ON")) {
    relayOnAfterReset = false;
    digitalWrite(GPIO13_PIN, GPIO13_ON_LEVEL);
    Serial.println("🟢 GPIO13");
  } else if (equalsIgnoreCase(command, "OFF")) {
    relayOnAfterReset = false;
    digitalWrite(GPIO13_PIN, GPIO13_OFF_LEVEL);
    Serial.println("🔴 GPIO13");
  } else if (equalsIgnoreCase(command, "HELP")) {
    printHelp();
  } else if (equalsIgnoreCase(command, "STS") || equalsIgnoreCase(command, "STATUS")) {
    printStatus();
  } else if (equalsIgnoreCase(command, "HISTORY")) {
    printEventHistory();
  } else if (equalsIgnoreCase(command, "RESETDIAG")) {
    printResetDiagnostics();
  } else if (equalsIgnoreCase(command, "RESET")) {
    startResetPulse(RESET_DURATION_MS, true);
  } else if (equalsIgnoreCase(command, "RESET100")) {
    startResetPulse(100);
  } else if (equalsIgnoreCase(command, "RST")) {
    // Release an active external reset before waiting for UART and rebooting.
    releaseResetLine();
    resetActive = false;
    relayOnAfterReset = false;
    Serial.println("RST REBOOT");
    Serial.flush();
    ESP.restart();
  } else if (command[0] != '\0') {
    Serial.print("❓ ");
    Serial.println(command);
    Serial.println("HELP: commands");
  }
}

void handleSerial() {
  while (Serial.available() > 0) {
    const char received = static_cast<char>(Serial.read());
    if (received == '\r' || received == '\n') {
      if (!discardCurrentCommand && commandLength > 0) {
        commandBuffer[commandLength] = '\0';
        trimCommand(commandBuffer);
        handleCommand(commandBuffer);
      }
      commandLength = 0;
      discardCurrentCommand = false;
      continue;
    }
    if (discardCurrentCommand) continue;
    if (commandLength >= COMMAND_BUFFER_SIZE - 1) {
      commandLength = 0;
      discardCurrentCommand = true;
      Serial.println("❌ ⌨️ >31");
      continue;
    }
    commandBuffer[commandLength++] = received;
  }
}

void handleGPIO33() {
  const unsigned long nowMs = millis();
  const uint8_t currentRawState = digitalRead(GPIO33_PIN) == HIGH ? HIGH : LOW;
  if (currentRawState != gpio33RawState) {
    gpio33RawState = currentRawState;
    gpio33LastRawChangeMs = nowMs;
  }
  if (gpio33RawState == gpio33StableState) return;
  if (static_cast<unsigned long>(nowMs - gpio33LastRawChangeMs) < GPIO33_DEBOUNCE_MS) return;
  const uint8_t oldState = gpio33StableState;
  gpio33StableState = gpio33RawState;
  Gpio33Event& event = eventHistory[eventHistoryWriteIndex];
  event = {};
  event.number = nextEventNumber++;
  event.oldState = oldState;
  event.newState = gpio33StableState;
  event.uptimeMs = nowMs;
  event.unixTime = time(nullptr);
  event.ntpTimeAvailable = ntpSynchronized &&
    getDateTimeString(event.dateTime, sizeof(event.dateTime), event.unixTime);
  event.relayOn = digitalRead(GPIO13_PIN) == GPIO13_ON_LEVEL;
  event.externalResetActive = resetActive;
  eventHistoryWriteIndex = static_cast<uint8_t>((eventHistoryWriteIndex + 1) % EVENT_HISTORY_SIZE);
  if (eventHistoryCount < EVENT_HISTORY_SIZE) ++eventHistoryCount;
  Serial.print("UNIX_TIME=");
  printUnixTime(event.unixTime, event.ntpTimeAvailable);
  Serial.printf(" | 🔔 WDT/EN GPIO33 #%lu: ", static_cast<unsigned long>(event.number));
  Serial.print(levelName(oldState));
  Serial.print(" -> ");
  Serial.print(levelName(gpio33StableState));
  Serial.print(" | ");
  printEventTime(event);
  Serial.print(" | ");
  printEventJson(event);
  printEventHistory();
}

void startWiFiConnection(bool firstAttempt) {
  if (firstAttempt) Serial.println("📶 ⏳");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  lastWifiAttemptMs = millis();
  wifiAttemptActive = true;
}

void handleWiFiLed() {
  const uint32_t nowMs = millis();
  const WifiLedMode mode = WiFi.status() == WL_CONNECTED ? WifiLedMode::Connected :
    wifiAttemptActive ? WifiLedMode::Connecting : WifiLedMode::Waiting;
  if (mode != wifiLedMode) {
    wifiLedMode = mode;
    wifiLedChangedAtMs = nowMs;
    wifiLedOn = true;
    digitalWrite(WIFI_LED_PIN, HIGH);
  }
  if (mode == WifiLedMode::Connected) return;
  const uint32_t intervalMs = mode == WifiLedMode::Connecting ? WIFI_LED_FAST_MS : WIFI_LED_SLOW_MS;
  if (static_cast<uint32_t>(nowMs - wifiLedChangedAtMs) >= intervalMs) {
    wifiLedChangedAtMs = nowMs;
    wifiLedOn = !wifiLedOn;
    digitalWrite(WIFI_LED_PIN, wifiLedOn ? HIGH : LOW);
  }
}

void handleWiFi() {
  const unsigned long nowMs = millis();
  const int wifiStatus = WiFi.status();
  if (wifiStatus == WL_CONNECTED) {
    wifiAttemptActive = false;
    if (!wifiWasConnected) {
      wifiWasConnected = true;
      Serial.println("📶 ✅");
      Serial.print("🌐 IP: ");
      Serial.println(WiFi.localIP());
      Serial.print("📶 RSSI: ");
      Serial.print(WiFi.RSSI());
      Serial.println(" dBm");
      setenv("TZ", TZ_INFO, 1);
      tzset();
      configTime(0, 0, "pool.ntp.org", "time.google.com");
      lastNtpCheckMs = 0;
    }
    return;
  }
  if (wifiWasConnected) {
    wifiWasConnected = false;
    wifiAttemptActive = false;
    lastWifiAttemptMs = nowMs;
    Serial.println("📶 ❌ | ⚙️ ✅");
  }
  if (wifiStatus == WL_CONNECT_FAILED || wifiStatus == WL_NO_SSID_AVAIL ||
      static_cast<uint32_t>(nowMs - lastWifiAttemptMs) >= WIFI_ATTEMPT_WINDOW_MS) {
    wifiAttemptActive = false;
  }
  if (static_cast<unsigned long>(nowMs - lastWifiAttemptMs) >= WIFI_RECONNECT_INTERVAL_MS) {
    startWiFiConnection(false);
  }
}

void handleTimeSync() {
  if (WiFi.status() != WL_CONNECTED || ntpSynchronized) return;
  const unsigned long nowMs = millis();
  if (static_cast<unsigned long>(nowMs - lastNtpCheckMs) < NTP_CHECK_INTERVAL_MS) return;
  lastNtpCheckMs = nowMs;
  if (time(nullptr) < 1700000000) return;
  ntpSynchronized = true;
  char dateTime[DATETIME_BUFFER_SIZE] = {};
  Serial.println("🕒 NTP ✅");
  if (getDateTimeString(dateTime, sizeof(dateTime))) {
    Serial.print("🕒 ");
    Serial.println(dateTime);
  }
}

void setup() {
  Serial.begin(SERIAL_BAUDRATE);
  Serial.setDebugOutput(false);
  // Preload HIGH before enabling output; never pulse OFF during startup.
  digitalWrite(GPIO13_PIN, GPIO13_ON_LEVEL);
  pinMode(GPIO13_PIN, OUTPUT);

  digitalWrite(WIFI_LED_PIN, LOW);
  pinMode(WIFI_LED_PIN, OUTPUT);
  wifiLedOn = false;
  wifiLedMode = WifiLedMode::Waiting;
  wifiLedChangedAtMs = millis();

  // GPIO25 управляет RESET внешнего устройства, а не EN/RESET этого ESP32.
  releaseResetLine();

  // Кнопка подключается между GPIO33 и GND.
  // При внешней подтяжке вместо INPUT_PULLUP используйте INPUT.
  pinMode(GPIO33_PIN, INPUT_PULLUP);
  gpio33StableState = digitalRead(GPIO33_PIN) == HIGH ? HIGH : LOW;
  gpio33RawState = gpio33StableState;
  gpio33LastRawChangeMs = millis();

  Serial.println("IC_WDT_TESTER MAIN | GPIO13=ON | HELP | STS | RESET_PIN=25");

  WiFi.mode(WIFI_STA);
  startWiFiConnection(true);
  handleWiFiLed();
}

void loop() {
  handleSerial();
  handleReset();
  handleGPIO33();
  handleWiFi();
  handleWiFiLed();
  handleTimeSync();
  yield();
}
