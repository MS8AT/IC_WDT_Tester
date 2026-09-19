## Русский

# Совместимость LATCH-02

RelayResetBench.h и relay_main.cpp сохранены для отдельной старой прошивки. Среда PlatformIO по умолчанию собирает только main.cpp.

Старые команды: identity, status, off, on, bypass:<1-5000ms>, release. Псевдонимы: function wdt status/on/off/timed <ms>. OFF фиксируется до ON или reboot. GPIO13 управляет реле; GPIO33 наблюдает EN. JSON type wdt_pin описан в [TELEMETRY](TELEMETRY.md). Identity/lease не являются командами main.cpp.

Применяйте tester_control.py только к подтверждённой старой прошивке; для main.cpp используйте CurrentProtocol. Не определяйте проводку или идентичность платы по COM. Частные исторические идентификаторы владельцев и аппаратные журналы исключены из снимка.

## 中文

# LATCH-02 兼容性

RelayResetBench.h 和 relay_main.cpp 为独立的旧固件保留。默认 PlatformIO 环境仅编译 main.cpp。

旧命令：identity、status、off、on、bypass:<1-5000ms>、release。别名：function wdt status/on/off/timed <ms>。OFF 保持至 ON 或重启。GPIO13 控制继电器；GPIO33 监测 EN。JSON type wdt_pin 见 [TELEMETRY](TELEMETRY.md)。Identity/lease 不是 main.cpp 的命令。

仅在确认安装了旧固件后使用 tester_control.py；main.cpp 使用 CurrentProtocol。不要根据 COM 判断接线或板卡身份。此快照不包含私人历史操作者标识和硬件日志。

## English

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
