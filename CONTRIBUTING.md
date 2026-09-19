# Изменения проекта

Начните с [AGENTS](AGENTS.md), [карты инструкций](docs/INSTRUCTIONS_INDEX.md)
и [описания работы](docs/HOW_IT_WORKS.md). Для настройки — [GETTING_STARTED](docs/GETTING_STARTED.md).

1. Перед правкой выполните `python -B tools/project.py check`.
2. Сохраняйте совместимость CurrentProtocol и отдельного LATCH-02.
3. GPIO25: только LOW → INPUT без pull-up; GPIO12 не использовать как RESET.
4. Не добавляйте delay в рабочий цикл. Новые JSON-поля отражайте в контракте и parser.
5. Обновляйте dependency-lock только для намеренно изменённых зависимостей.
6. Выполните `python -B tools/project.py test`; для прошивки также SDK preflight и build.
7. В описании изменения разделяйте source/test/build/flash/UART/hardware.

Исходники Wi-Fi-настроек не коммитить: локальный secrets.h игнорируется.
Для примеров используйте secrets.example.h. Публичный пакет создавайте через
`project.py export --public`; полную рабочую папку в Git не добавляйте.

Не удаляйте legacy-файлы только из-за отсутствия в активном build filter:
на них может ссылаться IC_WDT_Probe. Перемещение старых материалов выполняйте
по манифесту с SHA, сохраняя rollback и результаты аппаратных проверок.

Прошивка и команды RESET/RST/ON/OFF требуют понятного сценария, точной платы,
проводки и одного владельца COM. Тесты этого проекта COM не открывают.
