#pragma once

// BEGIN embedded TaskSerial
#ifndef CATENZO_TASK_SERIAL_H
#define CATENZO_TASK_SERIAL_H

// Application UART adapter. No Serial macro: library/SDK declarations stay intact.
// Include after Arduino.h; constructor paths must not call this C++ object.
#include <Arduino.h>
#include <atomic>
#include <stdarg.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

struct TaskSerialStats {
  uint32_t acceptedBytes;
  uint32_t transmittedBytes;
  uint32_t droppedBytes;
  uint32_t commandDroppedBytes;
  uint32_t startFailures;
  uint32_t flushTimeouts;
  size_t queuedBytes;
  bool ready;
  uint32_t receivedBytes;
  uint32_t rxDroppedBytes;
  uint32_t commandSuppressedBytes;
  uint32_t workerPasses;
};

class TaskSerialPort : public Stream {
public:
  static constexpr size_t Capacity = 2048;
  static constexpr size_t RxCapacity = 512;
  static constexpr uint32_t CommandWaitMs = 100;
  static constexpr uint32_t FlushWaitMs = 40;

  explicit TaskSerialPort(HardwareSerial &hardware) : hardware_(hardware) {}
  using Print::write;

  // Only stores the request and starts a worker. No UART begin in setup/ctor.
  bool start(unsigned long baud) {
    if (xTaskGetSchedulerState() != taskSCHEDULER_RUNNING) return false;
    portENTER_CRITICAL(&mux_);
    if (worker_ != nullptr) {
      const bool sameBaud = requestedBaud_ == baud;
      portEXIT_CRITICAL(&mux_);
      return sameBaud;
    }
    if (starting_) { portEXIT_CRITICAL(&mux_); return false; }
    starting_ = true;
    requestedBaud_ = baud;
    portEXIT_CRITICAL(&mux_);
    TaskHandle_t handle = nullptr;
    const BaseType_t result = xTaskCreatePinnedToCore(workerEntry, "Serial_IO", 3072,
                                                     this, 1, &handle, 0);
    portENTER_CRITICAL(&mux_);
    if (result == pdPASS) worker_ = handle;
    else ++startFailures_;
    starting_ = false;
    portEXIT_CRITICAL(&mux_);
    return result == pdPASS;
  }
  void begin(unsigned long baud) { start(baud); }
  unsigned long baudRate() const { return ready_ ? requestedBaud_.load() : 0; }
  explicit operator bool() const { return ready_.load(); }

  size_t write(uint8_t value) override { return write(&value, 1); }
  size_t write(const uint8_t *data, size_t length) override {
    if (data == nullptr || length == 0) return 0;
    const TaskHandle_t caller = canYield() ? xTaskGetCurrentTaskHandle() : nullptr;
    portENTER_CRITICAL(&mux_);
    const bool command = commandOwner_ != nullptr && commandOwner_ == caller;
    if (command && commandFailed_) {
      droppedBytes_ += length;
      commandDroppedBytes_ += length;
      portEXIT_CRITICAL(&mux_);
      return 0;
    }
    if (commandOwner_ != nullptr && !command) {
      droppedBytes_ += length;
      commandSuppressedBytes_ += length;
      portEXIT_CRITICAL(&mux_);
      return 0;
    }
    portEXIT_CRITICAL(&mux_);
    const uint32_t started = millis();
    size_t written = 0;
    do {
      portENTER_CRITICAL(&mux_);
      if (commandOwner_ != nullptr && commandOwner_ != caller) {
        commandSuppressedBytes_ += length - written;
        portEXIT_CRITICAL(&mux_);
        break;
      }
      const size_t room = Capacity - count_;
      const size_t pending = length - written;
      const size_t take = pending < room ? pending : room;
      for (size_t i = 0; i < take; ++i) {
        bytes_[(head_ + count_ + i) % Capacity] = data[written + i];
      }
      count_ += take;
      acceptedBytes_ += take;
      portEXIT_CRITICAL(&mux_);
      written += take;
      if (written == length || !command || worker_ == nullptr ||
          static_cast<uint32_t>(millis() - started) >= CommandWaitMs) break;
      vTaskDelay(1);
    } while (true);
    if (written != length) {
      portENTER_CRITICAL(&mux_);
      droppedBytes_ += length - written;
      if (command) {
        commandDroppedBytes_ += length - written;
        commandFailed_ = true;
      }
      portEXIT_CRITICAL(&mux_);
      setWriteError();
    }
    return written;
  }

