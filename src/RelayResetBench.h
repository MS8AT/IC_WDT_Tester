#pragma once

#ifndef RELAY_BENCH_HOST_TEST
#include <Arduino.h>
#include "driver/gpio.h"
#include "esp_timer.h"
#include "esp_system.h"
#include "esp_mac.h"
#include "soc/gpio_struct.h"
#endif

#include <stdint.h>
#include <string.h>

#ifndef RELAY_BENCH_MAINTENANCE_90S
#define RELAY_BENCH_MAINTENANCE_90S 0
#endif

#ifndef RELAY_BENCH_LATCHED_OFF
#define RELAY_BENCH_LATCHED_OFF 0
#endif

#ifndef RELAY_BENCH_START_LOW
#define RELAY_BENCH_START_LOW 0
#endif

#ifndef RELAY_BENCH_BLINK_TEST
#define RELAY_BENCH_BLINK_TEST 0
#endif

#if RELAY_BENCH_LATCHED_OFF
static constexpr const char *RELAY_BENCH_MARKER = "RELAY13-EN33-LATCH-02";
#elif RELAY_BENCH_MAINTENANCE_90S
static constexpr const char *RELAY_BENCH_MARKER = "RELAY13-EN33-MAINT90-01";
#else
static constexpr const char *RELAY_BENCH_MARKER = "RELAY13-EN33-01";
#endif
static constexpr int RELAY_BENCH_RELAY_PIN = 13;
static constexpr int RELAY_BENCH_EN_PIN = 33;
static constexpr uint32_t RELAY_BENCH_MAX_BYPASS_MS = 5000;
static constexpr uint32_t RELAY_BENCH_MAINTENANCE_MS = 90000;
static constexpr uint8_t RELAY_BENCH_EVENT_CAPACITY = 128;
#if RELAY_BENCH_BLINK_TEST
static constexpr uint8_t RELAY_BENCH_CHANGE_HISTORY = 10;
#endif

static_assert(RELAY_BENCH_RELAY_PIN != RELAY_BENCH_EN_PIN, "Relay and EN sense pins must differ");

struct RelayBenchEdge {
  int64_t atUs;
  uint32_t sequence;
  uint8_t level;
};

#if RELAY_BENCH_BLINK_TEST
struct RelayBenchPinChange {
  int64_t atUs;
  uint8_t from;
  uint8_t to;
};
#endif

enum RelayBenchReleaseReason : uint8_t {
  RelayBenchReleaseNone = 0,
  RelayBenchReleaseDeadline,
  RelayBenchReleaseCommand,
  RelayBenchReleaseMalformed,
  RelayBenchReleaseRxOverflow,
  RelayBenchReleaseTimerFailure,
  RelayBenchReleaseBusy
};

static portMUX_TYPE relayBenchMux = portMUX_INITIALIZER_UNLOCKED;
static RelayBenchEdge relayBenchEvents[RELAY_BENCH_EVENT_CAPACITY];
#if RELAY_BENCH_BLINK_TEST
static RelayBenchPinChange relayBenchChanges[RELAY_BENCH_CHANGE_HISTORY] = {};
#endif
static volatile uint8_t relayBenchRead = 0;
static volatile uint8_t relayBenchWrite = 0;
#if RELAY_BENCH_BLINK_TEST
static uint8_t relayBenchChangeCount = 0;
static uint8_t relayBenchChangeWrite = 0;
#endif
static volatile uint32_t relayBenchSequence = 0;
static volatile uint32_t relayBenchDropped = 0;
static volatile uint8_t relayBenchLastEn = 0;
static volatile bool relayBenchBypassActive = false;
static volatile bool relayBenchLatchedOff = false;
static volatile bool relayBenchArming = false;
static volatile bool relayBenchRelayHigh = true;
static volatile int64_t relayBenchDeadlineUs = 0;
static volatile int64_t relayBenchArmedAtUs = 0;
static volatile uint32_t relayBenchCommandId = 0;
static volatile bool relayBenchReleasePending = false;
static volatile RelayBenchReleaseReason relayBenchReleaseReason = RelayBenchReleaseNone;
static volatile int64_t relayBenchReleasedAtUs = 0;
static volatile int64_t relayBenchReleasedArmAtUs = 0;
static volatile uint32_t relayBenchReleasedCommandId = 0;
static esp_timer_handle_t relayBenchTimer = nullptr;
static bool relayBenchTimerReady = false;
static uint32_t relayBenchObservedRxDropped = 0;
static bool relayBenchBlinkTestActive = false;
static char relayBenchLine[64] = {};
static uint8_t relayBenchLineLength = 0;
static bool relayBenchDiscardLine = false;

