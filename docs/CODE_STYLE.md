[Русский](#ru) · [中文](#zh) · [English](#en)

<a id="ru"></a>

## Русский

# Стиль отдельного прибора

Активный entrypoint — `src/main.cpp`, выбранный build_src_filter в platformio.ini.
Arduino ESP32 2.0.17, espressif32 7.0.1, WiFi/NTP для времени, Serial для команд.
setup предзагружает GPIO13 HIGH до OUTPUT; loop обслуживает команды, RESET,
фильтр GPIO33 и Wi-Fi/NTP без delay. Интервалы считаются разностью millis.
GPIO2 — активный HIGH LED Wi-Fi: ожидание 500 мс ON/500 мс OFF, попытка подключения
125/125 мс, WL_CONNECTED — постоянно HIGH. Окно быстрой индикации 5 секунд после
WiFi.begin; ошибка/истечение окна переводит в медленное мигание. Попытки повторяются
через 10 секунд; после потери связи отсчёт начинается заново. LED не ожидает NTP,
работает через millis без delay; GPIO13/25 не затрагивает. Физическая полярность
LED на плате пока не подтверждена; код рассчитан на включение при HIGH.
В текущей ревизии RESET перенесён на GPIO25. GPIO12 не конфигурируется как выход
и не переключается: это strap выбора напряжения flash при старте.
GPIO25 только притягивает RESET к LOW: перед OUTPUT предзагружается LOW,
отпускание — INPUT без внутренней подтяжки. HIGH в GPIO25 не записывать.
Имена GPIO/интервалов — constexpr; HELP и STS не меняют выходы.
OFF без таймера до ON, RESET или reboot; NVS нет. Ошибка ввода не включает реле.
Подготовленный HISTORY читает кольцевую историю10 переходов GPIO33. Таблица
печатается после событий, но откладывается до завершения активного RESET.
STS сохраняет первую совместимую строку; справа от последней строки подробностей — ` | JSON {...}` schema=1.
Событие GPIO33 получает Unix-время при регистрации и одну JSON-строку gpio_change.
До NTP unix_time=null; uptime_ms доступен всегда. История повторяет записи как
gpio_history/replay=true с исходным временем, не пишет GPIO и не определяет причину сброса.
Контракт — [TELEMETRY](TELEMETRY.md); команды — [COMMANDS](COMMANDS.md).
Новые строки: человек слева, ` | JSON {...}` справа. Source/subsystem/signal обозначают
WDT/EN; wdt_triggered=null, причина не установлена. Старый формат parser принимает.
Offline-парсер tools/read_telemetry.py не импортирует serial и не открывает COM.

Проверки: `python -B tools/project.py check`, `python -B tools/project.py test`.
Сборка: `python -B tools/sdk_preflight.py`, затем `pio run -e ic_wdt_tester`.
Только локальные .sdk/.pio; без установки пакетов и без COM.
Тест main.cpp исполняет реальный код с fake GPIO/UART, не физические контакты.
Его JSON разбирается тем же проверяющим парсером, которым пользуется другой ИИ.
Сохранённый RelayResetBench/Auto_Serial имеет отдельные legacy harnesses;
их PASS не является проверкой активной main.cpp.

---

<a id="zh"></a>

## 中文

# 单个设备的样式

主动入口点 — `src/main.cpp`，由 platformio.ini 中的 build_src_filter 选择。
Arduino ESP32 2.0.17, espressif32 7.0.1, WiFi/NTP 获取时间，Serial 处理命令。
setup 在将 GPIO13 配置为 OUTPUT 之前，先将输出锁存值设为 HIGH；loop 处理命令、RESET、GPIO33 过滤器和无 delay 的 Wi-Fi/NTP。间隔通过 millis 差值计算。
GPIO2 — 活动的 HIGH LED，用于指示 Wi-Fi：等待 500 ms ON/500 ms OFF，连接尝试为 125/125 ms，WL_CONNECTED 持续保持 HIGH。快速指示窗口在 WiFi.begin 后持续 5 秒；错误或超时导致慢速闪烁。重试间隔为 10 秒；失去连接后重新开始计数。LED 不等待 NTP，通过 millis 计算时间而无 delay；GPIO13/25 不受影响。
板载 LED 的物理极性尚未确认；代码假设 HIGH 状态时点亮。
当前修订版中 RESET 被移动到 GPIO25。GPIO12 未配置为输出且不切换：这是启动时 flash 电压选择的 strap。
GPIO25 只将 RESET 拉低至 LOW：在设置为 OUTPUT 前预先设置为 LOW，释放后变为 INPUT 无内部上拉；禁止向 GPIO25 写入 HIGH。
GPIO/间隔名称 — constexpr；HELP 和 STS 不改变输出。
OFF 在没有定时器的情况下保持到 ON、RESET 或重启；NVS 没有使用。输入错误不会触发继电器。
准备好的 HISTORY 读取环形历史记录，包含 GPIO33 的 10 次转换。表格在事件后打印，但推迟至主动 RESET 完成。
STS 保存第一行兼容数据，在最后一行详细信息右侧为 ` | JSON {...}` schema=1。
GPIO33 事件注册时获取 Unix 时间并记录一条 gpio_change JSON 字符串。
NTP 前 unix_time=null；uptime_ms 永远可用。历史记录重复记录，如 gpio_history/replay=true，使用原始时间戳，不写入 GPIO 并不定义重置原因。
协议 — [TELEMETRY](TELEMETRY.md)；命令 — [COMMANDS](COMMANDS.md)。
新行：左边是人，右边是 ` | JSON {...}`。source/subsystem/signal 标记为 WDT/EN；wdt_triggered=null，原因未定义。旧格式解析器接受。
离线工具 read_telemetry.py 不导入 serial 且不打开 COM。

检查：`python -B tools/project.py check`，`python -B tools/project.py test`。
构建：`python -B tools/sdk_preflight.py`，然后是`pio run -e ic_wdt_tester`。
仅限本地 .sdk/.pio；不安装包且无COM。
测试main.cpp执行实际代码与模拟的GPIO/UART，而非物理连接。
其JSON由另一个AI使用的相同验证解析器处理。
保存的RelayResetBench/Auto_Serial具有独立的 legacy 测试框架；
它们的PASS不是活动中的main.cpp检查。

---

<a id="en"></a>

## English

# Style of individual instrument

Active entry point — `src/main.cpp`, selected by build_src_filter in platformio.ini.
Arduino ESP32 2.0.17, espressif32 7.0.1, WiFi/NTP for time, Serial for commands.
The setup preloads GPIO13 to HIGH before setting it as OUTPUT; the loop handles commands, RESET, filter on GPIO33 and Wi-Fi/NTP without delay. Intervals are calculated by the difference of millis.
GPIO2 — active HIGH LED indicating Wi-Fi: waits 500 ms ON/500 ms OFF, connection attempts at 125/125 ms, WL_CONNECTED stays continuously HIGH. A quick indication window lasts for 5 seconds after WiFi.begin; errors or timeout cause slow blinking. Retries occur every 10 seconds; the count restarts upon loss of connection. The LED does not wait for NTP and operates through millis without delay; GPIO13/25 are unaffected.
The physical polarity of the onboard LED is yet to be confirmed; code assumes HIGH state turns it on.
In the current revision, RESET has been moved to GPIO25. GPIO12 is not configured as an output and does not switch: this is the strap for selecting flash voltage at startup.
GPIO25 only pulls RESET low to LOW: preloaded to LOW before setting OUTPUT, released to INPUT without internal pull-up; HIGH should never be written to GPIO25.
Names of GPIOs/Intervals — constexpr; HELP and STS do not change outputs.
OFF remains until ON, RESET or reboot without a timer; NVS is unused. Input errors do not trigger relays.
The prepared HISTORY reads the circular history of 10 transitions on GPIO33. The table prints after events but delays until active RESET completes.
STS saves the first compatible line with ` | JSON {...}` schema=1 to the right of the last detailed line.
A GPIO33 event registers Unix time and logs one gpio_change JSON string upon registration.
Before NTP, unix_time=null; uptime_ms is always available. History repeats entries as gpio_history/replay=true using original timestamps, does not write GPIOs, and does not define reset reasons.
The contract — [TELEMETRY](TELEMETRY.md); commands — [COMMANDS](COMMANDS.md).
New lines: human on the left, ` | JSON {...}` on the right. source/subsystem/signal marked as WDT/EN; wdt_triggered=null, reason undefined. The old format parser accepts.
The offline tool read_telemetry.py does not import serial and does not open COM.

Checks: `python -B tools/project.py check`, `python -B tools/project.py test`.
Build: `python -B tools/sdk_preflight.py`, then `pio run -e ic_wdt_tester`.
Local .sdk/.pio only; no package installation and no COM.
The test main.cpp runs actual code with fake GPIO/UART, not physical connections.
Its JSON is parsed by the same validating parser used by another AI.
The saved RelayResetBench/Auto_Serial has separate legacy harnesses;
their PASS is not a check of active main.cpp.
