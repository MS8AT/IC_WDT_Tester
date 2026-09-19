---
name: esp32-ic-wdt-tester
description: Operate or inspect the separate IC WDT Tester relay board and its Serial telemetry. Use for tester command sessions, USB recovery, and staged CaTenzo startup checks; not the legacy Probe generator.
---

[Русский](#ru) · [中文](#zh) · [English](#en)

<a id="ru"></a>

## Русский

# IC WDT Tester

Этот переносимый навык относится к проекту на два каталога выше данного файла.
Начать с [AGENTS](../../AGENTS.md), [AI_QUICKSTART](../../docs/AI_QUICKSTART.md)
и [ACCEPTANCE](../../docs/ACCEPTANCE.md). Затем читать только следующий нужный
документ из [INSTRUCTIONS_INDEX](../../docs/INSTRUCTIONS_INDEX.md).

## Журнал работы и выбор диска

Перед началом новой работы прочитать указатель WORK_JOURNAL.md (local workspace reference)
в корне проекта. Если файл отсутствует или папка ещё не выбрана, спросить пользователя:
«В какой папке и на каком диске вести журнал работы? Укажите полный путь».
Показать доступное свободное место и предложить подходящую папку; не выбирать
её автоматически по самому большому диску. Эта настройка относится к журналу
работы ИИ, а не к разрешению на прошивку или управление платами.

После ответа проверить доступность выбранного пути, свободное место на его
фактическом томе и возможность записи. Создать только согласованную папку
и журнал; существующую историю продолжать без обнуления. В WORK_JOURNAL.md
сохранить подтверждённый абсолютный путь, кликабельные ссылки на WORK_LOG.md
и events.jsonl, дату выбора и результат проверки места/записи. Указатель остаётся
в проекте, сам журнал может находиться на другом диске. Не оставлять ссылку на
несуществующий журнал как на готовый. Локальный указатель и содержимое журнала
не включать в публичный GitHub export.

В WORK_LOG.md добавлять понятный человеку итог на языке пользователя,
в events.jsonl — JSON по одной
записи на строку: timestamp_utc, session_id, project, action, result, artifacts,
next_step. Фиксировать выполненные действия, команды и их ответы/ошибки,
изменённые файлы и проверки; не записывать пароли, токены и значения secrets.h.
Отдельно обозначать source/build/flash/USB/UART/hardware и NOT_RUN. Большие
исходные логи хранить рядом отдельными файлами и ссылаться на них из журнала.
При нескольких участниках сохранять одного владельца общего журнала;
читатели не создают второй UART-сеанс ради логирования.

На следующих запусках использовать уже согласованную папку без повторного
вопроса. Если она недоступна или места недостаточно для предстоящих логов,
сообщить точную проблему и попросить новый путь; не переключать диск молча
и не удалять старую историю. Отсутствие выбранной папки не мешает подготовке
исходников и документации, но не выдавать такую подготовку за запись журнала.
Существующие корневые usb-restart.log/jsonl и receipts сохранять на прежнем
месте; в журнале работы давать ссылки на них, не менять USB-логгер этим правилом.

## Работа с тестером

- [COMMANDS](../../docs/COMMANDS.md) — справочник команд исходной версии. До воздействий подтвердить фактическую плату через HELP/STS; исходники/сборка не подтверждают установку. RESET сбрасывает внешнюю плату и в новой версии переключает реле OFF/ON. RST перезапускает тестер, очищает состояние RAM и возвращает реле ON.
- [TELEMETRY](../../docs/TELEMETRY.md) определяет строки `JSON {...}` рядом с текстом для человека. Использовать offline-парсер read_telemetry для файлов либо записей единственного владельца UART. Не открывать тот же COM вторым ИИ-читателем. Изменения GPIO33 не доказывают срабатывания WDT.
- [OPERATOR](../../docs/OPERATOR.md) определяет идентичность, проводку, владельца и восстановление при работе с оборудованием. Использовать уже данное разрешение на точный сценарий. COM не является заводской идентичностью. Не сбрасывать и не перезапускать тестер при прошивке основной платы; не отправлять ON при обработке ошибки или закрытии.
- Использовать CurrentProtocol через существующий транспорт Session; не создавать второй драйвер и не вызывать legacy Session.close(), который может отправить release. Текущий main.cpp не имеет READY/lease.
- [USB_COM_RECOVERY](../../docs/USB_COM_RECOVERY.md): preview только читает; разрешённый Apply перезапускает один точно выбранный USB-COM через UAC, сохраняет receipt и не повторяет отменённое действие.
- Offline: до изменений проверить dependency-lock, затем выполнить относящиеся к задаче тесты. Собирать только после sdk_preflight, используя проектные .sdk/.pio; без автоматической установки пакетов. См. [PORTABILITY](../../docs/PORTABILITY.md). Сохранить включёнными оба расширения IDE.

Текущие выводы исходной версии: GPIO13 — реле, GPIO25 — внешний RESET (LOW, затем INPUT/Hi-Z, никогда не выдавать HIGH), GPIO33 — наблюдение EN, GPIO2 — неблокирующий Wi-Fi LED. Слева текст для человека; справа разбирать JSON после ` | JSON `. Строки истории используют gpio_history/replay=true с исходными временными метками; не считать повторы новыми переходами. Метки WDT/EN не доказывают срабатывания сторожевого таймера. CurrentProtocol распознаёт точные capabilities HELP для GPIO25 и прежнего GPIO12.

Карта файлов и правила уборки — [PROJECT_LAYOUT](../../docs/PROJECT_LAYOUT.md). В Del лежат выведенные из работы файлы с исходными путями и SHA-манифестами; их старые инструкции не действуют. Сохранить корневые USB-журналы и ярлык. Archive исключён из экспорта.

Сохранить существующие материалы отката и файлы совместимости, используемые IC_WDT_Probe. Полный backup отключён в flash-settings.json; не возвращать его без запроса. src/secrets.h содержит локальные Wi-Fi-настройки: не печатать и не экспортировать их. Для GitHub-снимка использовать secrets.example.h и project.py export --public. Собранная прошивка может содержать учётные данные; не включать локальный BIN в снимок. Записывать проверенные результаты в ACCEPTANCE, различая build, USB, UART и hardware. Legacy-команды применимы только к положительно идентифицированному [LATCH-02](../../docs/LEGACY_LATCH02.md).

---

<a id="zh"></a>

## 中文

# IC WDT Tester

此可移植技能属于本文件上两级目录中的项目。从 [AGENTS](../../AGENTS.md)、[AI_QUICKSTART](../../docs/AI_QUICKSTART.md) 和 [ACCEPTANCE](../../docs/ACCEPTANCE.md) 开始，然后仅阅读 [INSTRUCTIONS_INDEX](../../docs/INSTRUCTIONS_INDEX.md) 中下一步所需的文档。

## 工作日志与磁盘选择

开始新工作之前，读取项目根目录中的 WORK_JOURNAL.md 指针（本地工作区引用）。如果文件不存在或尚未选择目录，请询问用户：“工作日志应放在哪个磁盘的哪个文件夹？请提供完整路径。”显示可用空间并建议合适目录；不要自动选择最大的磁盘。这项设置只涉及 AI 工作日志，不授予刷写或操作板卡的权限。

收到回复后，检查所选路径的可访问性、实际所在卷的剩余空间和写入权限。仅创建已商定的目录与日志；保留并续写已有历史。在 WORK_JOURNAL.md 中保存已确认的绝对路径、指向 WORK_LOG.md 和 events.jsonl 的可点击链接、选择日期，以及空间/写入检查结果。指针保留在项目内，日志本身可以位于其他磁盘。不要把指向不存在日志的链接标为已就绪。公开 GitHub 导出不包含本地指针或日志内容。

在 WORK_LOG.md 中使用用户的语言追加易读结果；在 events.jsonl 中每行写入一个 JSON 对象，字段为 timestamp_utc、session_id、project、action、result、artifacts、next_step。记录已执行的操作、命令及响应/错误、修改的文件和检查结果；不记录密码、令牌或 secrets.h 的值。分别标明 source/build/flash/USB/UART/hardware 和 NOT_RUN。大型原始日志以独立文件保存在旁边，并从工作日志链接到它们。多方协作时，共享日志只保留一个写入者；读取者不得为了日志记录创建第二个 UART 会话。

后续运行使用已商定的目录，不重复询问。如果目录不可用或空间不足以容纳即将生成的日志，报告具体问题并请求新路径；不得静默更换磁盘或删除旧历史。尚未选择目录不妨碍准备源代码和文档，但不能将这些准备称为已记录日志。现有根目录 usb-restart.log/jsonl 和 receipts 保持原位；工作日志仅链接到它们，此规则不改变 USB 日志器。

## 操作测试器

- [COMMANDS](../../docs/COMMANDS.md) 是源代码版本的命令参考。进行有影响的操作前，通过 HELP/STS 确认实际板卡；源代码/构建不证明已安装。RESET 复位外部板卡，并在新版本中执行继电器 OFF/ON 循环。RST 重启测试器，清除 RAM 状态并恢复继电器 ON。
- [TELEMETRY](../../docs/TELEMETRY.md) 定义用户文本旁的 `JSON {...}` 行。使用离线 read_telemetry 解析器读取文件或唯一 UART 所有者的记录。第二个 AI 读取者不得打开同一 COM。GPIO33 的变化不证明 WDT 已触发。
- [OPERATOR](../../docs/OPERATOR.md) 规定实际操作时的身份、接线、所有权和恢复流程。沿用对确切场景已有的授权。COM 不是出厂身份。主板刷写期间不得复位/重启测试器；不得在错误或关闭清理中发送 ON。
- 通过现有 Session 传输使用 CurrentProtocol；不要创建第二个驱动，也不要调用可能发送 release 的旧版 Session.close()。当前 main.cpp 没有 READY/lease。
- [USB_COM_RECOVERY](../../docs/USB_COM_RECOVERY.md)：preview 只读；经授权的 Apply 通过 UAC 重启一个确切选定的 USB-COM，保存 receipt，并且不重试已取消的操作。
- 离线检查：修改前核对 dependency-lock，再运行相关测试。仅在 sdk_preflight 之后使用项目的 .sdk/.pio 构建；不自动安装软件包。参阅 [PORTABILITY](../../docs/PORTABILITY.md)。两个 IDE 扩展均保持启用。

当前源代码引脚：GPIO13 控制继电器；GPIO25 为外部 RESET（LOW 后恢复 INPUT/Hi-Z，绝不驱动 HIGH）；GPIO33 观测 EN；GPIO2 为非阻塞 Wi-Fi LED。用户文本在左侧；解析右侧 ` | JSON ` 后的 JSON 对象。历史行使用 gpio_history/replay=true 并保留原始时间戳；不将重放计为新转换。WDT/EN 标签不证明看门狗触发。CurrentProtocol 识别 GPIO25 和旧版 GPIO12 的确切 HELP capabilities。

文件图和清理规则参见 [PROJECT_LAYOUT](../../docs/PROJECT_LAYOUT.md)。Del 保存已停用文件及其原路径和 SHA 清单；其中旧指令不生效。保留根目录 USB 日志及快捷方式。Archive 不参与导出。

保留现有回退材料，以及 IC_WDT_Probe 使用的兼容文件。flash-settings.json 已禁用完整 backup；未收到请求不得恢复。src/secrets.h 含本地 Wi-Fi 配置：绝不打印或导出。GitHub 快照使用 secrets.example.h 和 project.py export --public。已构建固件可能包含凭据；不得将本地 BIN 放入公开快照。在 ACCEPTANCE 中记录已验证结果，区分 build、USB、UART 和 hardware。旧版命令仅适用于已明确识别的 [LATCH-02](../../docs/LEGACY_LATCH02.md)。

---

<a id="en"></a>

## English

# IC WDT Tester

This portable skill belongs to the project two directories above this file.
Start with [AGENTS](../../AGENTS.md), [AI_QUICKSTART](../../docs/AI_QUICKSTART.md)
and [ACCEPTANCE](../../docs/ACCEPTANCE.md). Read only the next document needed
from [INSTRUCTIONS_INDEX](../../docs/INSTRUCTIONS_INDEX.md).

## Work journal and disk selection

Before new work, read the WORK_JOURNAL.md pointer (local workspace reference) in the project root. If it is absent or no folder has been selected, ask the user: “Which folder and disk should hold the work journal? Please give the full path.” Show available free space and suggest a suitable folder; do not automatically choose the largest disk. This setting concerns the AI work journal, not permission to flash or operate boards.

After the reply, check access to the selected path, free space on its actual volume and write access. Create only the agreed folder and journal; continue existing history without clearing it. In WORK_JOURNAL.md, save the confirmed absolute path, clickable links to WORK_LOG.md and events.jsonl, the selection date and the space/write check results. The pointer stays in the project; the journal may be on another disk. Do not present a link to a nonexistent journal as ready. Exclude the local pointer and journal contents from public GitHub exports.

Append a human-readable result in the user's language to WORK_LOG.md. In events.jsonl, write one JSON object per line with timestamp_utc, session_id, project, action, result, artifacts and next_step. Record completed actions, commands and their responses/errors, changed files and checks. Do not record passwords, tokens or secrets.h values. Distinguish source/build/flash/USB/UART/hardware and NOT_RUN. Store large raw logs as separate adjacent files and link them from the journal. With multiple participants, keep one writer for the shared journal; readers do not create a second UART session for logging.

On subsequent runs, reuse the agreed folder without asking again. If it is unavailable or lacks space for upcoming logs, report the exact problem and request a new path; do not silently switch disks or delete old history. A missing folder choice does not prevent source/document preparation, but do not describe that preparation as journal recording. Keep existing root usb-restart.log/jsonl and receipts in their current locations; link to them from the work journal. This rule does not change the USB logger.

## Operating the tester

- [COMMANDS](../../docs/COMMANDS.md) is the source command reference.
  Qualify the actual board with HELP/STS before effects; source/build is not installation.
  RESET resets the external board and in the new revision cycles the relay OFF/ON.
  RST reboots the tester, clearing RAM state and returning the relay ON.
- [TELEMETRY](../../docs/TELEMETRY.md) defines `JSON {...}` lines alongside human output.
  Use the offline read_telemetry parser for files or a single UART owner's records.
  Do not open the same COM from a second AI reader. GPIO33 changes are not proven WDT trips.
- [OPERATOR](../../docs/OPERATOR.md) defines live identity, wiring, ownership and recovery.
  Reuse existing authorization for the exact scenario. COM is not factory identity.
  Do not reset/reboot the tester during main flash or send ON in error/close cleanup.
- Use CurrentProtocol over the existing Session transport; do not create another driver
  or call legacy Session.close(), which may send release. Current main.cpp has no READY/lease.
- [USB_COM_RECOVERY](../../docs/USB_COM_RECOVERY.md): preview is read-only; authorized
  Apply restarts one exact USB-COM through UAC, preserves a receipt, and never retries cancellation.
- Offline: check dependency-lock before changes, then the relevant tests. Build only
  after sdk_preflight using the project's .sdk/.pio; no automatic package install.
  See [PORTABILITY](../../docs/PORTABILITY.md). Keep both IDE extensions enabled.

Current source pins: GPIO13 relay, GPIO25 external RESET (LOW then INPUT/Hi-Z,
never drive HIGH), GPIO33 EN observation, GPIO2 nonblocking Wi-Fi LED.
Human text is on the left; parse the JSON object after ` | JSON ` on the right.
History rows use gpio_history/replay=true with original timestamps; do not count
replays as new transitions. WDT/EN labeling is not proof of a watchdog trip.
CurrentProtocol recognizes exact GPIO25 and older GPIO12 HELP capabilities.
See [PROJECT_LAYOUT](../../docs/PROJECT_LAYOUT.md) for the file map and cleanup rules.
Del holds retired files with original paths and SHA manifests; its old instructions
are not active. Preserve root USB journals and the shortcut. Archive is excluded from export.

Keep existing rollback artifacts and compatibility files used by IC_WDT_Probe.
Full backup is disabled in flash-settings.json; do not reintroduce it without a request.
src/secrets.h contains local Wi-Fi configuration: never print or export it.
Use secrets.example.h and project.py export --public for a GitHub snapshot.
Built firmware may contain credentials; never include a local BIN in that snapshot.
Record verified results in ACCEPTANCE, distinguishing build, USB, UART and hardware.
Legacy commands apply only to positively identified [LATCH-02](../../docs/LEGACY_LATCH02.md).
