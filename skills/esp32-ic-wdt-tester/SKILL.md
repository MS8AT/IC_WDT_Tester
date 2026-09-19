---
name: esp32-ic-wdt-tester
description: Operate or inspect the separate IC WDT Tester relay board and its Serial telemetry. Use for tester command sessions, USB recovery, and staged CaTenzo startup checks; not the legacy Probe generator.
---

# IC WDT Tester

This portable skill belongs to the project two directories above this file.
Start with [AGENTS](../../AGENTS.md), [AI_QUICKSTART](../../docs/AI_QUICKSTART.md)
and [ACCEPTANCE](../../docs/ACCEPTANCE.md). Read only the next document needed
from [INSTRUCTIONS_INDEX](../../docs/INSTRUCTIONS_INDEX.md).

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
