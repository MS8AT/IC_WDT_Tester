#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include <deque>
#include <string>

#define RELAY_BENCH_HOST_TEST 1
#define IRAM_ATTR
#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define INPUT 2
#define CHANGE 3
#define ESP_OK 0
#define ESP_TIMER_TASK 0
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL(x) (fakeEnterCritical(), (void)(x))
#define portEXIT_CRITICAL(x) ((void)(x))
#define portENTER_CRITICAL_ISR(x) ((void)(x))
#define portEXIT_CRITICAL_ISR(x) ((void)(x))

using portMUX_TYPE = int;
static void fakeEnterCritical();
using gpio_num_t = int;
using esp_timer_handle_t = void *;
using esp_timer_cb_t = void (*)(void *);
struct esp_timer_create_args_t {
  esp_timer_cb_t callback;
  void *arg;
  int dispatch;
  const char *name;
  bool skip;
};

struct TaskSerialStats {
  uint32_t acceptedBytes = 0, transmittedBytes = 0, droppedBytes = 0;
  uint32_t commandDroppedBytes = 0, startFailures = 0, flushTimeouts = 0;
  size_t queuedBytes = 0;
  bool ready = true;
  uint32_t receivedBytes = 0, rxDroppedBytes = 0, commandSuppressedBytes = 0, workerPasses = 0;
};

struct FakeSerial {
  std::string output;
  std::deque<int> input;
  TaskSerialStats stats;
  TaskSerialStats snapshot() { return stats; }
  int available() { return static_cast<int>(input.size()); }
  int read() { int value = input.front(); input.pop_front(); return value; }
  void push(const char *text) { while (*text) input.push_back(*text++); }
  void printf(const char *format, ...) {
    char buffer[512];
    va_list args;
    va_start(args, format);
    const int count = vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);
    assert(count >= 0 && count < static_cast<int>(sizeof(buffer)));
    output += buffer;
  }
} AppSerial;

static int64_t fakeNowUs = 0;
static uint32_t fakeNowMs = 0;
static int fakeRelayLevel = 1;
static int fakeEnLevel = 1;
static bool fakeRelayOutput = false;
static bool fakeSafeOutputOrder = false;
static unsigned fakeRelayWrites = 0;
static unsigned fakeInputModes = 0;
static unsigned fakeInterrupts = 0;
static bool fakeTimerCreateFail = false;
static bool fakeTimerStartFail = false;
static bool fakeTimerRunning = false;
static bool fakeTimerStartSawLow = false;
static bool fakeFireCallbackDuringStart = false;
static int64_t fakeTimerStartAdvanceUs = 0;
static uint64_t fakeTimerRequestedUs = 0;
static int64_t fakeArmCommitCriticalAdvanceUs = 0;
static int64_t fakeAdvanceOnNextCriticalEnterUs = 0;
static esp_timer_cb_t fakeTimerCallback = nullptr;

static void fakeEnterCritical() {
  fakeNowUs += fakeAdvanceOnNextCriticalEnterUs;
  fakeAdvanceOnNextCriticalEnterUs = 0;
}

