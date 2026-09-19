[Русский](#ru) · [中文](#zh) · [English](#en)

<a id="ru"></a>

## Русский

# JSON для ИИ и обычный вывод для человека

Serial остаётся смешанным UTF-8 потоком: обычные строки/эмодзи и отдельные
JSON справа в той же строке: **`текст для человека | JSON {...}`**.
Точный разделитель — ` | JSON `; справа один полный JSON-объект до конца строки.
Старые отдельные строки `JSON {...}` также читаются. Команды вводятся обычным
текстом — [COMMANDS](COMMANDS.md). Это контракт исходной ревизии, не доказательство установки.

## Какие записи есть

| `type` | Когда появляется | Что означает |
| --- | --- | --- |
| `status` | Один раз в ответ на STS или STATUS | Снимок состояния тестера |
| `gpio_change` | Один раз на подтверждённый переход GPIO33 | Событие входа после фильтра 40 мс |
| `gpio_history` | Каждая строка HISTORY, включая автоматическую таблицу | Повтор сохранённого события, replay=true |
| `wdt_pin` | RelayResetBench: boot/status/edge/command/release | Отдельный legacy-контракт ниже |

Первая строка STS сохранена для CurrentProtocol. JSON справа от последней строки
подробностей STS или соответствующего перехода/строки истории.
HISTORY использует **gpio_history**, не gpio_change; повтор не является новым событием.
В main.cpp HELP, ON/OFF, RESET/RESET100, RST,
RESETDIAG пока имеют текстовые ответы; их наличие не означает новую JSON-запись.

## Поля schema=1

| Поле | Тип и смысл |
| --- | --- |
| `schema` | Целое 1; версия структуры |
| `type` | `status`, `gpio_change` или `gpio_history` для main.cpp |
| `source`, `subsystem` | Новая ревизия: ic_wdt_tester и WDT |
| `unix_time` | Целые секунды UTC от Unix epoch; до NTP `null` |
| `time_valid` | Boolean; можно ли использовать unix_time |
| `uptime_ms` | Millis с запуска, 32 бита; не Unix milliseconds |
| `relay_on`, `reset_active` | Boolean; программное состояние реле и внешнего сброса |

Дополнительно `status`:

| Поле | Тип и смысл |
| --- | --- |
| `local_time` | `DD.MM.YYYY HH:MM:SS` в TZ_INFO из main.cpp; до NTP `null` |
| `relay_on_after_reset` | Boolean; запланировано ли включение реле после сброса |
| `gpio12` | Цифровое чтение GPIO12: HIGH/LOW |
| `gpio25`, `reset_gpio` | Новая ревизия: уровень GPIO25 и номер RESET-вывода 25; старые записи этих полей не имеют |
| `reset_drive` | Заданный режим GPIO25: LOW во время сброса, HI_Z после отпускания; старые записи поля не имеют |
| `gpio33`, `gpio33_raw` | Фильтрованный и сырой GPIO33: HIGH/LOW |
| `wifi_connected` | Boolean; текущее подключение |
| `ip`, `rssi_dbm` | Строка IPv4 и целое dBm; без Wi-Fi оба `null` |
| `ntp_synced` | Boolean; часы синхронизированы; совпадает с time_valid |
| `events_total`, `history_count` | Число переходов с запуска и размер RAM-истории (0..10) |

Дополнительно `gpio_change`/`gpio_history`: `event_id` (целый номер), `gpio` (33),
`old`/`new` (HIGH/LOW). Время, relay_on и reset_active сохранены при регистрации
события. Поздний HISTORY не заменяет это время текущим и не добавляет NTP задним числом.
Новые поля: signal=EN, wdt_triggered=null (причина не установлена), replay=false
для gpio_change и true для gpio_history. Для подсчёта исключать replay или
удалять дубли по (сессия загрузки, source, gpio, event_id). Время в квадратных
скобках слева добавляет терминал при выводе, это не время события.

## Пример одной полной записи

```text
UNIX_TIME=null | 🔔 WDT/EN GPIO33 #1: HIGH -> LOW | 🕒 ⏳ | ⏱ 00:00:00.050 | JSON {"unix_time":null,"schema":1,"source":"ic_wdt_tester","subsystem":"WDT","signal":"EN","wdt_triggered":null,"type":"gpio_change","replay":false,"event_id":1,"uptime_ms":50,"time_valid":false,"gpio":33,"old":"HIGH","new":"LOW","relay_on":true,"reset_active":false}
```

Нет времени — хранить `null`, а не 0 или время компьютера. После NTP часы идут
и без Wi-Fi; ntp_synced не доказывает свежую связь с сервером. Для расчётов
использовать unix_time UTC; local_time служит отображению в настроенной TZ.
Смена TZ в этой задаче не выполнялась.

После переноса RESET с GPIO12 на GPIO25 поле `gpio12` сохраняет буквальный смысл:
чтение физического GPIO12, который больше не управляет сбросом. RESET читается
по `reset_gpio=25` и `gpio25`. Это дополнительные поля schema=1; старые записи
принимаются парсером, новые поля при наличии проверяются. По одному `gpio12`
состояние внешнего сброса новой ревизии не определять.

## Готовый парсер без COM

```powershell
python -B tools/read_telemetry.py --input serial.txt --output telemetry.jsonl
```

Без `--input` читает stdin; без `--output` пишет stdout. Выход — чистый JSONL
без метки, по одному объекту на строку. Существующий выходной файл не перезаписывает.
Код 0 — разбор без ошибок (в том числе 0 записей), 1 — повреждённые/неподдерживаемые
машинные строки, 2 — ошибка файла/аргументов. При коде 1 корректные строки сохранены,
номер проблемной строки указан в stderr; отсутствие записей само по себе не PASS устройства.

Из Python (путь `tools` должен быть доступен импорту):

```python
from read_telemetry import parse_telemetry_line

record = parse_telemetry_line(raw_serial_line)
if record is not None:
    kind = record['type']
```

Строка без машинного разделителя/префикса возвращает None; неверный JSON/schema/type/тип полей — ValueError.
Предыдущая исходная ревизия печатала `{...}` без метки: поддерживается только
явным `--allow-unprefixed` или одноимённым аргументом функции. Повторяющиеся
ключи и NaN/Infinity отклоняются. Лишние поля разрешены для расширений schema=1.
Логи с префиксом времени хоста сначала преобразовать в исходное поле text транспорта;
использовать точный разделитель ` | JSON ` или старый префикс `JSON `, не случайные скобки.

UART открывает один владелец. ИИ анализирует его файлы/records, не второй COM handle.
event_id и uptime обнуляются после reboot; сопоставлять с текущей сессией.
32-битные счётчики переполняются. Пропуск номеров — признак возможной потери,
но отсутствие пропусков не доказывает отсутствие аппаратных событий: фильтр может
подавить короткий импульс. GPIO33 не сообщает причину сброса; не называть
events_total числом срабатываний WDT. JSON не заменяет factory identity или
проверку контактов. Телеметрия/история в UART занимают время; физические длительности
нужно измерять отдельно.

## RelayResetBench.h: сохранённый вариант

Этот файл не входит в текущую сборку main.cpp. Его JSON имеет type=wdt_pin,
source=relay_bench, subsystem=WDT, gpio=13 или 33 и level=0 или 1.
signal=relay_control обозначает заданный уровень GPIO13; signal=EN — наблюдение
GPIO33. event: boot/status/edge/command/release; reason объясняет источник записи.
uptime_us — 64-битное время с запуска, для edge сохранённое в ISR/фильтре,
для release — при отпускании, а не при поздней печати. NTP здесь нет:
unix_time=null и time_valid=false. wdt_triggered=null: причина EN неизвестна.
event_id для EN — номер перехода, для реле — command ID; status повторяет последний ID.
Человеческие RELAY_BENCH ответы и их счётчики потерь сохранены. JSON печатается
только в task context, вне ISR/таймера/critical section; одна JSON-строка помещается
в 384-байтовый буфер Auto_Serial. Потерянные UART-данные не восстанавливаются JSON.

## План и проверка формата 19.09.2026

- [x] Текст слева, полный JSON справа, один точный разделитель.
- [x] Время события, GPIO, уровень, источник и назначение WDT/EN.
- [x] История сохраняет исходное время и явно помечена replay.
- [x] Старый и новый формат читаются одним offline-парсером.
- [x] Реальный C++ вывод проверен парсером; нет выдуманного подтверждения WDT.
- [ ] Подтвердить установленный образ и фактический UART после прошивки.

---

<a id="zh"></a>

## 中文

# 面向 AI 的 JSON 与面向用户的普通输出

Serial 仍是混合 UTF-8 流：普通文本/表情和同一行右侧的独立 JSON：**`текст для человека | JSON {...}`**。精确分隔符为 ` | JSON `；右侧是一个完整的 JSON 对象，一直到行末。旧的独立 `JSON {...}` 行也可读取。命令以普通文本输入，见 [COMMANDS](COMMANDS.md)。这是源码版本的协议，不证明固件已安装。

## 记录类型

| `type` | 何时出现 | 含义 |
| --- | --- | --- |
| `status` | 每次 STS 或 STATUS 回复中一次 | 测试器状态快照 |
| `gpio_change` | 每次确认 GPIO33 电平变化时一次 | 经过 40 ms 滤波后的输入事件 |
| `gpio_history` | HISTORY 的每一行，包括自动表格 | 重放已保存事件，replay=true |
| `wdt_pin` | RelayResetBench: boot/status/edge/command/release | 下文所述的独立 legacy 协议 |

STS 第一行保留给 CurrentProtocol。JSON 位于 STS 最后一行详细信息，或相应电平变化/历史行的右侧。HISTORY 使用 **gpio_history**，不是 gpio_change；重放不是新事件。main.cpp 的 HELP、ON/OFF、RESET/RESET100、RST、RESETDIAG 目前使用文本回复；出现这些回复不意味着有新的 JSON 记录。

## schema=1 字段

| 字段 | 类型和意义 |
| --- | --- |
| `schema` | 整数 1；结构版本 |
| `type` | `status`，`gpio_change` 或 `gpio_history` 对于 main.cpp |
| `source`, `subsystem` | 新修订版：ic_wdt_tester 和 WDT |
| `unix_time` | UTC 自 Unix 纪元的整数秒；直到 NTP `null` |
| `time_valid` | 布尔值；是否可以使用 unix_time |
| `uptime_ms` | 从启动开始的毫秒，32位；不是 Unix 毫秒 |
| `relay_on`, `reset_active` | 布尔值；继电器和外部复位的软件状态 |

额外信息 `status`：

| 字段 | 类型和意义 |
| --- | --- |
| `local_time` | TZ_INFO 中的 `DD.MM.YYYY HH:MM:SS` 从 main.cpp；直到 NTP `null` |
| `relay_on_after_reset` | 布尔值；继电器在复位后是否计划开启 |
| `gpio12` | GPIO12 的数字读取：HIGH/LOW |
| `gpio25`, `reset_gpio` | 新修订版：GPIO25 的电平和 RESET 输出引脚 25 的编号；旧记录没有这些字段 |
| `reset_drive` | GPIO25 设置的模式：复位期间为 LOW，释放后为 HI_Z；旧记录不包含此字段 |
| `gpio33`, `gpio33_raw` | 过滤后的和原始的 GPIO33：HIGH/LOW |
| `wifi_connected` | 布尔值；当前连接状态 |
| `ip`, `rssi_dbm` | IPv4 字符串和整数 dBm；没有 Wi-Fi 时两者都为 `null` |
| `ntp_synced` | 布尔值；时间同步；与 time_valid 相同 |
| `events_total`, `history_count` | 自启动以来输入电平变化的次数和 RAM 历史记录大小（0..10）|

更多详情 `gpio_change`/`gpio_history`: `event_id` (整数编号), `gpio` (33),
`old`/`new` (HIGH/LOW). 时间、relay_on 和 reset_active 在事件注册时保存。
晚些时候的 HISTORY 不会用当前时间替换它，也不会事后补上 NTP 时间。
新字段：signal=EN, wdt_triggered=null（原因未设置），replay=false
用于 gpio_change 而 true 用于 gpio_history。在计数中排除 replay 或删除重复项 (启动会话、来源、GPIO、事件ID)。左方的 [时间] 在输出时添加终端，这不是事件时间。

## 示例完整记录
```text
UNIX_TIME=null | 🔔 WDT/EN GPIO33 #1: HIGH -> LOW | 🕒 ⏳ | ⏱ 00:00:00.050 | JSON {"unix_time":null,"schema":1,"source":"ic_wdt_tester","subsystem":"WDT","signal":"EN","wdt_triggered":null,"type":"gpio_change","replay":false,"event_id":1,"uptime_ms":50,"time_valid":false,"gpio":33,"old":"HIGH","new":"LOW","relay_on":true,"reset_active":false}
```
没有时间 — 保存 `null` 而不是 0 或计算机的时间。NTP 同步后即使没有 Wi-Fi，时间也会继续运行；ntp_synced 并不证明与服务器的最新连接。计算时使用 UTC 的 unix_time；local_time 用于在配置的 TZ 中显示。
在此任务中未执行时区更改。

将 RESET 从 GPIO12 移动到 GPIO25 后，字段 `gpio12` 保留其原始含义：读取物理 GPIO12，它不再控制重置。RESET 通过 `reset_gpio=25` 和 `gpio25` 读取。
这是额外的 schema=1 字段；旧记录被解析器接受，新字段在存在时进行验证。不能仅凭 `gpio12` 判断新硬件版本的外部复位状态。

## 无需 COM 的现成解析器

```powershell
python -B tools/read_telemetry.py --input serial.txt --output telemetry.jsonl
```

没有`--input`从stdin读取；没有`--output`向stdout写入。输出是一个干净的JSONL
不带标签，每行一个对象。现有输出文件不会被覆盖。
返回码0表示无错误解析（包括零条记录），1表示损坏/不受支持的机器行，2表示文件或参数错误。当返回码为1时，正确的行会被保留，问题行号会在stderr中指出；没有记录本身并不意味着PASS设备。

从Python（路径`tools`必须可导入）：
```python
from read_telemetry import parse_telemetry_line

record = parse_telemetry_line(raw_serial_line)
if record is not None:
    kind = record['type']
```

不带机器分隔符/前缀的行返回None；错误的JSON/schema/type/字段类型会引发ValueError。先前版本的源代码在没有标签的情况下打印了`{...}`，只支持明确的`--allow-unprefixed`或函数的一个同名参数。重复的键和NaN/Infinity会被拒绝。额外的字段允许用于schema=1扩展。
带有主机时间前缀的日志首先转换为传输原始文本字段；使用精确分隔符` | JSON `或旧前缀`JSON `，而不是随机括号。

UART只有一个所有者。AI分析其文件/记录，而不是第二个COM句柄。
event_id和uptime在重启后被重置；与当前会话进行匹配。
32位计数器可能会溢出。跳过的编号是可能丢失的标志，
但没有跳过并不证明没有硬件事件：过滤器可以抑制短暂脉冲。GPIO33不报告复位原因；不要将events_total视为WDT触发次数。
JSON不能替代工厂标识或接触检查。UART中的遥测/历史记录需要时间；物理持续时间必须单独测量。

## RelayResetBench.h：保留的旧版本

此文件不参与当前 main.cpp 的构建。其 JSON 使用 type=wdt_pin、source=relay_bench、subsystem=WDT、gpio=13 或 33，以及 level=0 或 1。signal=relay_control 表示 GPIO13 的设定电平；signal=EN 表示 GPIO33 的观测值。event 为 boot/status/edge/command/release；reason 说明记录来源。

uptime_us 是启动以来的 64 位时间：edge 的时间保存在 ISR/滤波器中，release 的时间在释放时保存，而不是在稍后打印时确定。此处没有 NTP：unix_time=null，time_valid=false。wdt_triggered=null：EN 的变化原因未知。EN 的 event_id 为电平转换编号，继电器的 event_id 为 command ID；status 重复最新的 ID。

面向用户的 RELAY_BENCH 响应及其丢失计数器保持不变。JSON 只在任务上下文中打印，不在 ISR/定时器/临界区中打印；一行 JSON 可放入 Auto_Serial 的 384 字节缓冲区。JSON 无法恢复丢失的 UART 数据。

## 2026年9月19日格式验证计划

- [x] 文本在左侧，完整的 JSON 在右侧，一个精确的分隔符。
- [x] 事件时间、GPIO、电平、来源和 WDT/EN 的目标。
- [x] 历史记录保留原始时间，并明确标记为重播。
- [x] 旧格式和新格式由同一个离线解析器读取。
- [x] 实际的 C++ 输出已通过解析器验证；没有编造的 WDT 确认。
- [ ] 在编程后确认安装的映像和实际的 UART。

---

<a id="en"></a>

## English

# JSON for AI and normal output for users

Serial remains a mixed UTF-8 stream: ordinary text/emoji and separate JSON on the right of the same line: **`текст для человека | JSON {...}`**. The exact delimiter is ` | JSON `; one complete JSON object follows to the end of the line. Older standalone `JSON {...}` lines are also accepted. Commands are entered as ordinary text; see [COMMANDS](COMMANDS.md). This is the source revision's contract, not evidence of installation.

## Record types

| `type` | When it appears | Meaning |
| --- | --- | --- |
| `status` | Once in response to STS or STATUS | Tester state snapshot |
| `gpio_change` | Once per confirmed GPIO33 transition | Input event after the 40 ms filter |
| `gpio_history` | Each HISTORY row, including the automatic table | Replay of a stored event, replay=true |
| `wdt_pin` | RelayResetBench: boot/status/edge/command/release | Separate legacy contract below |

The first STS line is retained for CurrentProtocol. JSON appears to the right of the final STS detail line or the corresponding transition/history row. HISTORY uses **gpio_history**, not gpio_change; a replay is not a new event. In main.cpp, HELP, ON/OFF, RESET/RESET100, RST and RESETDIAG currently have text replies; their presence does not imply a new JSON record.

## schema=1 fields

| Field | Type and Meaning |
| --- | --- |
| `schema` | Integer 1; structure version |
| `type` | `status`, `gpio_change` or `gpio_history` for main.cpp |
| `source`, `subsystem` | New revision: ic_wdt_tester and WDT |
| `unix_time` | Integer seconds UTC from Unix epoch; until NTP `null` |
| `time_valid` | Boolean; can unix_time be used |
| `uptime_ms` | Milliseconds since startup, 32 bits; not Unix milliseconds |
| `relay_on`, `reset_active` | Boolean; software state of relay and external reset |

Additional information `status`:

| Field | Type and Meaning |
| --- | --- |
| `local_time` | `DD.MM.YYYY HH:MM:SS` in TZ_INFO from main.cpp; until NTP `null` |
| `relay_on_after_reset` | Boolean; is relay planned to be turned on after reset |
| `gpio12` | Digital reading of GPIO12: HIGH/LOW |
| `gpio25`, `reset_gpio` | New revision: level of GPIO25 and number of RESET output pin 25; old records do not have these fields |
| `reset_drive` | Set mode of GPIO25: LOW during reset, HI_Z after release; old records do not contain this field |
| `gpio33`, `gpio33_raw` | Filtered and raw GPIO33: HIGH/LOW |
| `wifi_connected` | Boolean; current connection status |
| `ip`, `rssi_dbm` | IPv4 string and integer dBm; without Wi-Fi both are `null` |
| `ntp_synced` | Boolean; time synchronized; matches time_valid |
| `events_total`, `history_count` | Number of input transitions since startup and size of RAM history (0..10) |

Additional details `gpio_change`/`gpio_history`: `event_id` (integer), `gpio` (33),
`old`/`new` (HIGH/LOW). Time, relay_on and reset_active are saved upon event registration.
The later HISTORY does not replace this time with the current one or add NTP timestamps retroactively.
New fields: signal=EN, wdt_triggered=null (reason unset), replay=false
for gpio_change and true for gpio_history. Exclude replay in counting or remove duplicates by (boot session, source, GPIO, event_id). The [time] on the left is added to the terminal upon output; it's not the event time.

## Example of a complete record
```text
UNIX_TIME=null | 🔔 WDT/EN GPIO33 #1: HIGH -> LOW | 🕒 ⏳ | ⏱ 00:00:00.050 | JSON {"unix_time":null,"schema":1,"source":"ic_wdt_tester","subsystem":"WDT","signal":"EN","wdt_triggered":null,"type":"gpio_change","replay":false,"event_id":1,"uptime_ms":50,"time_valid":false,"gpio":33,"old":"HIGH","new":"LOW","relay_on":true,"reset_active":false}
```
No time — save `null` instead of 0 or computer time. After NTP sync, even without Wi-Fi, time continues running; ntp_synced does not prove latest connection to server. Use UTC unix_time for calculations; local_time is used for display in configured TZ.
Time zone change was not performed in this task.

After moving RESET from GPIO12 to GPIO25, field `gpio12` retains its literal meaning: reading physical GPIO12 which no longer controls reset. RESET is read via `reset_gpio=25` and `gpio25`. These are additional schema=1 fields; old records are accepted by the parser, new fields are validated if present. Do not infer the external reset state of the new revision from `gpio12` alone.

## Ready-to-use parser without COM

```powershell
python -B tools/read_telemetry.py --input serial.txt --output telemetry.jsonl
```

Without `--input` reading from stdin; without `--output` writing to stdout. Output is a clean JSONL
without labels, one object per line. Existing output file will not be overwritten.
Return code 0 indicates error-free parsing (including zero records), 1 indicates damaged/unsupported machine lines, and 2 indicates file or argument errors. When the return code is 1, correct lines are retained, problematic line numbers are indicated in stderr; absence of records itself does not mean PASS device.

From Python (path `tools` must be importable):
```python
from read_telemetry import parse_telemetry_line

record = parse_telemetry_line(raw_serial_line)
if record is not None:
    kind = record['type']
```

A line without a machine delimiter/prefix returns None; an incorrect JSON/schema/type/field type raises ValueError. The previous version's source code printed `{...}` without labels, this format is accepted only with explicit `--allow-unprefixed` or the corresponding named function argument. Duplicate keys and NaN/Infinity are rejected. Extra fields are allowed for schema=1 extensions.
Logs with host time prefix first convert to transport original text field; use the exact delimiter ` | JSON ` or old prefix `JSON `, not random brackets.

UART has one owner. AI analyzes its files/records, not a second COM handle.
event_id and uptime are reset after reboot; match with the current session.
32-bit counters may overflow. Skipped numbers indicate possible loss,
but no skipped numbers do not prove absence of hardware events: a filter can suppress short pulses. GPIO33 does not report reset reason; do not call events_total as WDT trigger count.
JSON does not replace factory identity or contact checks. Telemetry/history in UART takes time; physical durations must be measured separately.

## RelayResetBench.h: retained variant

This file is not part of the current main.cpp build. Its JSON has type=wdt_pin, source=relay_bench, subsystem=WDT, gpio=13 or 33 and level=0 or 1. signal=relay_control denotes the commanded GPIO13 level; signal=EN denotes observation of GPIO33. event is boot/status/edge/command/release; reason explains the record source.

uptime_us is the 64-bit time since startup, saved in the ISR/filter for an edge and at release for a release event, rather than at delayed printing. There is no NTP here: unix_time=null and time_valid=false. wdt_triggered=null: the cause of EN changes is unknown. For EN, event_id is the transition number; for the relay it is the command ID. status repeats the latest ID.

Human-readable RELAY_BENCH responses and their loss counters are retained. JSON is printed only in task context, outside the ISR/timer/critical section; one JSON line fits in the 384-byte Auto_Serial buffer. JSON does not recover lost UART data.

## Format verification plan, September 19, 2026

- [x] Text on the left, full JSON on the right, one precise delimiter.
- [x] Event time, GPIO, level, source and destination of WDT/EN.
- [x] History retains original timestamp and is explicitly marked as replay.
- [x] Old format and new format are read by a single offline parser.
- [x] Real C++ output has been verified by the parser; no fabricated WDT confirmation.
- [ ] Confirm installed image and actual UART after programming.
