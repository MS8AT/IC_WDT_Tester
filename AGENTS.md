[Русский](#ru) · [中文](#zh) · [English](#en)

<a id="ru"></a>

## Русский

# IC WDT Tester — вход для ИИ

Начать с [AI_QUICKSTART](docs/AI_QUICKSTART.md), затем читать документ по задаче
из [индекса](docs/INSTRUCTIONS_INDEX.md). [README](README.md) — краткий вход для человека.
Все группы файлов, зависимости и правила Del: [PROJECT_LAYOUT](docs/PROJECT_LAYOUT.md).

## Что считается текущим

- `platformio.ini` собирает только `src/main.cpp`. Команды — [COMMANDS](docs/COMMANDS.md).
- Исходники, собранный BIN и установленная программа — разные состояния;
  их подтверждения находятся в [ACCEPTANCE](docs/ACCEPTANCE.md).
- Слева текст для человека, справа ` | JSON {...}` — для ИИ; старый формат тоже читается.
  Контракт и готовый offline-парсер: [TELEMETRY](docs/TELEMETRY.md).
- В текущем коде OFF сохраняется до ON, RESET или reboot. RESET выполняет
  OFF → внешний сброс 1000 мс → отпускание → ON. RST перезапускает сам тестер.
- LATCH-02 — отдельная сохранённая реализация. Её READY/identity/lease
  не поддерживаются main.cpp; [исторический протокол](docs/LEGACY_LATCH02.md).
- Текущий исходник выводит внешний RESET на GPIO25; GPIO12 оставлен для boot strap.
  GPIO25: только OUTPUT LOW на импульс, затем INPUT (Hi-Z) без pull-up; не выдавать HIGH.
  Провод тестера GPIO12 → RESET/EN основной платы должен быть перенесён на GPIO25.
  Установку этой ревизии проверять по ACCEPTANCE и HELP (`GPIO25`), не по COM.
- GPIO2 — LED Wi-Fi: ожидание 1 Гц, подключение 4 Гц, соединение — HIGH постоянно.
  Индикация неблокирующая, NTP не является условием включения LED.
- История JSON имеет type=gpio_history/replay=true; исходное время сохраняется.
  Метка WDT/EN обозначает назначение входа, wdt_triggered=null — причина неизвестна.

## Границы работы

При запросе на выполнение USB-команд сначала продумать цель и порядок действий,
обновить дорожную карту и подготовить чек-лист текущего запуска в
[USB_RESTART_PLAN](USB_RESTART_PLAN.md). Затем выполнить разрешённые шаги,
проверить журнал/отчёты и отметить только фактически подтверждённые результаты.
Продолжать существующий план; старые выполненные пункты не считать проверкой
нового запуска. Сам план не требует повторного согласования уже разрешённого действия.
Ответы и ошибки USB launcher читать по `JSON {...}` или корневому
`usb-restart-events.jsonl`; готовый offline-reader — `tools/read_usb_restart_events.py`.
Сверять launch_id, RESULT/ERROR и END; отсутствие ошибки или END не доказывает успех.

Использовать команды тестера через существующий `CurrentProtocol` и общий Session,
не создавать второй relay driver. `tester_control.py` — только для LATCH-02.
До live нужны разрешённый сценарий, точные платы/проводка и один владелец COM.
Роль платы определяется chip model + factory eFuse BASE_MAC, COM — транспорт.
Не вытеснять владельца и не завершать его процессы. Подробности — [OPERATOR](docs/OPERATOR.md).
Существующее разрешение пользователя на конкретный сценарий сохраняется.

Offline: `python -B tools/project.py check/test`; COM не открывается.
Перед изменениями проверить dependency-lock.json; незапрошенный mismatch разобрать,
не перезаписывать digest вслепую. Запрошенную source revision отразить в lock.
Build: сначала `python -B tools/sdk_preflight.py`, затем локальные `.sdk/.pio`.
Сохранять оба IDE extensions. Не печатать локальную Wi-Fi конфигурацию из src/secrets.h.
Публикацию готовить через `project.py export --public`; образец — secrets.example.h.
Не включать BIN с рабочими Wi-Fi-настройками; публикация GitHub — отдельное действие.

Не удалять совместимые LATCH-02 исходники/helper/tests: на них ссылается IC_WDT_Probe.
SDK, build, rollback и live evidence сохранять; [PORTABILITY](docs/PORTABILITY.md).
Del исключён из рабочего входа и export; старые AGENTS/SKILL внутри не исполнять.
При уборке вести манифест переносов с SHA-256, обновлять ссылки и PROJECT_FILES;
не удалять физически и не перезаписывать новый файл при восстановлении.
Результат кратко фиксировать в ACCEPTANCE; root-регистрацию и журналы передавать
координатору. В полном WorckBook общие правила: AI_MASTER (local workspace reference),
карта AI_CODE_INDEX (local workspace reference); standalone не зависит от этих ссылок.

---

<a id="zh"></a>

## 中文

# IC WDT 测试器——AI 入口

从 [AI_QUICKSTART](docs/AI_QUICKSTART.md) 开始，然后阅读任务文档
来自 [索引](docs/INSTRUCTIONS_INDEX.md)。[README](README.md) — 面向用户的简明入口。
所有文件组、依赖项和Del 目录规则：[PROJECT_LAYOUT](docs/PROJECT_LAYOUT.md)。

## 当前版本的判定
- `platformio.ini` 仅编译 `src/main.cpp`。命令—— [COMMANDS](docs/COMMANDS.md)。
- 源代码、编译的 BIN 和安装的应用程序是不同的状态；
它们的确认位于 [ACCEPTANCE](docs/ACCEPTANCE.md)。
- 左侧为人类文本，右侧 ` | JSON {...}` 用于 AI；旧格式也可以读取。
协议和现成的离线解析器：[TELEMETRY](docs/TELEMETRY.md)。
- 在当前代码中，OFF 保持到 ON、RESET 或重启。RESET 执行
OFF → 外部复位 1000 毫秒 → 放开 → ON。RST 重新启动测试器本身。
- LATCH-02 是单独保存的实现。其 READY/identity/lease
不被 main.cpp 支持；[历史协议](docs/LEGACY_LATCH02.md)。
- 当前源代码将外部 RESET 输出到 GPIO25；GPIO12 保留作为启动配置引脚（boot strap）。
GPIO25: 只有 OUTPUT LOW 脉冲，然后 INPUT (Hi-Z)，不启用上拉；绝不输出 HIGH。
测试器的 GPIO12 → 主板的 RESET/EN 线应移至 GPIO25。
此修订版的安装检查请参考 ACCEPTANCE 和 HELP (`GPIO25`)，而不是 COM。
- GPIO2 — LED Wi-Fi: 等待时 1 Hz，连接过程中 4 Hz，已连接时持续 HIGH。
指示是非阻塞的，NTP 不是 LED 开启的条件。
- JSON 历史记录具有 type=gpio_history/replay=true；原始时间被保存。
WDT/EN 标记表示输入的目的，wdt_triggered=null 表示原因未知。

# 工作范围

收到执行USB命令的请求后，先考虑目标和操作顺序，更新路线图，并准备当前启动的检查清单，在[USB_RESTART_PLAN](USB_RESTART_PLAN.md)中。然后执行允许的操作步骤，检查日志/报告并仅标记实际确认的结果。
继续现有计划；旧完成的项目不被视为新启动的验证。该计划不需要对已批准的行为进行重新审批。
USB启动器的回答和错误在`JSON {...}`或根`usb-restart-events.jsonl`中查看，离线阅读器为`tools/read_usb_restart_events.py`。
核对launch_id、RESULT/ERROR和END；没有错误或END并不能证明成功。

通过现有的`CurrentProtocol`和通用Session使用测试命令，不要创建第二个继电器驱动程序。`tester_control.py`仅用于LATCH-02。
需要批准的场景、精确的电路板/布线以及一个COM所有者才能进行现场操作。
电路板的角色由芯片型号+工厂eFuse BASE_MAC定义，COM为传输层。
不要替换所有者或结束其进程。详情请参阅[OPERATOR](docs/OPERATOR.md)。
用户对特定场景的现有许可保持不变。

离线：`python -B tools/project.py check/test`；COM 不打开。
在更改前检查 dependency-lock.json；解析未请求的不匹配，不要盲目重写摘要。反映请求的 source revision 到 lock 中。
构建：先 `python -B tools/sdk_preflight.py`，然后本地 `.sdk/.pio`。
保存两个 IDE 扩展程序。不要从 src/secrets.h 输出本地 Wi-Fi 配置。
通过 `project.py export --public` 准备发布；示例为 secrets.example.h。
不包含带有工作 Wi-Fi 设置的 BIN 文件；GitHub 发布是单独的操作。

不要删除与 IC_WDT_Probe 相关的兼容 LATCH-02 源代码/辅助程序/测试：它们被引用了。
保存 SDK、构建、回滚和实时证据；[可移植性](docs/PORTABILITY.md)。
Del 从工作输入和导出中排除；不执行 Del 内的旧 AGENTS/SKILL 指令。
在清理时记录带有 SHA-256 的迁移清单，更新链接和 PROJECT_FILES；
不要实际删除文件；恢复时不要覆盖新文件。
简要记录结果到 ACCEPTANCE 中；将根注册和日志传递给协调员。
在整个 WorckBook 中有通用规则：AI_MASTER（本地工作区引用），
AI_CODE_INDEX 地图（本地工作区引用）；独立不依赖这些链接。

---

<a id="en"></a>

## English

# IC WDT Tester — AI entry point

Start with [AI_QUICKSTART](docs/AI_QUICKSTART.md), then read the task document
from [index](docs/INSTRUCTIONS_INDEX.md). [README](README.md) — a brief entry point for users.
All file groups, dependencies and Del directory rules: [PROJECT_LAYOUT](docs/PROJECT_LAYOUT.md).

## What is considered current
- `platformio.ini` builds only `src/main.cpp`. Commands — [COMMANDS](docs/COMMANDS.md).
- Source code, compiled BIN, and installed application are different states;
their confirmations are located in [ACCEPTANCE](docs/ACCEPTANCE.md).
- Left side is human text, right side ` | JSON {...}` for AI; old format can also be read.
Contract and ready-made offline parser: [TELEMETRY](docs/TELEMETRY.md).
- In the current code, OFF persists until ON, RESET or reboot. RESET performs
OFF → external reset 1000 ms → release → ON. RST restarts the tester itself.
- LATCH-02 is a separately saved implementation. Its READY/identity/lease
are not supported by main.cpp; [historical protocol](docs/LEGACY_LATCH02.md).
- The current source code outputs external RESET to GPIO25; GPIO12 reserved as a boot strap.
GPIO25: only OUTPUT LOW pulse, then INPUT (Hi-Z), no pull-up; never output HIGH.
The tester's GPIO12 → main board's RESET/EN line should be moved to GPIO25.
Check the installation of this revision by referring to ACCEPTANCE and HELP (`GPIO25`) instead of COM.
- GPIO2 — LED Wi-Fi: waiting at 1 Hz, connecting at 4 Hz, connected continuously HIGH.
The indication is non-blocking; NTP is not a condition for turning on the LED.
- JSON history has type=gpio_history/replay=true; original time is preserved.
The WDT/EN label indicates the purpose of the input, wdt_triggered=null means cause unknown.

# Scope of Work

When asked to execute USB commands, consider the goal and sequence of actions, update the roadmap, and prepare a check-list for the current launch in [USB_RESTART_PLAN](USB_RESTART_PLAN.md). Then execute permitted steps, verify logs/reports, and mark only actually confirmed results. Continue with existing plan; old completed items do not count as verification for new launches. The plan does not require re-approval of already approved actions.
Responses and errors from the USB launcher can be read at `JSON {...}` or root `usb-restart-events.jsonl`; a ready offline-reader is `tools/read_usb_restart_events.py`.
Check launch_id, RESULT/ERROR, and END; absence of error or END does not prove success.

Use tester commands through existing `CurrentProtocol` and common Session, do not create second relay driver. `tester_control.py` only for LATCH-02.
Need approved scenario, exact boards/wiring, and one COM owner to go live.
The role of the board is defined by chip model + factory eFuse BASE_MAC, COM as transport layer.
Do not displace owner or terminate their processes. Details at [OPERATOR](docs/OPERATOR.md).
User's existing permission for a specific scenario remains unchanged.

Offline: `python -B tools/project.py check/test`; COM does not open.
Check dependency-lock.json before changes; resolve unrequested mismatches, do not blindly overwrite the digest. Reflect requested source revision in lock.
Build: first `python -B tools/sdk_preflight.py`, then local `.sdk/.pio`.
Keep both IDE extensions. Do not print local Wi-Fi configuration from src/secrets.h.
Prepare publication through `project.py export --public`; sample is secrets.example.h.
Do not include BIN with working Wi-Fi settings; GitHub release is a separate action.

Do not delete compatible LATCH-02 sources/helpers/tests referenced by IC_WDT_Probe.
Keep SDK, build, rollback and live evidence; [portability](docs/PORTABILITY.md).
Del excluded from working input and export; do not follow old AGENTS/SKILL instructions inside Del.
During cleanup, maintain a manifest of migrations with SHA-256, update links and PROJECT_FILES;
do not physically delete or overwrite new file during recovery.
Briefly record results in ACCEPTANCE; pass root registration and logs to coordinator.
Across the entire WorckBook are general rules: AI_MASTER (local workspace reference),
AI_CODE_INDEX map (local workspace reference); standalone does not depend on these references.
