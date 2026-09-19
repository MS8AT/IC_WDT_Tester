[Русский](#ru) · [中文](#zh) · [English](#en)

<a id="ru"></a>

## Русский

# Работа с IC WDT Tester

Команды и их семантика: [COMMANDS](COMMANDS.md). Формат данных: [TELEMETRY](TELEMETRY.md).
Начальный маршрут ИИ: [AI_QUICKSTART](AI_QUICKSTART.md). Этот документ описывает live-порядок.

## До подключения

Проверить разрешённый сценарий, роль каждой платы, проводку, текущий COM и его
единственного владельца. Прежние owner ID/COM — только история. Не завершать
чужие процессы и не вытеснять монитор. Chip model + factory eFuse BASE_MAC
из [device-profile](../device-profile.json) определяют роль; USB/COM — транспорт.
После переподключения сверить mapping и identity перед воздействием/прошивкой.
ROM-проверка сама может reset: выполнять до main flash, не во время него.

Даже открытие/закрытие Serial иногда перезапускает ESP32. Тестер после reboot
включает реле. Общая GND, сигналы до 3.3 V, GPIO33 имеет внутреннюю подтяжку;
фактическую точку измерения и контакты NO/NC/COM не выводить из имён GPIO.
Провода переставлять без питания. GPIO0/WDI основной платы здесь не измеряется.

## Выбор фактического протокола

В разрешённой сессии 115200/8N1 UTF-8 начать с HELP, затем STS.
[ACCEPTANCE](ACCEPTANCE.md) отделяет исходную ревизию от установленной.
Текущий main.cpp не имеет команды identity, READY/lease или счётчиков потерь UART.
Не создавать READY для main flash по одному STS.

Для обычных команд использовать `tools/current_protocol.py` поверх общего
Session из `tools/relay_bench_session.py`. Адаптер не открывает/закрывает COM,
снимает допуск после ошибки протокола/транспорта. RST проверяется по capability;
после его отправки старый uptime и допуск сбрасываются. Прямой write принимает
канонические команды; STATUS — alias на плате, для адаптера использовать STS.

Точная строка HELP `RESET: relay OFF, GPIO25 LOW for 1000 ms, GPIO25 INPUT (Hi-Z), relay ON`
подтверждает новую семантику RESET. Без неё не предполагать переключение реле.
RESET100/HISTORY/RESETDIAG/RST также проверять по соответствующим HELP-строкам.
Новый HELP сообщает `JSON: human text then pipe + JSON object; schema=1; types=status,gpio_change,gpio_history`.
Прежний HELP с `separate lines start with JSON` обозначает старый формат; parser читает оба.

`tester_control.py` и legacy команды Session рассчитаны на [LATCH-02](LEGACY_LATCH02.md).
Не вызывать legacy Session.close(): он может отправить release/ON. Владелец
сессии закрывает handles и журнал без неявной GPIO-команды.

## Разрешённый OFF / main flash / ON / RESET

1. Подтвердить обе платы и проводку; записать точный образ/SHA, исходное состояние,
   откат и план проверки. Закрепить владельцев/handles на время сценария.
2. OFF → свежий STS GPIO13=OFF RESET=IDLE. Сохранять handle тестера и наблюдение
   uptime; при ошибке, reboot или потере связи остановить новые main-воздействия.
3. Запись основной платы и отдельный verify — только в её разрешённом scope.
   Не отправлять RESET/RST и не перезапускать USB тестера во время записи.
4. После завершения main-операции и проверенного общения выполнить разрешённый
   ON, подтвердить STS. Затем один RESET с проверенной проводкой GPIO25;
   подтвердить IDLE и наблюдать новую загрузку основной платы.
5. Отдельно оценить startup/runtime и физические сигналы. Успешная UART-команда,
   STS и счётчик GPIO33 не доказывают контакты/WDI или три нормальных запуска.

Не отправлять ON автоматически в finally, при ошибке или закрытии helper.
Если состояние неизвестно — сохранить evidence и передать конкретный следующий шаг.
Полный backup отключён пользователем: `flash-settings.json`, full_backup_before_flash=false.
До tester flash остаются factory/layout/image-fit/SHA, одна запись и отдельный verify;
чтение нужных boot/partition/OTA областей. `--backup` — только по запросу.

## USB recovery и результат

[restart_usb_port.ps1](../tools/restart_usb_port.ps1) и [USB_COM_RECOVERY](USB_COM_RECOVERY.md):
preview → точный InstanceId/new receipt → Apply/UAC. Он перезапускает один адаптер,
не гарантирует снятие питания и не завершает захвативший COM процесс.

Сохранить команды/ответы, время хоста/платы, SHA/identity, последнее известное
состояние и закрытие handles. В [ACCEPTANCE](ACCEPTANCE.md) писать только проверенный
результат; host/build, PnP restart, UART и hardware — отдельные подтверждения.

---

<a id="zh"></a>

## 中文

# 使用IC WDT Tester

命令及其语义：[COMMANDS](COMMANDS.md)。数据格式：[TELEMETRY](TELEMETRY.md)。
初始AI路径：[AI_QUICKSTART](AI_QUICKSTART.md)。本文档描述了实时顺序。

## 在连接之前

检查允许的场景，每块板的角色，布线，当前COM及其唯一所有者。以前的所有者ID/COM只是历史记录。不要结束其他人的进程或驱逐监控器。芯片型号+工厂eFuse BASE_MAC从[device-profile](../device-profile.json)定义角色；USB/COM是传输方式。
重新连接后，在影响/编程之前，要验证映射和身份。ROM检查本身可能会重置：在主板刷写前执行，不要在过程中执行。

即使打开或关闭串行有时也会重启ESP32。测试仪在重启后会启动继电器。共同的GND，信号不超过3.3V，GPIO33 具有内部上拉（INPUT_PULLUP）；实际测量点和NO/NC/COM触点不从GPIO名称中导出。断电时重新布线。
GPIO0/WDI主板在这里不会被测量。

## 选择实际协议

在允许的会话中以115200/8N1 UTF-8开始HELP，然后是STS。
[ACCEPTANCE](ACCEPTANCE.md)将原始修订与安装版本分开。当前main.cpp没有身份命令、READY/租赁或UART丢失计数器。
不要因为一个STS而为主闪存创建READY。

对于常规命令，在共用传输层上使用 `tools/current_protocol.py`，
Session来自`tools/relay_bench_session.py`。适配器不打开/关闭COM端口,
在协议或传输错误后取消许可。RST根据能力检查;
发送它之后,旧的uptime和许可被重置。直接写入接受
规范命令;STATUS是板上的别名，对于适配器使用STS。

精确的帮助行`RESET: relay OFF, GPIO25 LOW for 1000 ms, GPIO25 INPUT (Hi-Z), relay ON`
确认新的RESET语义。没有它不要假设继电器切换。
RESET100/HISTORY/RESETDIAG/RST也根据相应的帮助行检查。
新帮助提供`JSON: human text then pipe + JSON object; schema=1; types=status,gpio_change,gpio_history`。
旧帮助带有`separate lines start with JSON`表示旧格式;解析器读取两者。

`tester_control.py`和遗留的Session命令针对[LATCH-02](LEGACY_LATCH02.md)设计。
不要调用legacy Session.close():它可能会发送release/ON。会话所有者
关闭句柄和日志,不使用隐式GPIO命令。

## 已授权的 OFF / 主板刷写 / ON / RESET

1. 确认两块板子和连线；记录精确的镜像/SHA，初始状态，回滚计划以及验证方案。在整个场景期间固定测试者的所有权/handles。
2. OFF → 新鲜 STS GPIO13=OFF RESET=IDLE。保持测试器 handle 并监测 uptime；发生错误、重启或通信丢失时，停止对主板的新操作。
3. 主板刷写和单独验证 — 只在它的许可范围内进行。不要发送 RESET/RST，也不要重启 USB 测试器。
4. 在完成主要操作并确认通信后执行允许的 ON，确认 STS。然后进行一次带有已验证连线的 GPIO25 的 RESET；确认 IDLE 并观察主板的新启动过程。
5. 单独评估启动/运行时和物理信号。成功的 UART 命令、STS 和计数器 GPIO33 不能证明接触点/WDI 或三个正常启动。

不要在 finally、出错时或关闭 helper 时自动发送 ON。
如果状态未知 — 保存证据并传递具体的下一步骤。
完整的备份已由用户禁用：`flash-settings.json`, full_backup_before_flash=false。在测试器闪存之前还有工厂/布局/镜像适配/SHA、一次刷写和单独验证；读取所需的引导分区/OTA 区域。`--backup` — 只有在请求时。

## USB 恢复与结果

[重启 USB 端口.ps1](../tools/restart_usb_port.ps1) 和 [USB_COM_RECOVERY](USB_COM_RECOVERY.md):
预览 → 准确的 InstanceId/新收据 → 应用/UAC。它会重新启动一个适配器，不保证断电，并且不会结束占用 COM 的进程。

保存命令/响应，主机/板的时间戳，SHA/身份，最后已知的状态和关闭句柄。在[ACCEPTANCE](ACCEPTANCE.md)中只写入验证过的结果；主机/构建、PnP重启、UART和硬件——各自独立确认。

---

<a id="en"></a>

## English

# Working with IC WDT Tester

Commands and their semantics: [COMMANDS](COMMANDS.md). Data format: [TELEMETRY](TELEMETRY.md).
Initial AI route: [AI_QUICKSTART](AI_QUICKSTART.md). This document describes the live order.

## Before Connection

Check the allowed scenario, role of each board, wiring, current COM and its unique owner. Previous owner ID/COM is only history. Do not terminate other processes or displace monitor. Chip model + factory eFuse BASE_MAC from [device-profile](../device-profile.json) define roles; USB/COM is transport.
After reconnection, verify mapping and identity before hardware actions/flashing. ROM check itself may reset: execute before main flash, not during it.

Even opening/closing Serial sometimes resets ESP32. Tester after reboot enables relay. Common GND, signals up to 3.3V, GPIO33 has an internal pull-up (INPUT_PULLUP); actual measurement point and NO/NC/COM contacts do not derive from GPIO names. Re-wire without power. GPIO0/WDI of the main board is not measured here.

## Selection of Actual Protocol

In an allowed session start with HELP at 115200/8N1 UTF-8, then STS.
[ACCEPTANCE](ACCEPTANCE.md) separates original revision from installed. Current main.cpp does not have identity command, READY/lease or UART loss counters.
Do not create READY for main flash based on one STS.

For regular commands, use `tools/current_protocol.py` over the common
Session from `tools/relay_bench_session.py`. The adapter does not open/close COM,
cancels access after protocol/transport error. RST is checked by capability;
after sending it, old uptime and access are reset. Direct write accepts
canonical commands; STATUS is an alias on the board, use STS for the adapter.

The exact help line `RESET: relay OFF, GPIO25 LOW for 1000 ms, GPIO25 INPUT (Hi-Z), relay ON`
confirms new RESET semantics. Without it do not assume relay switching.
RESET100/HISTORY/RESETDIAG/RST also check against corresponding help lines.
The new help provides `JSON: human text then pipe + JSON object; schema=1; types=status,gpio_change,gpio_history`.
The old help with `separate lines start with JSON` indicates the old format; parser reads both.

`tester_control.py` and legacy Session commands are designed for [LATCH-02](LEGACY_LATCH02.md).
Do not call legacy Session.close(): it may send release/ON. The session owner
closes handles and logs without implicit GPIO command.

## Authorized OFF / main flash / ON / RESET

1. Confirm both boards and wiring; record the exact image/SHA, initial state, rollback plan, and verification scheme. Fixate tester owners/handles for the duration of the scenario.
2. OFF → fresh STS GPIO13=OFF RESET=IDLE. Save tester handle and uptime; if an error, reboot or loss of communication occurs, stop new main operations.
3. Main board flashing and separate verification — only within its permitted scope. Do not send RESET/RST, nor restart USB tester during writing.
4. After completing the main operation and confirming communication, execute allowed ON, confirm STS. Then one RESET with verified wiring GPIO25; confirm IDLE and observe new main board boot process.
5. Evaluate startup/runtime and physical signals separately. A successful UART command, STS, and counter GPIO33 do not prove contact points/WDI or three normal boots.

Do not automatically send ON in finally, on error, or when closing the helper.
If the state is unknown — save evidence and pass on a specific next step.
The full backup has been disabled by the user: `flash-settings.json`, full_backup_before_flash=false. Before tester flash remains factory/layout/image-fit/SHA, one write and separate verification; reading required boot/partition/OTA areas. `--backup` — only on request.

## USB recovery and result

[restart_usb_port.ps1](../tools/restart_usb_port.ps1) and [USB_COM_RECOVERY](USB_COM_RECOVERY.md):
preview → exact InstanceId/new receipt → Apply/UAC. It restarts one adapter, does not guarantee power off, and does not terminate the COM process that has captured it.

Save commands/responses, host/board timestamps, SHA/identity, last known state and closed handles. In [ACCEPTANCE](ACCEPTANCE.md), write only the verified result; host/build, PnP restart, UART and hardware — separate confirmations.