static const char *RelayBenchReleaseReasonName(RelayBenchReleaseReason reason) {
  switch (reason) {
    case RelayBenchReleaseDeadline: return "deadline";
    case RelayBenchReleaseCommand: return "command";
    case RelayBenchReleaseMalformed: return "malformed";
    case RelayBenchReleaseRxOverflow: return "rx_overflow";
    case RelayBenchReleaseTimerFailure: return "timer_failure";
    case RelayBenchReleaseBusy: return "busy";
    default: return "none";
  }
}

// Task-context output only: never print inside the ISR, timer callback or mux.
// Fixed tokens keep each JSON printf below Auto_Serial's 384-byte buffer.
static void RelayBenchPinJson(const char *event, int pin, uint8_t level,
                              int64_t atUs, uint32_t eventId, const char *reason) {
  AppSerial.printf("JSON {\"schema\":1,\"type\":\"wdt_pin\",\"source\":\"relay_bench\","
    "\"subsystem\":\"WDT\",\"event\":\"%s\",\"signal\":\"%s\",\"unix_time\":null,"
    "\"time_valid\":false,\"uptime_us\":%lld,\"gpio\":%d,\"level\":%u,"
    "\"event_id\":%lu,\"reason\":\"%s\",\"wdt_triggered\":null}\n",
    event, pin == RELAY_BENCH_EN_PIN ? "EN" : "relay_control", (long long)atUs,
    pin, static_cast<unsigned>(level), (unsigned long)eventId, reason);
}

static void IRAM_ATTR RelayBenchWriteRelay(bool high) {
#ifdef RELAY_BENCH_HOST_TEST
  gpio_set_level((gpio_num_t)RELAY_BENCH_RELAY_PIN, high ? 1 : 0);
#else
  if (high) GPIO.out_w1ts = 1UL << RELAY_BENCH_RELAY_PIN;
  else GPIO.out_w1tc = 1UL << RELAY_BENCH_RELAY_PIN;
#endif
}

static void RelayBenchDriveHighLocked() {
  RelayBenchWriteRelay(true);
  relayBenchRelayHigh = true;
}

static void RelayBenchReleaseLocked(RelayBenchReleaseReason reason, int64_t nowUs) {
  // Latched OFF can only be cancelled by explicit ON/release or a reboot.
  if (relayBenchLatchedOff && reason != RelayBenchReleaseCommand) return;
  RelayBenchDriveHighLocked();
  const bool report = relayBenchBypassActive || reason != RelayBenchReleaseCommand;
  relayBenchBypassActive = false;
  relayBenchLatchedOff = false;
  relayBenchArming = false;
  relayBenchDeadlineUs = 0;
  if (report) {
    relayBenchReleaseReason = reason;
    relayBenchReleasedAtUs = nowUs;
    relayBenchReleasedArmAtUs = relayBenchArmedAtUs;
    relayBenchReleasedCommandId = relayBenchCommandId;
    relayBenchReleasePending = true;
  }
}

static void RelayBenchRelease(RelayBenchReleaseReason reason) {
  if (relayBenchTimer != nullptr) esp_timer_stop(relayBenchTimer);
  const int64_t nowUs = esp_timer_get_time();
  portENTER_CRITICAL(&relayBenchMux);
  RelayBenchReleaseLocked(reason, nowUs);
  portEXIT_CRITICAL(&relayBenchMux);
}

static void RelayBenchDeadlineCallback(void *) {
  const int64_t nowUs = esp_timer_get_time();
  portENTER_CRITICAL(&relayBenchMux);
  // An already queued callback from an older lease cannot end a newer lease.
  if ((relayBenchBypassActive || relayBenchArming) && relayBenchDeadlineUs != 0 &&
      nowUs >= relayBenchDeadlineUs) {
    RelayBenchReleaseLocked(RelayBenchReleaseDeadline, nowUs);
  }
  portEXIT_CRITICAL(&relayBenchMux);
}

