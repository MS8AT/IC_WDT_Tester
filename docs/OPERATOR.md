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
