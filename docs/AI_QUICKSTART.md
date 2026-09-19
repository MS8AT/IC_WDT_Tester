[Русский](#ru) · [中文](#zh) · [English](#en)

<a id="ru"></a>

## Русский

# Другому ИИ: начать здесь

Это проект отдельного IC WDT Tester. Сначала прочитать [AGENTS](../AGENTS.md)
и [ACCEPTANCE](ACCEPTANCE.md). Не считать исходник или успешную сборку доказательством
того, что такая программа установлена на плате.

Текущий исходник: GPIO13 реле, GPIO25 RESET только LOW → INPUT без pull-up,
GPIO33 наблюдение EN, GPIO2 LED Wi-Fi. Подробности — [COMMANDS](COMMANDS.md).
Пользователь сообщил о переносе провода RESET на GPIO25; не просить повторить
уже подтверждённый перенос. Новая запись/установка остаётся отдельной проверкой.
Карта всех файлов и Del — [PROJECT_LAYOUT](PROJECT_LAYOUT.md). Старые инструкции
в Del не определяют текущие действия. COM не открывать ради чтения журнала.

Журнал работы ИИ: прочитать локальный WORK_JOURNAL (local workspace reference).
Если пути ещё нет, спросить пользователя, на каком диске и в какой папке вести
журнал, проверить место/запись и оставить здесь ссылку. Уже выбранный путь
использовать повторно; полный порядок — в [навыке проекта](../skills/esp32-ic-wdt-tester/SKILL.md).
В публичном snapshot локального указателя нет: создать его после выбора папки.

## Выбор задачи

| Задача | Читать / использовать |
| --- | --- |
| Узнать команды и пины | [COMMANDS](COMMANDS.md), `src/main.cpp` |
| IN1232N / DS1232LP, порог и таймаут | [IC_WDT_HARDWARE](IC_WDT_HARDWARE.md), [PDF и редакции](datasheets/README.md); TOL/TD не управляются командами тестера |
| Получать данные для анализа | [TELEMETRY](TELEMETRY.md), `tools/read_telemetry.py` |
| Управлять стендом | [OPERATOR](OPERATOR.md), `tools/current_protocol.py` |
| USB-COM занят/не работает | [USB_COM_RECOVERY](USB_COM_RECOVERY.md) |
| Изменить код / проверить offline | [CODE_STYLE](CODE_STYLE.md), `tools/project.py` |
| Передать или перенести | [HANDOFF](HANDOFF.md), [PORTABILITY](PORTABILITY.md) |
| Пересмотреть файлы / перенести лишнее | [PROJECT_LAYOUT](PROJECT_LAYOUT.md) |

## Чтение данных

Человеку сохранять обычный вывод слева. Справа после **` | JSON `** находится JSON.
Старые отдельные строки `JSON {...}` также читаются парсером.
Типы main.cpp: `status`, `gpio_change`, `gpio_history`; RelayResetBench: `wdt_pin`, schema=1.
Готовый проверяющий парсер не открывает COM:

```powershell
python -B tools/read_telemetry.py --input serial.txt --output telemetry.jsonl
```

Файл должен содержать исходные строки UART. Если logger добавил время хоста,
использовать его исходное поле `text` без префикса хоста. Не извлекать случайные
фигурные скобки из человеческого сообщения. Прежние строки без метки принимаются
только с явным `--allow-unprefixed`. Повреждённая JSON-строка означает потерю данных,
а не нулевые значения. Поля, ограничения и возвращаемые коды — TELEMETRY.

## Команды и транспорт

Команды передаются текстом, не JSON. В разрешённой live-сессии начать с HELP/STS
и подтвердить нужные capabilities. Один процесс владеет UART; другие ИИ читают
его журнал/поток, а не открывают тот же COM вторым процессом.

`CurrentProtocol(session)` работает поверх существующего Session, сам COM не
открывает и не закрывает. Он разбирает совместимую первую строку STS; новые JSON
поля доступны через `parse_telemetry_line(record['text'])` из read_telemetry.
`Session.close()` относится к legacy и может отправить release/ON: не вызывать
для текущего main.cpp; владелец закрывает handles/журнал без GPIO-команды.
После ошибки прекращать новые воздействия. После RST нужен новый HELP/STS.

RST и USB restart могут вернуть реле ON. RESET в новой ревизии тоже включает
реле после импульса. Во время main flash эти действия запрещены сценарием.
GPIO33/event_id — переходы входа, не доказанные срабатывания WDT.

Наведение порядка в проекте само по себе не разрешает прошивку или live-сценарий.
Для них использовать существующее разрешение на точную операцию либо получить новое.

---

<a id="zh"></a>

## 中文

# 另一个AI：从这里开始

这是一个独立IC WDT Tester项目。首先阅读[AGENTS](../AGENTS.md)和[ACCEPTANCE](ACCEPTANCE.md)。不要认为源代码或成功构建是该程序已安装在板上的证据。

当前的源码为：GPIO13继电器，GPIO25 RESET仅LOW → INPUT无上拉，GPIO33观察EN，GPIO2 LED Wi-Fi。详情见[COMMANDS](COMMANDS.md)。用户报告将 RESET 接线移至 GPIO25；不要要求重复已确认的移动操作。新的刷写/安装仍须单独验证。文件列表和Del — [PROJECT_LAYOUT](PROJECT_LAYOUT.md)。Del 中的旧指令不决定当前操作。COM不要打开以读取日志。

AI工作日志：阅读本地WORK_JOURNAL（本地工作区引用）。如果路径尚不存在，询问用户在哪个磁盘上的哪个文件夹中记录日志，并检查存储空间和写入权限并在此处留下链接。已选择的路径重复使用；完整顺序见[项目技能](../skills/esp32-ic-wdt-tester/SKILL.md)。公开快照不包含本地日志指针：选择文件夹后再创建指针。

## 选择任务

| 任务 | 阅读 / 使用 |
| --- | --- |
| 学习命令和引脚 | [COMMANDS](COMMANDS.md), `src/main.cpp` |
| IN1232N / DS1232LP, 门限和超时 | [IC_WDT_HARDWARE](IC_WDT_HARDWARE.md), [PDF 和版本](datasheets/README.md); TOL/TD 不由测试器命令控制 |
| 获取用于分析的数据 | [TELEMETRY](TELEMETRY.md), `tools/read_telemetry.py` |
| 控制平台 | [OPERATOR](OPERATOR.md), `tools/current_protocol.py` |
| USB-COM 占用/不工作 | [USB_COM_RECOVERY](USB_COM_RECOVERY.md) |
| 更改代码 / 离线验证 | [CODE_STYLE](CODE_STYLE.md), `tools/project.py` |
| 传递或转移 | [HANDOFF](HANDOFF.md), [PORTABILITY](PORTABILITY.md) |
| 检查文件 / 移放多余文件 | [PROJECT_LAYOUT](PROJECT_LAYOUT.md) |

## 读取数据
人类保存左侧的常规输出。右侧在 **` | JSON `** 后是 JSON。
旧单独行 `JSON {...}` 也由解析器读取。
type main.cpp: `status`, `gpio_change`, `gpio_history`; RelayResetBench: `wdt_pin`, schema=1.
现成的验证解析器不打开 COM:

```powershell
python -B tools/read_telemetry.py --input serial.txt --output telemetry.jsonl
```

文件应包含原始 UART 行。如果日志记录器添加了主机时间，
使用其原始字段 `text` 而无主机前缀。不要从人类消息中提取随机的
花括号。未标记的旧行仅接受明确的 `--allow-unprefixed`。损坏的 JSON 行意味着数据丢失，
而不是零值。字段、限制和返回代码 — TELEMETRY。
## 命令和传输

命令以文本形式发送，而不是JSON。在允许的实时会话中，从HELP/STS开始，并确认所需的capabilities。一个进程控制UART；其他AI读取其日志流，而不是通过第二个进程打开相同的COM端口。

`CurrentProtocol(session)`运行在一个现有的Session之上，它自己不打开或关闭COM端口。它解析兼容的第一行STS；新的JSON字段可以通过`parse_telemetry_line(record['text'])`从read_telemetry中获取。
`Session.close()`涉及legacy，并可能发送release/ON：不要为当前的main.cpp调用它；所有者在没有GPIO命令的情况下关闭句柄/日志。
错误后停止新的操作。RST之后需要一个新的HELP/STS。

RST和USB重启可以将继电器恢复到ON状态。新版本中的RESET也包括一个脉冲后的继电器开启。在主板刷写期间，操作方案禁止这些动作。GPIO33/event_id — 输入转换，未证实的WDT触发。

项目本身整理并不能授权固件更新或实时场景。对于它们，请使用现有的特定操作权限或者获取新的。

---

<a id="en"></a>

## English

# Another AI: start here

This is a standalone IC WDT Tester project. First, read [AGENTS](../AGENTS.md) and [ACCEPTANCE](ACCEPTANCE.md). Do not consider the source code or successful build as proof that such a program is installed on the board.

The current source code: GPIO13 relay, GPIO25 RESET only LOW → INPUT no pull-up, GPIO33 observe EN, GPIO2 LED Wi-Fi. Details are in [COMMANDS](COMMANDS.md). A user reported moving the RESET wire to GPIO25; do not ask for a repeat of an already confirmed move. New flash writes/installations remain separate verifications. File list and Del — [PROJECT_LAYOUT](PROJECT_LAYOUT.md). Old instructions in Del do not define current actions. COM should not be opened just to read logs.

AI work log: read the local WORK_JOURNAL (local workspace reference). If the path does not yet exist, ask the user which disk and folder to keep the journal in, check available space and write access and leave a link here. The chosen path is reused; full order is in [project skill](../skills/esp32-ic-wdt-tester/SKILL.md). There's no local pointer in public snapshots: create it after selecting the folder.

## Choosing a task

| Task | Read / Use |
| --- | --- |
| Learn commands and pins | [COMMANDS](COMMANDS.md), `src/main.cpp` |
| IN1232N / DS1232LP, threshold and timeout | [IC_WDT_HARDWARE](IC_WDT_HARDWARE.md), [PDF and versions](datasheets/README.md); TOL/TD not controlled by tester commands |
| Obtain data for analysis | [TELEMETRY](TELEMETRY.md), `tools/read_telemetry.py` |
| Control the platform | [OPERATOR](OPERATOR.md), `tools/current_protocol.py` |
| USB-COM occupied/not working | [USB_COM_RECOVERY](USB_COM_RECOVERY.md) |
| Modify code / offline verification | [CODE_STYLE](CODE_STYLE.md), `tools/project.py` |
| Transfer or move | [HANDOFF](HANDOFF.md), [PORTABILITY](PORTABILITY.md) |
| Review files / relocate surplus files | [PROJECT_LAYOUT](PROJECT_LAYOUT.md) |

## Reading data
Human to save regular output on the left. JSON is after **` | JSON `** on the right.
The old individual lines `JSON {...}` are also read by the parser.
type main.cpp: `status`, `gpio_change`, `gpio_history`; RelayResetBench: `wdt_pin`, schema=1.
A ready validating parser does not open COM:

```powershell
python -B tools/read_telemetry.py --input serial.txt --output telemetry.jsonl
```

The file should contain original UART lines. If the logger added host time,
use its original field `text` without a host prefix. Do not extract arbitrary
curly braces from human messages. Unmarked old lines are only accepted with explicit `--allow-unprefixed`. A damaged JSON line means data loss,
not zero values. Fields, constraints and return codes — TELEMETRY.
## Commands and transport

Commands are sent as text, not JSON. In an allowed live session, start with HELP/STS and confirm the required capabilities. One process controls the UART; other AIs read its log stream rather than opening the same COM port via a second process.

`CurrentProtocol(session)` operates on top of an existing Session; it does not open or close the COM port itself. It parses the compatible first line STS; new JSON fields are available through `parse_telemetry_line(record['text'])` from read_telemetry.
`Session.close()` relates to legacy and may send release/ON: do not call for current main.cpp; owner closes handles/log without a GPIO command.
After an error, stop new operations. After RST, a new HELP/STS is needed.

RST and USB restarts can return the relay to ON state. RESET in the new revision also includes relay activation after a pulse. During main flashing, these actions are prohibited by the operating scenario. GPIO33/event_id — input transitions, unconfirmed WDT triggers.

Organizing the project does not itself authorize flashing or live operation. Use existing authorization for the exact operation or obtain new authorization.