static void IRAM_ATTR RelayBenchEnISR() {
  const uint8_t level = gpio_get_level((gpio_num_t)RELAY_BENCH_EN_PIN) ? 1U : 0U;
  const int64_t nowUs = esp_timer_get_time();
  portENTER_CRITICAL_ISR(&relayBenchMux);
  if (level != relayBenchLastEn) {
    relayBenchLastEn = level;
    const uint32_t sequence = ++relayBenchSequence;
    const uint8_t next = static_cast<uint8_t>((relayBenchWrite + 1U) & (RELAY_BENCH_EVENT_CAPACITY - 1U));
    if (next == relayBenchRead) {
      ++relayBenchDropped;
    } else {
      relayBenchEvents[relayBenchWrite] = {nowUs, sequence, level};
      relayBenchWrite = next;
    }
  }
  portEXIT_CRITICAL_ISR(&relayBenchMux);
}

static bool RelayBenchParseDuration(const char *command, uint32_t &durationMs) {
  static const char prefix[] = "bypass:";
  if (strncmp(command, prefix, sizeof(prefix) - 1U) != 0) return false;
  const char *cursor = command + sizeof(prefix) - 1U;
  if (*cursor < '0' || *cursor > '9') return false;
  uint32_t parsed = 0;
  while (*cursor >= '0' && *cursor <= '9') {
    const uint32_t digit = static_cast<uint32_t>(*cursor - '0');
    if (parsed > (UINT32_MAX - digit) / 10U) return false;
    parsed = parsed * 10U + digit;
    ++cursor;
  }
  if (*cursor != '\0' || parsed < 1U || parsed > RELAY_BENCH_MAX_BYPASS_MS) return false;
  durationMs = parsed;
  return true;
}

static bool RelayBenchParseMaintenance(const char *command, uint32_t &durationMs) {
#if RELAY_BENCH_MAINTENANCE_90S
  if (strcmp(command, "flash-bypass:90000") != 0) return false;
  durationMs = RELAY_BENCH_MAINTENANCE_MS;
  return true;
#else
  (void)command;
  (void)durationMs;
  return false;
#endif
}

static bool RelayBenchArm(uint32_t durationMs) {
  const int64_t requestedAtUs = esp_timer_get_time();
  portENTER_CRITICAL(&relayBenchMux);
  if (relayBenchLatchedOff) {
    portEXIT_CRITICAL(&relayBenchMux);
    return false;
  }
  if (relayBenchBypassActive || relayBenchArming) {
    RelayBenchReleaseLocked(RelayBenchReleaseBusy, requestedAtUs);
    portEXIT_CRITICAL(&relayBenchMux);
    if (relayBenchTimer != nullptr) esp_timer_stop(relayBenchTimer);
    return false;
  }
  if (!relayBenchTimerReady) {
    RelayBenchReleaseLocked(RelayBenchReleaseTimerFailure, requestedAtUs);
    portEXIT_CRITICAL(&relayBenchMux);
    return false;
  }
  ++relayBenchCommandId;
  relayBenchArmedAtUs = 0;
  relayBenchDeadlineUs = requestedAtUs + static_cast<int64_t>(durationMs) * 1000LL;
  relayBenchArming = true;
  portEXIT_CRITICAL(&relayBenchMux);

  const int64_t scheduleAtUs = esp_timer_get_time();
  const int64_t remainingUs = relayBenchDeadlineUs - scheduleAtUs;
  if (remainingUs <= 0) {
    RelayBenchRelease(RelayBenchReleaseDeadline);
    return false;
  }
  if (esp_timer_start_once(relayBenchTimer, static_cast<uint64_t>(remainingUs)) != ESP_OK) {
    RelayBenchRelease(RelayBenchReleaseTimerFailure);
    return false;
  }

  // The deadline callback can run while esp_timer_start_once is returning.
  // Commit LOW only while this arm is still current and time remains.
  bool committed = false;
  portENTER_CRITICAL(&relayBenchMux);
  const int64_t commitAtUs = esp_timer_get_time();
  if (relayBenchArming && relayBenchDeadlineUs != 0 && commitAtUs < relayBenchDeadlineUs) {
    RelayBenchWriteRelay(false);
    relayBenchRelayHigh = false;
    relayBenchArmedAtUs = commitAtUs;
    relayBenchArming = false;
    relayBenchBypassActive = true;
    committed = true;
  } else {
    RelayBenchReleaseLocked(RelayBenchReleaseDeadline, commitAtUs);
  }
  portEXIT_CRITICAL(&relayBenchMux);
  if (!committed) esp_timer_stop(relayBenchTimer);
  return committed;
}

