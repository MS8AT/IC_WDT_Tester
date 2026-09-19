# Legacy LATCH-02 compatibility

RelayResetBench.h and relay_main.cpp are retained for a separate legacy firmware.
The default PlatformIO environment builds main.cpp only.

Legacy commands: identity, status, off, on, bypass:<1-5000ms>, release.
Aliases: function wdt status/on/off/timed <ms>. OFF is latched until ON or reboot.
GPIO13 controls the relay; GPIO33 observes EN. JSON type wdt_pin is described
in [TELEMETRY](TELEMETRY.md). Identity/lease workflows are not main.cpp commands.
Use tester_control.py only with positively identified legacy firmware;
use CurrentProtocol for main.cpp. Do not infer wiring or board identity from COM.
Private historical owner IDs and hardware logs are excluded from this snapshot.