  // Arduino's printf may allocate arbitrarily large temporary buffers. Bound it.
  size_t printf(const char *format, ...) __attribute__((format(printf, 2, 3))) {
    char text[384];
    va_list args;
    va_start(args, format);
    const int requested = vsnprintf(text, sizeof(text), format, args);
    va_end(args);
    if (requested <= 0) return 0;
    const size_t length = static_cast<size_t>(requested);
    const size_t kept = length < sizeof(text) ? length : sizeof(text) - 1;
    const size_t result = write(reinterpret_cast<const uint8_t *>(text), kept);
    if (length > kept) {
      portENTER_CRITICAL(&mux_);
      droppedBytes_ += length - kept;
      if (commandOwner_ != nullptr && canYield() &&
          commandOwner_ == xTaskGetCurrentTaskHandle()) {
        commandDroppedBytes_ += length - kept;
        commandFailed_ = true;
      }
      portEXIT_CRITICAL(&mux_);
      setWriteError();
    }
    return result;
  }

  int availableForWrite() override {
    portENTER_CRITICAL(&mux_);
    const int room = Capacity - count_;
    portEXIT_CRITICAL(&mux_);
    return room;
  }
  int available() override {
    portENTER_CRITICAL(&mux_);
    const int result = rxCount_ + (rxOverflowSignal_ ? 1 : 0);
    portEXIT_CRITICAL(&mux_);
    return result;
  }
  int read() override {
    portENTER_CRITICAL(&mux_);
    // Reader must discard its partial command on this transport-loss sentinel.
    if (rxOverflowSignal_) {
      rxOverflowSignal_ = false;
      portEXIT_CRITICAL(&mux_);
      return -2;
    }
    const int result = rxCount_ == 0 ? -1 : rx_[rxHead_];
    if (rxCount_ != 0) { rxHead_ = (rxHead_ + 1) % RxCapacity; --rxCount_; }
    portEXIT_CRITICAL(&mux_);
    return result;
  }
  int peek() override {
    portENTER_CRITICAL(&mux_);
    const int result = rxOverflowSignal_ ? -2 : (rxCount_ == 0 ? -1 : rx_[rxHead_]);
    portEXIT_CRITICAL(&mux_);
    return result;
  }

  // Bounded software drain only. Never waits on the hardware UART mutex/flush.
  void flush() override {
    if (!canYield() || worker_ == nullptr || xTaskGetCurrentTaskHandle() == worker_) return;
    const uint32_t started = millis();
    while (snapshot().queuedBytes != 0) {
      if (static_cast<uint32_t>(millis() - started) >= FlushWaitMs) {
        portENTER_CRITICAL(&mux_);
        ++flushTimeouts_;
        portEXIT_CRITICAL(&mux_);
        return;
      }
      vTaskDelay(1);
    }
  }
  // Hardware debug bypasses this queue and can block callers; keep it disabled.
  void setDebugOutput(bool) {}

  TaskSerialStats snapshot() {
    portENTER_CRITICAL(&mux_);
    const TaskSerialStats result = {acceptedBytes_, transmittedBytes_, droppedBytes_,
      commandDroppedBytes_, startFailures_, flushTimeouts_, count_, ready_,
      receivedBytes_, rxDroppedBytes_, commandSuppressedBytes_, workerPasses_};
    portEXIT_CRITICAL(&mux_);
    return result;
  }