static void RelayBenchPrintStatus(const char *type, const char *command) {
  const int64_t nowUs = esp_timer_get_time();
  bool active, relayHigh, timerReady, latched;
  int64_t deadlineUs;
  uint32_t sequence, dropped, commandId;
  uint8_t enLevel;
  portENTER_CRITICAL(&relayBenchMux);
  active = relayBenchBypassActive;
  latched = relayBenchLatchedOff;
  relayHigh = relayBenchRelayHigh;
  deadlineUs = relayBenchDeadlineUs;
  sequence = relayBenchSequence;
  dropped = relayBenchDropped;
  commandId = relayBenchCommandId;
  enLevel = relayBenchLastEn;
  timerReady = relayBenchTimerReady;
  portEXIT_CRITICAL(&relayBenchMux);
  const int64_t remainingUs = active && deadlineUs > nowUs ? deadlineUs - nowUs : 0;
  const TaskSerialStats serial = AppSerial.snapshot();
  AppSerial.printf("RELAY_BENCH marker=%s type=%s command=%s esp_us=%lld relay=%s bypass=%u remaining_ms=%lld en=%u edges=%lu seq=%lu dropped=%lu txdrop=%lu timer_ready=%u id=%lu max_bypass_ms=%lu flash_bypass_ms=%lu mode=%s rxdrop=%lu\n",
    RELAY_BENCH_MARKER, type, command, (long long)nowUs, relayHigh ? "high" : "low", active ? 1U : 0U,
    (long long)((remainingUs + 999LL) / 1000LL), enLevel, (unsigned long)sequence,
    (unsigned long)sequence, (unsigned long)dropped, (unsigned long)serial.droppedBytes,
    timerReady ? 1U : 0U, (unsigned long)commandId,
    (unsigned long)RELAY_BENCH_MAX_BYPASS_MS,
    (unsigned long)(RELAY_BENCH_MAINTENANCE_90S ? RELAY_BENCH_MAINTENANCE_MS : 0U),
    latched ? "off_latched" : active ? "off_timed" : "on", (unsigned long)serial.rxDroppedBytes);
  AppSerial.printf("WDT relay GPIO13=%u esp_us=%lld | ", relayHigh ? 1U : 0U, (long long)nowUs);
  RelayBenchPinJson("status", RELAY_BENCH_RELAY_PIN, relayHigh ? 1U : 0U, nowUs, commandId, "snapshot");
  AppSerial.printf("WDT/EN GPIO33=%u esp_us=%lld | ", enLevel, (long long)nowUs);
  RelayBenchPinJson("status", RELAY_BENCH_EN_PIN, enLevel, nowUs, sequence, "snapshot");
}