int64_t esp_timer_get_time() { return fakeNowUs; }
uint32_t millis() { return fakeNowMs; }
int gpio_get_level(gpio_num_t pin) { assert(pin == 33); return fakeEnLevel; }
int gpio_set_level(gpio_num_t pin, int level) {
  assert(pin == 13 && (level == 0 || level == 1));
  fakeRelayLevel = level;
  ++fakeRelayWrites;
  return ESP_OK;
}
void digitalWrite(int pin, int level) { assert(pin == 13); fakeRelayLevel = level; ++fakeRelayWrites; }
void pinMode(int pin, int mode) {
  if (pin == 13) {
    assert(mode == OUTPUT);
    fakeSafeOutputOrder = fakeRelayLevel == 1;
    fakeRelayOutput = true;
  } else {
    assert(pin == 33 && mode == INPUT);
    ++fakeInputModes;
  }
}
int digitalPinToInterrupt(int pin) { assert(pin == 33); return pin; }
void attachInterrupt(int pin, void (*)(), int mode) { assert(pin == 33 && mode == CHANGE); ++fakeInterrupts; }
int esp_timer_create(const esp_timer_create_args_t *args, esp_timer_handle_t *handle) {
  if (fakeTimerCreateFail) return -1;
  fakeTimerCallback = args->callback;
  *handle = reinterpret_cast<void *>(1);
  return ESP_OK;
}
int esp_timer_start_once(esp_timer_handle_t handle, uint64_t timeoutUs) {
  assert(handle != nullptr);
  fakeTimerStartSawLow = fakeRelayLevel == 0;
  fakeTimerRequestedUs = timeoutUs;
  fakeNowUs += fakeTimerStartAdvanceUs;
  if (fakeFireCallbackDuringStart) fakeTimerCallback(nullptr);
  if (fakeTimerStartFail) return -1;
  fakeTimerRunning = true;
  fakeAdvanceOnNextCriticalEnterUs = fakeArmCommitCriticalAdvanceUs;
  return ESP_OK;
}
int esp_timer_stop(esp_timer_handle_t) { fakeTimerRunning = false; return ESP_OK; }

#include "../src/RelayResetBench.h"

static void assertReleased() {
  assert(fakeRelayLevel == 1);
  assert(relayBenchRelayHigh);
  assert(!relayBenchBypassActive);
  assert(relayBenchDeadlineUs == 0);
}