  bool enterCommand() {
    if (!canYield()) return false;
    portENTER_CRITICAL(&mux_);
    const bool acquired = commandOwner_ == nullptr;
    if (acquired) {
      commandOwner_ = xTaskGetCurrentTaskHandle();
      commandFailed_ = false;
    }
    portEXIT_CRITICAL(&mux_);
    return acquired;
  }
  void leaveCommand() {
    portENTER_CRITICAL(&mux_);
    if (commandOwner_ == xTaskGetCurrentTaskHandle()) commandOwner_ = nullptr;
    portEXIT_CRITICAL(&mux_);
  }

private:
  static bool canYield() { return xTaskGetSchedulerState() == taskSCHEDULER_RUNNING; }
  static void workerEntry(void *context) {
    TaskSerialPort &port = *static_cast<TaskSerialPort *>(context);
    port.hardware_.begin(port.requestedBaud_);
    port.hardware_.setDebugOutput(false);
    port.ready_ = static_cast<bool>(port.hardware_);
    for (;;) {
      port.ready_ = static_cast<bool>(port.hardware_);
      port.serviceRx();
      port.serviceTx();
      portENTER_CRITICAL(&port.mux_);
      ++port.workerPasses_;
      portEXIT_CRITICAL(&port.mux_);
      vTaskDelay(1);
    }
  }

  void serviceRx() {
    if (!ready_) return;
    // A continuous RX stream cannot starve TX or monopolize the task.
    for (size_t i = 0; i < 128 && hardware_.available() > 0; ++i) {
      const int value = hardware_.read();
      if (value < 0) break;
      portENTER_CRITICAL(&mux_);
      ++receivedBytes_;
      if (rxDiscardLine_) {
        ++rxDroppedBytes_;
        if (value == '\n' || value == '\r') rxDiscardLine_ = false;
      } else if (rxCount_ < RxCapacity) {
        rx_[(rxHead_ + rxCount_) % RxCapacity] = static_cast<uint8_t>(value);
        ++rxCount_;
      } else {
        rxDroppedBytes_ += rxCount_ + 1;
        rxHead_ = 0;
        rxCount_ = 0;
        rxOverflowSignal_ = true;
        rxDiscardLine_ = value != '\n' && value != '\r';
      }
      portEXIT_CRITICAL(&mux_);
    }
  }

  void serviceTx() {
    if (!ready_) return;
    // Only this worker writes HardwareSerial. Keep each write within FIFO space.
    const int room = hardware_.availableForWrite();
    if (room <= 0) return;
    uint8_t chunk[96];
    portENTER_CRITICAL(&mux_);
    size_t length = count_ < sizeof(chunk) ? count_ : sizeof(chunk);
    if (length > static_cast<size_t>(room)) length = room;
    for (size_t i = 0; i < length; ++i) chunk[i] = bytes_[(head_ + i) % Capacity];
    portEXIT_CRITICAL(&mux_);
    if (length == 0) return;
    const size_t sent = hardware_.write(chunk, length);
    portENTER_CRITICAL(&mux_);
    const size_t consumed = sent < length ? sent : length;
    head_ = (head_ + consumed) % Capacity;
    count_ -= consumed;
    transmittedBytes_ += consumed;
    portEXIT_CRITICAL(&mux_);
  }

  HardwareSerial &hardware_;
  portMUX_TYPE mux_ = portMUX_INITIALIZER_UNLOCKED;
  uint8_t bytes_[Capacity] = {};
  size_t head_ = 0, count_ = 0;
  uint8_t rx_[RxCapacity] = {};
  size_t rxHead_ = 0, rxCount_ = 0;
  bool rxOverflowSignal_ = false, rxDiscardLine_ = false;
  std::atomic<unsigned long> requestedBaud_{0};
  std::atomic<bool> ready_{false};
  bool starting_ = false;
  std::atomic<TaskHandle_t> worker_{nullptr};
  TaskHandle_t commandOwner_ = nullptr;
  bool commandFailed_ = false;
  uint32_t acceptedBytes_ = 0, transmittedBytes_ = 0, droppedBytes_ = 0;
  uint32_t commandDroppedBytes_ = 0, startFailures_ = 0, flushTimeouts_ = 0;
  uint32_t receivedBytes_ = 0, rxDroppedBytes_ = 0;
  uint32_t commandSuppressedBytes_ = 0, workerPasses_ = 0;
};