static void RelayBenchExecuteCommand(const char *command) {
#if RELAY_BENCH_BLINK_TEST
  const bool blinkReadOnlyCommand = !strcmp(command, "identity") ||
                                    !strcmp(command, "status") ||
                                    !strcmp(command, "function wdt status");
  if (!blinkReadOnlyCommand) relayBenchBlinkTestActive = false;
#endif
#if RELAY_BENCH_LATCHED_OFF
  if (!strcmp(command, "function wdt status")) command = "status";
  if (!strcmp(command, "function wdt on")) command = "on";
  if (!strcmp(command, "function wdt off")) command = "off";
  if (!strncmp(command, "function wdt timed ", 19)) {
    char normalized[64];
    snprintf(normalized, sizeof(normalized), "bypass:%s", command + 19);
    RelayBenchExecuteCommand(normalized);
    return;
  }
  if (!strcmp(command, "identity")) {
#ifndef RELAY_BENCH_HOST_TEST
    uint8_t baseMac[6] = {};
    const bool valid = esp_efuse_mac_get_default(baseMac) == ESP_OK;
    AppSerial.printf("RELAY_ID marker=%s chip_model=%s base_mac=%02x:%02x:%02x:%02x:%02x:%02x mac_type=efuse_base ok=%u\n",
      RELAY_BENCH_MARKER, ESP.getChipModel(), baseMac[0], baseMac[1], baseMac[2], baseMac[3], baseMac[4], baseMac[5], valid ? 1U : 0U);
#endif
    return;
  }
  if (!strcmp(command, "off")) {
    // Mark latched while holding the callback mux before stopping an old timer.
    portENTER_CRITICAL(&relayBenchMux);
    const bool already = relayBenchLatchedOff;
    relayBenchLatchedOff = true;
    relayBenchDeadlineUs = 0;
    relayBenchArming = false;
    relayBenchBypassActive = true;
    relayBenchReleasePending = false;
    if (!already) { ++relayBenchCommandId; relayBenchArmedAtUs = esp_timer_get_time(); }
    RelayBenchWriteRelay(false);
    relayBenchRelayHigh = false;
    portEXIT_CRITICAL(&relayBenchMux);
    if (relayBenchTimer != nullptr) esp_timer_stop(relayBenchTimer);
    AppSerial.printf("RELAY_BENCH marker=%s type=response command=off ok=1 relay=low bypass=1 mode=off_latched remaining_ms=0 id=%lu esp_us=%lld\n",
      RELAY_BENCH_MARKER, (unsigned long)relayBenchCommandId, (long long)esp_timer_get_time());
    AppSerial.printf("WDT relay GPIO13=0 command=off | ");
    RelayBenchPinJson("command", RELAY_BENCH_RELAY_PIN, 0, esp_timer_get_time(), relayBenchCommandId, "off");
    return;
  }
  if (!strcmp(command, "on")) {
    RelayBenchRelease(RelayBenchReleaseCommand);
    AppSerial.printf("RELAY_BENCH marker=%s type=response command=on ok=1 relay=high bypass=0 mode=on id=%lu esp_us=%lld\n",
      RELAY_BENCH_MARKER, (unsigned long)relayBenchCommandId, (long long)esp_timer_get_time());
    return;
  }
#endif
  if (!strcmp(command, "help")) {
#if RELAY_BENCH_LATCHED_OFF
    AppSerial.printf("RELAY_BENCH marker=%s type=response command=help ok=1 commands=off,on,bypass:<1-5000ms>,release,status reboot=on persistence=none\n", RELAY_BENCH_MARKER);
#elif RELAY_BENCH_MAINTENANCE_90S
    AppSerial.printf("RELAY_BENCH marker=%s type=response command=help ok=1 commands=bypass:<1-5000ms>,flash-bypass:90000,release,status\n", RELAY_BENCH_MARKER);
#else
    AppSerial.printf("RELAY_BENCH marker=%s type=response command=help ok=1 commands=bypass:<1-5000ms>,release,status\n", RELAY_BENCH_MARKER);
#endif
    return;
  }
  if (!strcmp(command, "status")) {
    RelayBenchPrintStatus("response", "status");
    return;
  }
  if (!strcmp(command, "release")) {
    RelayBenchRelease(RelayBenchReleaseCommand);
    AppSerial.printf("RELAY_BENCH marker=%s type=response command=release ok=1 relay=high bypass=0\n", RELAY_BENCH_MARKER);
    return;
  }
  uint32_t durationMs = 0;
  if (relayBenchLatchedOff) {
    AppSerial.printf("RELAY_BENCH marker=%s type=response command=invalid ok=0 reason=latched_off relay=low bypass=1 mode=off_latched\n", RELAY_BENCH_MARKER);
    return;
  }
  const bool maintenance = RelayBenchParseMaintenance(command, durationMs);
  if (!maintenance && !RelayBenchParseDuration(command, durationMs)) {
    RelayBenchRelease(RelayBenchReleaseMalformed);
    AppSerial.printf("RELAY_BENCH marker=%s type=response command=invalid ok=0 reason=malformed relay=high bypass=0\n", RELAY_BENCH_MARKER);
    return;
  }
  const char *responseCommand = maintenance ? "flash-bypass" : "bypass";
  const bool armed = RelayBenchArm(durationMs);
  if (armed) {
    AppSerial.printf("RELAY_BENCH marker=%s type=response command=%s ok=1 duration_ms=%lu esp_us=%lld id=%lu relay=low\n",
      RELAY_BENCH_MARKER, responseCommand, (unsigned long)durationMs, (long long)relayBenchArmedAtUs,
      (unsigned long)relayBenchCommandId);
    AppSerial.printf("WDT relay GPIO13=0 command=%s | ", responseCommand);
    RelayBenchPinJson("command", RELAY_BENCH_RELAY_PIN, 0, relayBenchArmedAtUs, relayBenchCommandId, responseCommand);
  } else {
    AppSerial.printf("RELAY_BENCH marker=%s type=response command=%s ok=0 reason=%s relay=high bypass=0\n",
      RELAY_BENCH_MARKER, responseCommand, RelayBenchReleaseReasonName(relayBenchReleaseReason));
  }
}

