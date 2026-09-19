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
