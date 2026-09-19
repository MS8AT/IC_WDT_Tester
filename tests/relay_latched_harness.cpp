#define RELAY_BENCH_LATCHED_OFF 1
#define RELAY_TEST_LATCHED 1
#include "relay_bench_harness.cpp"

static void assertLatched() {
  assert(fakeRelayLevel == 0 && !relayBenchRelayHigh);
  assert(relayBenchLatchedOff && relayBenchBypassActive);
  assert(relayBenchDeadlineUs == 0 && !fakeTimerRunning);
}

int main() {
  RelayBenchSetup();
  assertReleased();
  RelayBenchExecuteCommand("function wdt off");
  assertLatched();
  const uint32_t id = relayBenchCommandId;
  RelayBenchExecuteCommand("off");
  assert(relayBenchCommandId == id);
  fakeNowUs += 100000000000LL; // Far beyond both 5 seconds and 90 seconds.
  fakeTimerCallback(nullptr);
  RelayBenchLoop();
  assertLatched();
  for (const char *cmd : {"garbage", "bypass:1000", "bypass:0", "flash-bypass:90000", "help", "status"}) {
    RelayBenchExecuteCommand(cmd);
    assertLatched();
  }
  AppSerial.push("on\x01\n");
  RelayBenchPollSerial();
  assertLatched();
  std::string overflow(80, 'x'); overflow += "on\n";
  AppSerial.push(overflow.c_str()); RelayBenchPollSerial(); assertLatched();
  AppSerial.stats.rxDroppedBytes++;
  AppSerial.push("on\n"); RelayBenchPollSerial(); assertLatched();
  AppSerial.input.push_back(-2); AppSerial.push("on\n");
  RelayBenchPollSerial(); assertLatched();
  assert(AppSerial.output.find("mode=off_latched") != std::string::npos);
  assert(AppSerial.output.find("reason=rx_overflow relay=low bypass=1") != std::string::npos);
  RelayBenchExecuteCommand("function wdt on"); assertReleased();
  assert(!relayBenchLatchedOff);
  for (uint32_t ms : {1U, 1500U, 5000U}) {
    assert(RelayBenchArm(ms));
    assert(!relayBenchLatchedOff && fakeRelayLevel == 0);
    fakeNowUs += ms * 1000LL;
    fakeTimerCallback(nullptr); assertReleased();
  }
  RelayBenchExecuteCommand("function wdt timed 1500");
  assert(fakeTimerRunning && fakeRelayLevel == 0);
  const int64_t oldDeadline = relayBenchDeadlineUs;
  RelayBenchExecuteCommand("off"); assertLatched();
  fakeNowUs = oldDeadline + 1;
  fakeTimerCallback(nullptr); RelayBenchLoop(); assertLatched();
  relayBenchTimerReady = false;
  assert(!RelayBenchArm(1500)); assertLatched();
  RelayBenchExecuteCommand("on"); assertReleased();
  relayBenchTimerReady = true;
  RelayBenchExecuteCommand("off"); assertLatched();
  RelayBenchSetup(); // Software setup post-reset state; electrical Hi-Z is separate.
  assertReleased(); assert(!relayBenchLatchedOff && fakeSafeOutputOrder);
  puts("latched and timed relay scenarios PASS");
}