int legacyMain() {
  RelayBenchSetup();
  assert(fakeSafeOutputOrder && fakeRelayOutput);
  assert(fakeInputModes == 1 && fakeInterrupts == 1);
  assertReleased();
  assert(fakeTimerCallback != nullptr && relayBenchTimerReady);
  assert(AppSerial.output.find("marker=RELAY13-EN33-01 type=boot") != std::string::npos);

  uint32_t duration = 0;
  assert(RelayBenchParseDuration("bypass:1", duration) && duration == 1);
  assert(RelayBenchParseDuration("bypass:5000", duration) && duration == 5000);
  const char *invalid[] = {"bypass:0", "bypass:5001", "bypass:-1", "bypass:",
                           "bypass:1x", "bypass:42949672960", " bypass:1"};
  for (const char *value : invalid) assert(!RelayBenchParseDuration(value, duration));

  fakeNowUs = 1000;
  assert(RelayBenchArm(100));
  assert(fakeRelayLevel == 0 && relayBenchBypassActive && fakeTimerRunning);
  const unsigned writesBeforeIsr = fakeRelayWrites;
  fakeEnLevel = 0;
  fakeNowUs = 1100;
  RelayBenchEnISR();
  assert(fakeRelayWrites == writesBeforeIsr);
  assert(relayBenchSequence == 1 && relayBenchEvents[0].atUs == 1100 && relayBenchEvents[0].level == 0);

  // A second arm never renews an active lease and fails safe HIGH.
  assert(!RelayBenchArm(200));
  assertReleased();
  assert(relayBenchReleaseReason == RelayBenchReleaseBusy);

  fakeNowUs = 2000;
  assert(RelayBenchArm(500));
  fakeNowUs = 499999;  // A stale/early callback cannot stop the current lease.
  fakeTimerCallback(nullptr);
  assert(relayBenchBypassActive && fakeRelayLevel == 0);
  fakeNowUs = 502000;
  fakeTimerCallback(nullptr);
  assertReleased();
  assert(relayBenchReleaseReason == RelayBenchReleaseDeadline);

  fakeTimerStartFail = true;
  fakeNowUs = 600000;
  assert(!RelayBenchArm(10));
  assertReleased();
  assert(!fakeTimerStartSawLow); // Timer failure can never strand relay LOW.
  assert(relayBenchReleaseReason == RelayBenchReleaseTimerFailure);
  fakeTimerStartFail = false;
  relayBenchTimerReady = false;
  assert(!RelayBenchArm(10));
  assertReleased();
  assert(relayBenchReleaseReason == RelayBenchReleaseTimerFailure);
  relayBenchTimerReady = true;

  // Timer scheduling delay consumes the original lease; it never extends it.
  fakeNowUs = 700000;
  fakeTimerStartAdvanceUs = 500;
  assert(RelayBenchArm(1));
  assert(!fakeTimerStartSawLow && fakeTimerRequestedUs == 1000);
  assert(relayBenchArmedAtUs == 700500 && relayBenchDeadlineUs == 701000);
  const uint32_t delayedArmId = relayBenchCommandId;
  fakeNowUs = 701000;
  fakeTimerCallback(nullptr);
  assertReleased();
  RelayBenchReportRelease();
  assert(AppSerial.output.find("type=release reason=deadline") != std::string::npos);
  assert(AppSerial.output.find("arm_esp_us=700500") != std::string::npos);
  char expectedReleaseId[32];
  snprintf(expectedReleaseId, sizeof(expectedReleaseId), "id=%lu relay=high", (unsigned long)delayedArmId);
  assert(AppSerial.output.find(expectedReleaseId) != std::string::npos);

  // Deterministic preemption: callback expires the pending arm before LOW commit.
  fakeNowUs = 800000;
  fakeTimerStartAdvanceUs = 1000;
  fakeFireCallbackDuringStart = true;
  assert(!RelayBenchArm(1));
  assertReleased();
  assert(!fakeTimerStartSawLow);
  fakeTimerStartAdvanceUs = 0;
  fakeFireCallbackDuringStart = false;

  // Preemption immediately before commit must be observed inside the mux.
  fakeNowUs = 900000;
  fakeArmCommitCriticalAdvanceUs = 1100;
  assert(!RelayBenchArm(1));
  assertReleased();
  assert(!fakeTimerStartSawLow);
  fakeArmCommitCriticalAdvanceUs = 0;

  // Invalid and overlong frames release immediately and never execute a prefix.
  assert(RelayBenchArm(100));
  AppSerial.push("bypass:0\n");
  RelayBenchPollSerial();
  assertReleased();
  assert(AppSerial.output.find("reason=malformed") != std::string::npos);
  assert(RelayBenchArm(100));
  std::string longLine(80, 'x');
  longLine += "\n";
  AppSerial.push(longLine.c_str());
  RelayBenchPollSerial();
  assertReleased();
  assert(!relayBenchDiscardLine);

  assert(RelayBenchArm(100));
  AppSerial.stats.rxDroppedBytes++;
  RelayBenchPollSerial();
  assertReleased();
  assert(relayBenchReleaseReason == RelayBenchReleaseRxOverflow);

  // Saturating the edge ring reports loss without touching GPIO13.
  relayBenchRead = relayBenchWrite = 0;
  relayBenchSequence = relayBenchDropped = 0;
  relayBenchLastEn = fakeEnLevel;
  const unsigned relayWritesBeforeFlood = fakeRelayWrites;
  for (unsigned i = 0; i < 300; ++i) {
    fakeEnLevel ^= 1;
    ++fakeNowUs;
    RelayBenchEnISR();
  }
  assert(relayBenchSequence == 300 && relayBenchDropped == 173);
  assert(fakeRelayWrites == relayWritesBeforeFlood);
  // Queue/UART pressure cannot prevent the independent deadline release.
  fakeNowUs += 1000;
  assert(RelayBenchArm(1));
  fakeNowUs += 1000;
  fakeTimerCallback(nullptr);
  assertReleased();

  RelayBenchExecuteCommand("status");
  RelayBenchExecuteCommand("help");
  RelayBenchExecuteCommand("release");
  fakeNowMs = 1000;
  RelayBenchLoop();
  assert(AppSerial.output.find("type=response command=help ok=1") != std::string::npos);
  assert(AppSerial.output.find("type=response command=release ok=1") != std::string::npos);
  assert(AppSerial.output.find("esp_us=") != std::string::npos);
  assert(AppSerial.output.find("command=status") != std::string::npos);
  assert(AppSerial.output.find("edges=") != std::string::npos);
  assert(AppSerial.output.find("txdrop=") != std::string::npos);

  puts("relay bench host scenarios PASS");
  return 0;
}

#ifndef RELAY_TEST_LATCHED
int main() { return legacyMain(); }
#endif