static void RelayBenchRxFailure(RelayBenchReleaseReason reason) {
  relayBenchLineLength = 0;
  relayBenchDiscardLine = true;
  RelayBenchRelease(reason);
  AppSerial.printf("RELAY_BENCH marker=%s type=response command=invalid ok=0 reason=%s relay=%s bypass=%u\n",
    RELAY_BENCH_MARKER, RelayBenchReleaseReasonName(reason), relayBenchRelayHigh ? "high" : "low", relayBenchBypassActive ? 1U : 0U);
}

static void RelayBenchPollSerial() {
  const TaskSerialStats before = AppSerial.snapshot();
  if (before.rxDroppedBytes != relayBenchObservedRxDropped) {
    relayBenchObservedRxDropped = before.rxDroppedBytes;
    RelayBenchRxFailure(RelayBenchReleaseRxOverflow);
  }
  for (unsigned count = 0; count < 128U && AppSerial.available() > 0; ++count) {
    const int raw = AppSerial.read();
    if (raw == -2) {
      RelayBenchRxFailure(RelayBenchReleaseRxOverflow);
      continue;
    }
    if (raw < 0) break;
    const char c = static_cast<char>(raw);
    if (c == '\r' || c == '\n') {
      if (!relayBenchDiscardLine && relayBenchLineLength != 0) {
        relayBenchLine[relayBenchLineLength] = '\0';
        RelayBenchExecuteCommand(relayBenchLine);
      }
      relayBenchLineLength = 0;
      relayBenchDiscardLine = false;
      continue;
    }
    if (relayBenchDiscardLine) continue;
    if (raw < 0x20 || raw > 0x7e || relayBenchLineLength >= sizeof(relayBenchLine) - 1U) {
      RelayBenchRxFailure(RelayBenchReleaseMalformed);
      continue;
    }
    relayBenchLine[relayBenchLineLength++] = c;
  }
}

static void RelayBenchReportRelease() {
  bool pending;
  RelayBenchReleaseReason reason;
  int64_t atUs, armAtUs;
  uint32_t commandId;
  portENTER_CRITICAL(&relayBenchMux);
  pending = relayBenchReleasePending;
  reason = relayBenchReleaseReason;
  atUs = relayBenchReleasedAtUs;
  armAtUs = relayBenchReleasedArmAtUs;
  commandId = relayBenchReleasedCommandId;
  relayBenchReleasePending = false;
  portEXIT_CRITICAL(&relayBenchMux);
  if (pending) AppSerial.printf("RELAY_BENCH marker=%s type=release reason=%s esp_us=%lld arm_esp_us=%lld id=%lu relay=high bypass=0\n",
    RELAY_BENCH_MARKER, RelayBenchReleaseReasonName(reason), (long long)atUs,
    (long long)armAtUs, (unsigned long)commandId);
  if (pending) {
    AppSerial.printf("WDT relay GPIO13=1 reason=%s esp_us=%lld | ", RelayBenchReleaseReasonName(reason), (long long)atUs);
    RelayBenchPinJson("release", RELAY_BENCH_RELAY_PIN, 1, atUs, commandId, RelayBenchReleaseReasonName(reason));
  }
}

static void RelayBenchDrainEdges() {
  for (unsigned count = 0; count < 8U; ++count) {
    RelayBenchEdge event;
    bool available;
    portENTER_CRITICAL(&relayBenchMux);
    available = relayBenchRead != relayBenchWrite;
    if (available) {
      event = relayBenchEvents[relayBenchRead];
      relayBenchRead = static_cast<uint8_t>((relayBenchRead + 1U) & (RELAY_BENCH_EVENT_CAPACITY - 1U));
    }
    portEXIT_CRITICAL(&relayBenchMux);
    if (!available) break;
    AppSerial.printf("RELAY_BENCH marker=%s type=edge esp_us=%lld en=%u seq=%lu | ",
      RELAY_BENCH_MARKER, (long long)event.atUs, event.level, (unsigned long)event.sequence);
    RelayBenchPinJson("edge", RELAY_BENCH_EN_PIN, event.level, event.atUs, event.sequence, "observed");
  }
}

