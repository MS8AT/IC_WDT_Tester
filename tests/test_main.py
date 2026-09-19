"""Execute the selected main.cpp with fake GPIO/UART; no hardware or network."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ARDUINO = r'''
#pragma once
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstdarg>
#include <string>
#include <vector>
#include <utility>
#include <ctime>
using String = std::string;
inline time_t fakeEpoch = 0;
inline time_t fakeTime(time_t*) { return fakeEpoch; }
#ifdef _WIN32
inline tm* localtime_r(const time_t* value, tm* output) {
  *output = *std::localtime(value); return output;
}
inline int setenv(const char*, const char*, int) { return 0; }
#endif
#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define INPUT 0
#define INPUT_PULLUP 2
inline unsigned long nowMs = 0;
inline int pins[40] = {};
inline int modes[40] = {};
inline int latches[40] = {};
inline int resetPadOverride = -1;
inline unsigned pinModeCalls = 0;
inline std::vector<std::pair<int, int>> writes;
inline unsigned long millis() { return nowMs; }
inline void digitalWrite(int pin, int value) {
  if (pin == 12 || (pin == 25 && value != LOW)) std::abort();
  latches[pin] = value;
  if (pin != 25 || modes[pin] == OUTPUT) pins[pin] = value;
  writes.emplace_back(pin, value);
}
inline int digitalRead(int pin) { return pin == 25 && resetPadOverride >= 0 ? resetPadOverride : pins[pin]; }
inline void pinMode(int pin, int mode) {
  ++pinModeCalls;
  if (pin == 12) std::abort(); // GPIO12 must remain a boot strap, never a driven RESET.
  if (pin == 13 && mode == OUTPUT && pins[13] != HIGH) std::abort();
  if (pin == 25) {
    if (mode != INPUT && mode != OUTPUT) std::abort();
    if (mode == OUTPUT && latches[pin] != LOW) std::abort();
    pins[pin] = mode == INPUT ? HIGH : latches[pin]; // Target's external pull-up.
  }
  modes[pin] = mode;
  if (mode == INPUT_PULLUP) pins[pin] = HIGH;
}
inline void yield() {}
inline void configTime(long, int, const char*, const char*) {}
struct FakeSerial {
  std::string input, output;
  bool flushed = false;
  void flush() { flushed = true; }
  void begin(unsigned long) {}
  void setDebugOutput(bool) {}
  int available() { return static_cast<int>(input.size()); }
  int read() { char c = input.front(); input.erase(0, 1); return c; }
  void print(const char* s) { output += s; }
  void print(int n) { output += std::to_string(n); }
  void println(const char* s = "") { print(s); output += '\n'; }
  void printf(const char* fmt, ...) {
    char buf[1024]; va_list ap; va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap); va_end(ap); output += buf;
  }
};
inline FakeSerial Serial;
struct RebootRequested {};
struct FakeESP {
  unsigned restarts = 0;
  void restart() {
    if (!Serial.flushed || modes[25] != INPUT) std::abort();
    ++restarts;
    throw RebootRequested{};
  }
};
inline FakeESP ESP;
'''
WIFI = r'''
#pragma once
#define WL_CONNECTED 3
#define WL_NO_SSID_AVAIL 1
#define WL_CONNECT_FAILED 4
#define WIFI_STA 1
struct FakeIP {
  std::string toString() const { return "192.168.88.46"; }
  operator const char*() const { return "192.168.88.46"; }
};
struct FakeWiFi {
  bool connected = false;
  int offlineStatus = 0;
  int status() { return connected ? WL_CONNECTED : offlineStatus; }
  void begin(const char*, const char*) {}
  void mode(int) {}
  FakeIP localIP() { return {}; }
  int RSSI() { return -22; }
};
inline FakeWiFi WiFi;
'''
SOC = r'''
#pragma once
#include "Arduino.h"
#define GPIO_OUT_REG 1
#define GPIO_ENABLE_REG 2
#define IO_MUX_GPIO25_REG 3
#define FUN_IE (1U << 9)
#define MCU_SEL_S 12
#define MCU_SEL_M (7U << MCU_SEL_S)
#define PIN_FUNC_GPIO 2
inline unsigned mockMux = FUN_IE | (PIN_FUNC_GPIO << MCU_SEL_S);
inline unsigned REG_READ(unsigned reg) {
  if (reg == GPIO_OUT_REG) return latches[25] ? (1U << 25) : 0;
  if (reg == GPIO_ENABLE_REG) return modes[25] == OUTPUT ? (1U << 25) : 0;
  return mockMux;
}
'''
HARNESS = r'''
#include <cassert>
#include "Arduino.h"
#define time fakeTime
#include "main.cpp"
void command(const std::string& text) { Serial.input = text; handleSerial(); }
int main() {
  printHelp();
  std::fputs(Serial.output.c_str(), stdout);
  Serial.output.clear();
  setup();
  assert(modes[25] == INPUT);
  assert(pins[13] == HIGH && pins[25] == HIGH);
  for (nowMs = 0; nowMs < 6000; nowMs += 100) loop();
  for (const auto& write : writes) assert(write.first != 13 || write.second == HIGH);
  command("  oFf \r\n");
  assert(pins[13] == LOW);
  const auto count = writes.size();
  Serial.output.clear();
  command("hElP\nStS\nSTATUS\n");
  assert(writes.size() == count);
  assert(Serial.output.find("GPIO13=OFF") != std::string::npos);
  assert(Serial.output.find("RESET=IDLE") != std::string::npos);
  assert(Serial.output.find("WIFI=DISCONNECTED") != std::string::npos);
  assert(Serial.output.find("max 31 chars") != std::string::npos);
  command(std::string(40, 'x') + "ON\nUNKNOWN\n\n");
  assert(writes.size() == count && pins[13] == LOW);
  nowMs = 100000; loop();
  assert(pins[13] == LOW);  // OFF has no timeout or startup callback.
  const auto resetWrites = writes.size();
  command("RESET\n");
  assert(writes[resetWrites] == std::make_pair(13, LOW));
  assert(writes[resetWrites + 1] == std::make_pair(25, LOW));
  assert(pins[25] == LOW && pins[13] == LOW && modes[25] == OUTPUT);
  nowMs += 999; handleReset(); assert(pins[25] == LOW);
  Serial.output.clear(); command("STS\n");
  assert(Serial.output.find("RESET=ACTIVE") != std::string::npos);
  ++nowMs; handleReset(); assert(pins[25] == HIGH && pins[13] == HIGH);
  assert(modes[25] == INPUT);
  assert(writes[resetWrites + 2] == std::make_pair(13, HIGH));
  command("OFF\n");
  Serial.output.clear(); command("reset100\n");
  assert(pins[25] == LOW && pins[13] == LOW);
  nowMs += 99; handleReset(); assert(pins[25] == LOW);
  ++nowMs; handleReset(); assert(pins[25] == HIGH && pins[13] == LOW);
  assert(modes[25] == INPUT);
  assert(Serial.output.find("RESET100 START") != std::string::npos);
  assert(Serial.output.find("RESET100 DONE") != std::string::npos);
  command("RESET100\n"); nowMs += 90;
  command("RESET\n"); nowMs += 100; handleReset(); assert(pins[25] == LOW);
  nowMs += 899; handleReset(); assert(pins[25] == LOW);
  ++nowMs; handleReset(); assert(pins[25] == HIGH);
  command("RESET\n"); nowMs += 90;
  command("RESET100\n"); nowMs += 99; handleReset(); assert(pins[25] == LOW);
  ++nowMs; handleReset(); assert(pins[25] == HIGH && pins[13] == HIGH);
  // RESET also cycles an initially enabled relay; explicit OFF cancels re-enable.
  command("RESET\n"); assert(pins[13] == LOW && pins[25] == LOW);
  command("OFF\n"); nowMs += 1000; handleReset();
  assert(pins[25] == HIGH && pins[13] == LOW && !relayOnAfterReset);
  command("RESET100\n"); nowMs += 100; handleReset();
  assert(pins[13] == LOW);  // Diagnostic reset alone preserves latched OFF.
  command("ON\n"); assert(pins[13] == HIGH);
  command("OFF\n"); setup(); assert(pins[13] == HIGH);
  // GPIO33 history observes debounced transitions; it must not drive outputs.
  const auto beforeHistory = writes.size();
  Serial.output.clear(); command("hIsToRy\n");
  assert(Serial.output.find("0/10") != std::string::npos);
  assert(writes.size() == beforeHistory);
  command("RESET\n");
  Serial.output.clear(); command("HISTORY\n");
  assert(Serial.output.empty() && eventHistoryPrintPending);
  assert(pins[25] == LOW);
  nowMs += 999; handleReset();
  assert(Serial.output.empty() && pins[25] == LOW);
  ++nowMs; handleReset();
  assert(pins[25] == HIGH && !eventHistoryPrintPending);
  assert(Serial.output.find("📋 GPIO33") != std::string::npos);
  pins[33] = LOW; handleGPIO33();
  nowMs += 39; handleGPIO33();
  assert(eventHistoryCount == 0);
  pins[33] = HIGH; handleGPIO33();
  nowMs += 40; handleGPIO33();
  assert(eventHistoryCount == 0);  // A short bounce is not an event.
  for (unsigned n = 1; n <= 12; ++n) {
    pins[33] = (n % 2) ? LOW : HIGH;
    ++nowMs; handleGPIO33();
    nowMs += 40; handleGPIO33();
  }
  assert(eventHistoryCount == 10 && nextEventNumber == 13);
  assert(writes.size() == beforeHistory + 3);
  Serial.output.clear(); command("HISTORY\n");
  assert(Serial.output.find("#1 ") == std::string::npos);
  assert(Serial.output.find("#2 ") == std::string::npos);
  assert(Serial.output.find("#3  HIGH -> LOW") != std::string::npos);
  assert(Serial.output.find("#12  LOW -> HIGH") != std::string::npos);
  size_t previous = 0;
  for (unsigned n = 3; n <= 12; ++n) {
    const auto position = Serial.output.find("#" + std::to_string(n) + "  ");
    assert(position != std::string::npos && position >= previous);
    previous = position;
  }
  assert(Serial.output.find("🕒 ⏳ | ⏱") != std::string::npos);
  Serial.output.clear(); command("STS\n");
  assert(Serial.output.rfind("STS GPIO13=ON RESET=IDLE GPIO33=HIGH", 0) == 0);
  assert(Serial.output.find("UNIX_TIME=null") != std::string::npos);
  std::fputs(Serial.output.c_str(), stdout);
  assert(writes.size() == beforeHistory + 3);
  const auto beforeDiagModes = pinModeCalls;
  Serial.output.clear(); command("RESETDIAG\n");
  assert(Serial.output.find("EXPECTED=HIGH PAD=HIGH LATCH=LOW") != std::string::npos);
  assert(Serial.output.find("OE=0 IE=1 MUX=2 PAD_VALID=1") != std::string::npos);
  assert(writes.size() == beforeHistory + 3 && pinModeCalls == beforeDiagModes);
  command("RESET\n");
  resetPadOverride = HIGH;  // External pad may differ from the commanded latch.
  Serial.output.clear(); command("RESETDIAG\n");
  assert(Serial.output.find("ACTIVE=1 EXPECTED=LOW PAD=HIGH LATCH=LOW") != std::string::npos);
  assert(writes.size() == beforeHistory + 5 && pinModeCalls == beforeDiagModes + 1);
  resetPadOverride = -1;
  mockMux &= ~FUN_IE;
  Serial.output.clear(); command("RESETDIAG\n");
  assert(Serial.output.find("IE=0 MUX=2 PAD_VALID=0") != std::string::npos);
  mockMux = FUN_IE | (1U << MCU_SEL_S);
  Serial.output.clear(); command("RESETDIAG\n");
  assert(Serial.output.find("MUX=1 PAD_VALID=0") != std::string::npos);
  mockMux = FUN_IE | (PIN_FUNC_GPIO << MCU_SEL_S);
  nowMs += 1000; handleReset();
  // Real JSON output is parsed by Python; the clock and Wi-Fi are deterministic.
  const auto beforeTelemetry = writes.size();
  Serial.output.clear();
  pins[33] = LOW; handleGPIO33(); nowMs += 40; handleGPIO33();
  std::fputs(Serial.output.c_str(), stdout);
  WiFi.connected = true; ntpSynchronized = true; fakeEpoch = 1789746536;
  Serial.output.clear(); command("STATUS\n");
  assert(Serial.output.find("📶 ✅\n🌐 IP: 192.168.88.46\n📶 RSSI: -22 dBm\n🕒 NTP ✅\n") != std::string::npos);
  std::fputs(Serial.output.c_str(), stdout);
  Serial.output.clear();
  pins[33] = HIGH; handleGPIO33(); nowMs += 40; handleGPIO33();
  std::fputs(Serial.output.c_str(), stdout);
  const auto eventEpoch = eventHistory[(eventHistoryWriteIndex + EVENT_HISTORY_SIZE - 1) % EVENT_HISTORY_SIZE].unixTime;
  fakeEpoch += 100;
  Serial.output.clear(); command("HISTORY\n");
  assert(eventEpoch == 1789746536);
  assert(Serial.output.find("UNIX_TIME=1789746536 | WDT/EN GPIO33 #14") != std::string::npos);
  assert(Serial.output.find("\"type\":\"gpio_change\"") == std::string::npos);
  std::fputs(Serial.output.c_str(), stdout);
  WiFi.connected = false;
  Serial.output.clear(); command("STS\n");
  std::fputs(Serial.output.c_str(), stdout);
  assert(writes.size() == beforeTelemetry);
  // RST reboots this MCU, releases external RESET first, flushes its ACK,
  // and does not process another queued command before the reboot.
  command("RESET\n");
  Serial.output.clear(); Serial.flushed = false;
  try { command("  rSt \r\nON\n"); assert(false); }
  catch (const RebootRequested&) {}
  assert(ESP.restarts == 1 && pins[25] == HIGH && pins[13] == LOW);
  assert(!resetActive && !relayOnAfterReset);
  assert(Serial.output == "RST REBOOT\n");
  commandLength = 0; Serial.input.clear();
  Serial.flushed = false;
  try { command("RST\n"); assert(false); }
  catch (const RebootRequested&) {}
  assert(ESP.restarts == 2);
  // LED is independent of the relay/reset, has no delay, and handles timer wrap.
  WiFi.connected = false; WiFi.offlineStatus = 0; wifiWasConnected = false;
  wifiLedMode = WifiLedMode::Waiting; wifiLedOn = false; pins[2] = LOW;
  nowMs = 200000;
  startWiFiConnection(false); handleWiFiLed();
  assert(modes[2] == OUTPUT && pins[2] == HIGH);
  const auto beforeLed = writes.size();
  nowMs += 124; handleWiFiLed(); assert(pins[2] == HIGH);
  ++nowMs; handleWiFiLed(); assert(pins[2] == LOW);
  nowMs += 125; handleWiFiLed(); assert(pins[2] == HIGH);
  nowMs = lastWifiAttemptMs + 5000; handleWiFi(); handleWiFiLed();
  assert(wifiLedMode == WifiLedMode::Waiting && pins[2] == HIGH);
  nowMs += 499; handleWiFiLed(); assert(pins[2] == HIGH);
  ++nowMs; handleWiFiLed(); assert(pins[2] == LOW);
  nowMs = lastWifiAttemptMs + 10000; handleWiFi(); handleWiFiLed();
  assert(wifiLedMode == WifiLedMode::Connecting && pins[2] == HIGH);
  WiFi.connected = true; handleWiFi(); handleWiFiLed();
  assert(wifiLedMode == WifiLedMode::Connected && pins[2] == HIGH);
  nowMs += 1000; handleWiFi(); handleWiFiLed(); assert(pins[2] == HIGH);
  WiFi.connected = false; handleWiFi(); handleWiFiLed();
  assert(wifiLedMode == WifiLedMode::Waiting);
  startWiFiConnection(false); WiFi.offlineStatus = WL_CONNECT_FAILED;
  handleWiFi(); handleWiFiLed(); assert(wifiLedMode == WifiLedMode::Waiting);
  wifiLedChangedAtMs = 0xFFFFFF00UL; wifiLedOn = true; pins[2] = HIGH;
  nowMs = 243; handleWiFiLed(); assert(pins[2] == HIGH);
  nowMs = 244; handleWiFiLed(); assert(pins[2] == LOW);
  for (size_t i = beforeLed; i < writes.size(); ++i) assert(writes[i].first == 2);
}
'''


class MainFirmwareTests(unittest.TestCase):
    def test_boot_commands_and_reset(self):
        compiler = shutil.which('g++')
        self.assertIsNotNone(compiler, 'g++ required; no automatic install')
        with tempfile.TemporaryDirectory(prefix='tester-main-') as directory:
            folder = Path(directory)
            (folder / 'soc').mkdir()
            for name in ('gpio_reg.h', 'io_mux_reg.h', 'soc.h'):
                (folder / 'soc' / name).write_text(SOC, encoding='utf-8')
            for name, text in [('Arduino.h', ARDUINO), ('WiFi.h', WIFI),
                               ('main_harness.cpp', HARNESS)]:
                (folder / name).write_text(text, encoding='utf-8')
            binary = folder / 'main_harness.exe'
            subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I', str(folder), '-I', str(ROOT / 'src'),
                            str(folder / 'main_harness.cpp'), '-o', str(binary)],
                           check=True, timeout=40)
            result = subprocess.run([str(binary)], check=False, timeout=15,
                                    capture_output=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            from sys import path
            path.insert(0, str(ROOT / 'tools'))
            from read_telemetry import parse_telemetry_line
            lines = result.stdout.splitlines()
            self.assertFalse(any(line.startswith('{') for line in lines))
            self.assertFalse(any(line.startswith('JSON ') for line in lines))
            all_rows = [parse_telemetry_line(line) for line in lines if ' | JSON ' in line]
            history = [r for r in all_rows if r['type'] == 'gpio_history']
            rows = [r for r in all_rows if r['type'] != 'gpio_history']
            self.assertEqual(len(history), 30)
            self.assertTrue(all(r['replay'] for r in history))
            self.assertEqual([r['event_id'] for r in history[-10:]], list(range(5, 15)))
            self.assertEqual(history[-1]['unix_time'], 1789746536)
            self.assertIsNone(history[-2]['unix_time'])  # No invented NTP time on replay.
            self.assertTrue(all(r['subsystem'] == 'WDT' for r in all_rows))
            self.assertEqual([r['type'] for r in rows],
                             ['status', 'gpio_change', 'status', 'gpio_change', 'status'])
            offline, early_event, online, timed_event, disconnected = rows
            self.assertIsNone(offline['unix_time'])
            self.assertIsNone(offline['local_time'])
            self.assertIsNone(offline['ip'])
            self.assertIsNone(offline['rssi_dbm'])
            self.assertFalse(offline['time_valid'])
            self.assertEqual(offline['reset_gpio'], 25)
            self.assertEqual(offline['gpio25'], 'HIGH')
            self.assertEqual(offline['reset_drive'], 'HI_Z')
            self.assertEqual(offline['gpio12'], 'LOW')  # Physical strap, not RESET level.
            self.assertIsNone(early_event['unix_time'])
            self.assertEqual(online['unix_time'], 1789746536)
            self.assertEqual(online['ip'], '192.168.88.46')
            self.assertEqual(online['rssi_dbm'], -22)
            self.assertTrue(online['ntp_synced'])
            self.assertTrue(online['relay_on'])
            self.assertFalse(online['reset_active'])
            self.assertEqual(online['events_total'], 13)
            self.assertEqual(online['history_count'], 10)
            self.assertEqual((timed_event['event_id'], timed_event['gpio'], timed_event['new']),
                             (14, 33, 'HIGH'))
            self.assertEqual(timed_event['unix_time'], online['unix_time'])
            self.assertFalse(timed_event['replay'])
            self.assertIsNone(timed_event['wdt_triggered'])
            self.assertEqual(timed_event['signal'], 'EN')
            self.assertGreater(timed_event['uptime_ms'], online['uptime_ms'])
            self.assertTrue(disconnected['ntp_synced'])
            self.assertFalse(disconnected['wifi_connected'])
            self.assertIsNone(disconnected['ip'])
            self.assertIsNone(disconnected['rssi_dbm'])
            self.assertTrue(all(row['schema'] == 1 for row in rows))


if __name__ == '__main__':
    unittest.main()