static TaskSerialPort AppSerial(Serial);
inline bool StartTaskSerial(unsigned long baud) { return AppSerial.start(baud); }

class TaskSerialCommandScope {
public:
  explicit TaskSerialCommandScope(TaskSerialPort &port = AppSerial)
      : port_(port), acquired_(port.enterCommand()),
        droppedBefore_(port.snapshot().commandDroppedBytes) {}
  ~TaskSerialCommandScope() { if (acquired_) port_.leaveCommand(); }
  bool acquired() const { return acquired_; }
  bool failed() { return !acquired_ || port_.snapshot().commandDroppedBytes != droppedBefore_; }
  TaskSerialCommandScope(const TaskSerialCommandScope &) = delete;
  TaskSerialCommandScope &operator=(const TaskSerialCommandScope &) = delete;
private:
  TaskSerialPort &port_;
  bool acquired_;
  uint32_t droppedBefore_;
};

#endif
// END embedded TaskSerial

// BEGIN embedded SerialCommandReader
#ifndef SERIAL_COMMAND_READER_H
#define SERIAL_COMMAND_READER_H

#include <Arduino.h>

typedef void (*SerialCommandLineHandler)(const String &line);

class SerialCommandReader {
public:
  SerialCommandReader(SerialCommandLineHandler handler = nullptr,
                      uint32_t idleFlushMs = 80,
                      size_t maxBufferLength = 128)
      : _handler(handler),
        _idleFlushMs(idleFlushMs),
        _maxBufferLength(maxBufferLength),
        _serial(&AppSerial),
        _lastByteMillis(0) {
  }

  void begin(Stream &serial = AppSerial) {
    _serial = &serial;
    _buffer = "";
    _discardLine = false;
    _lastByteMillis = millis();
  }

  void setHandler(SerialCommandLineHandler handler) {
    _handler = handler;
  }

  void poll() {
    // One bounded slice; continuous input must return control to AutoLoop.
    size_t bytes = 0;
    size_t lines = 0;
    while (bytes++ < 128 && lines < 1 && _serial->available() > 0) {
      const int raw = _serial->read();
      if (raw == -2) { _buffer = ""; _discardLine = false; continue; }
      if (raw < 0) break;
      const char c = static_cast<char>(raw);
      _lastByteMillis = millis();

      if (c == '\r' || c == '\n') {
        if (!_discardLine && _buffer.length() > 0) { flush(); ++lines; }
        _discardLine = false;
        continue;
      }

      if (_discardLine) continue;
      if (_buffer.length() < _maxBufferLength) {
        _buffer += c;
      } else {
        // Never execute a truncated command prefix (including reset/OTA).
        _buffer = "";
        _discardLine = true;
      }
    }

    if (!_discardLine && lines == 0 && _serial->available() == 0 &&
        _buffer.length() > 0 && _idleFlushMs > 0 &&
        (millis() - _lastByteMillis) >= _idleFlushMs) {
      flush();
    }
  }

private:
  void flush() {
    String line = _buffer;
    _buffer = "";
    line.trim();
    if (line.length() > 0 && _handler != nullptr) {
      _handler(line);
    }
  }

  String _buffer;
  SerialCommandLineHandler _handler;
  uint32_t _idleFlushMs;
  size_t _maxBufferLength;
  Stream *_serial;
  uint32_t _lastByteMillis;
  bool _discardLine = false;
};

#endif
// END embedded SerialCommandReader

// BEGIN embedded AutoSerial
#ifndef AUTOSERIAL_H
#define AUTOSERIAL_H

