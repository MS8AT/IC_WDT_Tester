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