#if RELAY_BENCH_BLINK_TEST
static void RelayBenchMonitorEnChanges() {
  static uint32_t lastSampleMs = 0;
  static uint8_t previousLevel = 0;
  static uint8_t candidateLevel = 0;
  static uint8_t candidateSamples = 0;
  static bool initialized = false;
  const uint32_t nowMs = millis();
  if (static_cast<uint32_t>(nowMs - lastSampleMs) < 10U) return;
  lastSampleMs = nowMs;
  const uint8_t currentLevel = gpio_get_level((gpio_num_t)RELAY_BENCH_EN_PIN) ? 1U : 0U;
  if (!initialized) {
    previousLevel = currentLevel;
    candidateLevel = currentLevel;
    initialized = true;
    return;
  }
  if (currentLevel != candidateLevel) {
    candidateLevel = currentLevel;
    candidateSamples = 1U;
    return;
  }
  if (candidateSamples < 3U) ++candidateSamples;
  if (candidateSamples < 3U || currentLevel == previousLevel) return;

  relayBenchChanges[relayBenchChangeWrite] = {
    esp_timer_get_time(), previousLevel, currentLevel};
  relayBenchChangeWrite = static_cast<uint8_t>(
    (relayBenchChangeWrite + 1U) % RELAY_BENCH_CHANGE_HISTORY);
  if (relayBenchChangeCount < RELAY_BENCH_CHANGE_HISTORY) ++relayBenchChangeCount;
  previousLevel = currentLevel;

  const RelayBenchPinChange &latest = relayBenchChanges[
    (relayBenchChangeWrite + RELAY_BENCH_CHANGE_HISTORY - 1U) % RELAY_BENCH_CHANGE_HISTORY];
  AppSerial.printf("WDT/EN GPIO33 %u -> %u esp_us=%lld | ", latest.from, latest.to, (long long)latest.atUs);
  RelayBenchPinJson("edge", RELAY_BENCH_EN_PIN, latest.to, latest.atUs, ++relayBenchSequence, "filtered");

  AppSerial.printf("RELAY_BENCH marker=%s type=pin_history gpio=33 rows=%u\n",
    RELAY_BENCH_MARKER, static_cast<unsigned>(relayBenchChangeCount));
  AppSerial.printf("RELAY_BENCH gpio=33 columns=index,esp_us,from,to\n");
  const uint8_t first = relayBenchChangeCount == RELAY_BENCH_CHANGE_HISTORY
    ? relayBenchChangeWrite : 0U;
  for (uint8_t row = 0; row < relayBenchChangeCount; ++row) {
    const uint8_t index = static_cast<uint8_t>(
      (first + row) % RELAY_BENCH_CHANGE_HISTORY);
    const RelayBenchPinChange &change = relayBenchChanges[index];
    AppSerial.printf("RELAY_BENCH gpio=33 row=%u esp_us=%lld from=%u to=%u\n",
      static_cast<unsigned>(row + 1U), (long long)change.atUs,
      change.from, change.to);
  }
}
#endif