#include <Arduino.h>

#ifndef AUTOSERIAL_BACKGROUND_TASK
#define AUTOSERIAL_BACKGROUND_TASK 1
#endif

// The application releases this gate after Arduino/global objects are ready.
bool AutoSerialRuntimeReady() __attribute__((weak));
void AutoSerialService() __attribute__((weak));

#ifndef AUTOSERIAL_IDLE_FLUSH_MS
#define AUTOSERIAL_IDLE_FLUSH_MS 600
#endif

typedef void (*AutoSerialLineHandler)(const String &line);

void processSerialCommandLine(const String &line) __attribute__((weak));
void RegisterAutoLoopCallback(const char *functionName, void (*callback)()) __attribute__((weak));

static AutoSerialLineHandler autoSerialCustomHandler = nullptr;
static bool autoSerialReaderInitialized = false;
inline AutoSerialLineHandler AutoSerialResolveHandler() {
  if (autoSerialCustomHandler != nullptr) {
    return autoSerialCustomHandler;
  }

  if (processSerialCommandLine != nullptr) {
    return processSerialCommandLine;
  }

  return nullptr;
}

inline void AutoSerialDispatch(const String &line) {
  AutoSerialLineHandler handler = AutoSerialResolveHandler();
  if (handler != nullptr) {
    handler(line);
  }
}

static SerialCommandReader autoSerialReader(AutoSerialDispatch, AUTOSERIAL_IDLE_FLUSH_MS, 128);

inline bool AutoSerialIsActive() {
  return static_cast<bool>(AppSerial) && AppSerial.baudRate() > 0;
}

inline void AutoSerialSetHandler(AutoSerialLineHandler handler) {
  autoSerialCustomHandler = handler;
}

inline void AutoSerialBegin(Stream &serial = AppSerial) {
  if (autoSerialReaderInitialized) {
    return;
  }

  autoSerialReader.begin(serial);
  autoSerialReaderInitialized = true;
}

inline void AutoSerialLoop() {
  if (AutoSerialRuntimeReady != nullptr && !AutoSerialRuntimeReady()) return;
  if (!autoSerialReaderInitialized) {
    AutoSerialBegin(AppSerial);
  }

  if (!AutoSerialIsActive()) {
    return;
  }

  autoSerialReader.poll();
}

inline void read_Serial() {
  AutoSerialLoop();
}

inline void _Auto_Serial_() {
  AutoSerialBegin(AppSerial);
  AutoSerialLoop();
}

static void _Auto_Serial_Initializer() {
  AutoSerialBegin(AppSerial);
  if (RegisterAutoLoopCallback != nullptr) {
    RegisterAutoLoopCallback("_Auto_Serial_", _Auto_Serial_);
  }
}

#if AUTOSERIAL_BACKGROUND_TASK
static bool AutoSerialWorkerCreated = false;
static bool AutoSerialUartRequested = false;
static void AutoSerialWorker(void*) {
  // Never touch HardwareSerial while global constructors are still running.
  while (AutoSerialRuntimeReady == nullptr || !AutoSerialRuntimeReady()) vTaskDelay(1);
  for (;;) {
    if (!AutoSerialUartRequested) AutoSerialUartRequested = StartTaskSerial(115200);
    if (AutoSerialService != nullptr) AutoSerialService();
    else AutoSerialLoop();
    vTaskDelay(1);
  }
}
#endif

// Ordinary C++ initialization preserves source order: AppSerial and reader first.
struct AutoSerialInitializer {
  AutoSerialInitializer() {
    _Auto_Serial_Initializer();
#if AUTOSERIAL_BACKGROUND_TASK
    AutoSerialWorkerCreated = xTaskCreatePinnedToCore(
      AutoSerialWorker, "Serial_CMD", 6144, nullptr, 1, nullptr, 0) == pdPASS;
#endif
  }
};
static AutoSerialInitializer autoSerialInitializer;

#endif
// END embedded AutoSerial
