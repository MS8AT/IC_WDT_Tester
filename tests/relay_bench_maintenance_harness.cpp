#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include <deque>
#include <string>

#define RELAY_BENCH_HOST_TEST 1
#define RELAY_BENCH_MAINTENANCE_90S 1
#define IRAM_ATTR
#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define INPUT 2
#define CHANGE 3
#define ESP_OK 0
#define ESP_TIMER_TASK 0
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL(x) ((void)(x))
#define portEXIT_CRITICAL(x) ((void)(x))
#define portENTER_CRITICAL_ISR(x) ((void)(x))
#define portEXIT_CRITICAL_ISR(x) ((void)(x))

using portMUX_TYPE = int;
using gpio_num_t = int;
using esp_timer_handle_t = void *;
using esp_timer_cb_t = void (*)(void *);
struct esp_timer_create_args_t { esp_timer_cb_t callback; void *arg; int dispatch; const char *name; bool skip; };
struct TaskSerialStats {
  uint32_t acceptedBytes = 0, transmittedBytes = 0, droppedBytes = 0;
  uint32_t commandDroppedBytes = 0, startFailures = 0, flushTimeouts = 0;
  size_t queuedBytes = 0; bool ready = true;
  uint32_t receivedBytes = 0, rxDroppedBytes = 0, commandSuppressedBytes = 0, workerPasses = 0;
};
struct FakeSerial {
  std::string output; std::deque<int> input; TaskSerialStats stats;
  TaskSerialStats snapshot() { return stats; }
  int available() { return static_cast<int>(input.size()); }
  int read() { int value = input.front(); input.pop_front(); return value; }
  void push(const char *text) { while (*text) input.push_back(*text++); }
  void printf(const char *format, ...) {
    char buffer[512]; va_list args; va_start(args, format);
    const int count = vsnprintf(buffer, sizeof(buffer), format, args); va_end(args);
    assert(count >= 0 && count < static_cast<int>(sizeof(buffer))); output += buffer;
  }
} AppSerial;

static int64_t fakeNowUs = 0; static uint32_t fakeNowMs = 0;
static int fakeRelayLevel = 1, fakeEnLevel = 1; static bool fakeTimerStartFail = false;
static bool fakeTimerRunning = false, fakeTimerStartSawLow = false;
static uint64_t fakeTimerRequestedUs = 0; static esp_timer_cb_t fakeTimerCallback = nullptr;
int64_t esp_timer_get_time() { return fakeNowUs; }
uint32_t millis() { return fakeNowMs; }
int gpio_get_level(gpio_num_t pin) { assert(pin == 33); return fakeEnLevel; }
int gpio_set_level(gpio_num_t pin, int level) { assert(pin == 13); fakeRelayLevel = level; return ESP_OK; }
void digitalWrite(int pin, int level) { assert(pin == 13); fakeRelayLevel = level; }
void pinMode(int pin, int mode) { assert((pin == 13 && mode == OUTPUT) || (pin == 33 && mode == INPUT)); }
int digitalPinToInterrupt(int pin) { return pin; }
void attachInterrupt(int pin, void (*)(), int mode) { assert(pin == 33 && mode == CHANGE); }
int esp_timer_create(const esp_timer_create_args_t *args, esp_timer_handle_t *handle) {
  fakeTimerCallback = args->callback; *handle = reinterpret_cast<void *>(1); return ESP_OK;
}
int esp_timer_start_once(esp_timer_handle_t handle, uint64_t timeoutUs) {
  assert(handle); fakeTimerStartSawLow = fakeRelayLevel == 0; fakeTimerRequestedUs = timeoutUs;
  if (fakeTimerStartFail) return -1;
  fakeTimerRunning = true;
  return ESP_OK;
}
int esp_timer_stop(esp_timer_handle_t) { fakeTimerRunning = false; return ESP_OK; }

#include "../src/RelayResetBench.h"

static void assertReleased() {
  assert(fakeRelayLevel == 1 && relayBenchRelayHigh && !relayBenchBypassActive);
  assert(relayBenchDeadlineUs == 0);
}

int main() {
  RelayBenchSetup();
  assertReleased();
  assert(strcmp(RELAY_BENCH_MARKER, "RELAY13-EN33-MAINT90-01") == 0);
  uint32_t duration = 0;
  assert(RelayBenchParseDuration("bypass:5000", duration) && duration == 5000);
  assert(!RelayBenchParseDuration("bypass:5001", duration));
  assert(!RelayBenchParseDuration("bypass:90000", duration));
  assert(RelayBenchParseMaintenance("flash-bypass:90000", duration) && duration == 90000);
  assert(!RelayBenchParseMaintenance("flash-bypass:89999", duration));
  assert(!RelayBenchParseMaintenance("flash-bypass:90001", duration));
  assert(!RelayBenchParseMaintenance("flash-bypass:090000", duration));

  fakeNowUs = 1000000;
  RelayBenchExecuteCommand("flash-bypass:90000");
  assert(relayBenchBypassActive && fakeRelayLevel == 0 && fakeTimerRunning);
  assert(!fakeTimerStartSawLow && fakeTimerRequestedUs == 90000000ULL);
  assert(relayBenchDeadlineUs == 91000000);
  assert(AppSerial.output.find("command=flash-bypass ok=1 duration_ms=90000") != std::string::npos);

  // No renewal while active: busy always returns HIGH.
  RelayBenchExecuteCommand("flash-bypass:90000");
  assertReleased();
  assert(relayBenchReleaseReason == RelayBenchReleaseBusy);

  // Malformed maintenance forms fail safe and cannot use the long deadline.
  fakeNowUs = 2000000;
  assert(RelayBenchArm(5000));
  RelayBenchExecuteCommand("flash-bypass:90001");
  assertReleased();
  assert(relayBenchReleaseReason == RelayBenchReleaseMalformed);

  // Explicit release preserves the existing safe path.
  fakeNowUs = 3000000;
  RelayBenchExecuteCommand("flash-bypass:90000");
  assert(relayBenchBypassActive);
  RelayBenchExecuteCommand("release");
  assertReleased();

  // Timer start failure happens before LOW and forces HIGH.
  fakeTimerStartFail = true; fakeTimerStartSawLow = false; fakeNowUs = 4000000;
  RelayBenchExecuteCommand("flash-bypass:90000");
  assertReleased(); assert(!fakeTimerStartSawLow);
  assert(relayBenchReleaseReason == RelayBenchReleaseTimerFailure);
  fakeTimerStartFail = false;

  // Independent timer callback expires exactly the committed 90-second lease.
  fakeNowUs = 5000000;
  RelayBenchExecuteCommand("flash-bypass:90000");
  assert(relayBenchBypassActive);
  fakeNowUs = 94999999; fakeTimerCallback(nullptr);
  assert(relayBenchBypassActive && fakeRelayLevel == 0);
  fakeNowUs = 95000000; fakeTimerCallback(nullptr);
  assertReleased(); assert(relayBenchReleaseReason == RelayBenchReleaseDeadline);

  RelayBenchExecuteCommand("status");
  assert(AppSerial.output.find("max_bypass_ms=5000 flash_bypass_ms=90000") != std::string::npos);
  fakeNowMs = 1000;
  RelayBenchLoop();
  puts("relay bench maintenance scenarios PASS");
  return 0;
}