static void RelayBenchSetup() {
  // Set the requested boot level before enabling the relay output.
#if RELAY_BENCH_START_LOW
  digitalWrite(RELAY_BENCH_RELAY_PIN, LOW);
#else
  digitalWrite(RELAY_BENCH_RELAY_PIN, HIGH);
#endif
  pinMode(RELAY_BENCH_RELAY_PIN, OUTPUT);
  pinMode(RELAY_BENCH_EN_PIN, INPUT);
  const bool startHigh = RELAY_BENCH_START_LOW == 0;
  gpio_set_level((gpio_num_t)RELAY_BENCH_RELAY_PIN, startHigh ? 1 : 0);
  relayBenchRelayHigh = startHigh;
  relayBenchBypassActive = !startHigh;
  relayBenchLatchedOff = !startHigh;
  relayBenchBlinkTestActive = RELAY_BENCH_BLINK_TEST != 0;
  relayBenchArming = false;
  relayBenchDeadlineUs = 0;
  relayBenchLastEn = gpio_get_level((gpio_num_t)RELAY_BENCH_EN_PIN) ? 1U : 0U;
  const esp_timer_create_args_t timerArgs = {
    RelayBenchDeadlineCallback, nullptr, ESP_TIMER_TASK, "relay13_deadline", true};
  relayBenchTimerReady = esp_timer_create(&timerArgs, &relayBenchTimer) == ESP_OK;
  if (!relayBenchTimerReady) RelayBenchRelease(RelayBenchReleaseTimerFailure);
#if RELAY_BENCH_BLINK_TEST
  for (uint8_t click = 0; click < 2U; ++click) {
    RelayBenchWriteRelay(true);
    relayBenchRelayHigh = true;
    AppSerial.printf("RELAY_BENCH marker=%s type=start_click gpio=13 level=1 n=%u esp_us=%lld\n",
      RELAY_BENCH_MARKER, static_cast<unsigned>(click + 1U), (long long)esp_timer_get_time());
    delay(250);
    RelayBenchWriteRelay(false);
    relayBenchRelayHigh = false;
    AppSerial.printf("RELAY_BENCH marker=%s type=start_click gpio=13 level=0 n=%u esp_us=%lld\n",
      RELAY_BENCH_MARKER, static_cast<unsigned>(click + 1U), (long long)esp_timer_get_time());
    delay(250);
  }
  relayBenchBypassActive = true;
  relayBenchLatchedOff = true;
  relayBenchBlinkTestActive = false;
#endif
#if !RELAY_BENCH_BLINK_TEST
  attachInterrupt(digitalPinToInterrupt(RELAY_BENCH_EN_PIN), RelayBenchEnISR, CHANGE);
  RelayBenchEnISR();
#endif
  AppSerial.printf("RELAY_BENCH marker=%s type=boot relay_gpio=13 en_gpio=33 relay=%s bypass=%u timer_ready=%u en=%u mode=%s\n",
    RELAY_BENCH_MARKER, relayBenchRelayHigh ? "high" : "low", relayBenchBypassActive ? 1U : 0U,
    relayBenchTimerReady ? 1U : 0U, relayBenchLastEn,
    relayBenchLatchedOff ? "off_latched" : relayBenchBypassActive ? "off_timed" : "on");
  AppSerial.printf("WDT relay GPIO13=%u boot | ", relayBenchRelayHigh ? 1U : 0U);
  RelayBenchPinJson("boot", RELAY_BENCH_RELAY_PIN, relayBenchRelayHigh ? 1U : 0U,
    esp_timer_get_time(), relayBenchCommandId, "startup");
}

static void RelayBenchLoop() {
#if RELAY_BENCH_BLINK_TEST
  RelayBenchMonitorEnChanges();
#endif
#if RELAY_BENCH_BLINK_TEST
  static uint32_t lastBlinkMs = 0;
  static bool blinkHigh = false;
  const uint32_t blinkNowMs = millis();
  if (relayBenchBlinkTestActive) {
    RelayBenchPollSerial();
  }
  if (relayBenchBlinkTestActive && static_cast<uint32_t>(blinkNowMs - lastBlinkMs) >= 500U) {
    lastBlinkMs = blinkNowMs;
    blinkHigh = !blinkHigh;
    RelayBenchWriteRelay(blinkHigh);
  }
  if (relayBenchBlinkTestActive) return;
#endif
  RelayBenchPollSerial();
  // Secondary deadline guard; the esp_timer callback remains authoritative.
  const int64_t nowUs = esp_timer_get_time();
  portENTER_CRITICAL(&relayBenchMux);
  if (relayBenchBypassActive && relayBenchDeadlineUs != 0 && nowUs >= relayBenchDeadlineUs) {
    RelayBenchReleaseLocked(RelayBenchReleaseDeadline, nowUs);
  }
  portEXIT_CRITICAL(&relayBenchMux);
  RelayBenchReportRelease();
  RelayBenchDrainEdges();
  static uint32_t lastStatusMs = 0;
  const uint32_t nowMs = millis();
  if (static_cast<uint32_t>(nowMs - lastStatusMs) >= 1000U) {
    lastStatusMs = nowMs;
    RelayBenchPrintStatus("status", "periodic");
  }
}
