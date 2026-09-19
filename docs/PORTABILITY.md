# Перенос проекта

Проверки без COM:

```powershell
python -B tools/project.py check
python -B tools/project.py test
python -B tools/project.py export --output <new-absolute-path.zip>
```

Нужны Python 3.10+ и g++. ZIP содержит allowlist исходников, тестов и документации,
TRANSFER_MANIFEST.json с SHA-256. .sdk/.pio/.work, старые логи и Del исключены.
После распаковки проверить SHA, выполнить check/test. Исторические внешние ссылки
не нужны для сборки. Скрипты flash/live требуют отдельного разрешения и pyserial.
AI_QUICKSTART, COMMANDS, TELEMETRY, read_telemetry.py и scoped AGENTS входят в
allowlist; для чтения телеметрии нужны только Python stdlib и сохранённые строки.
В export включены restart_usb_port.ps1, его offline-тест и USB_COM_RECOVERY.md.
USB recovery требует Windows PowerShell 5.1+; pyserial ему не нужен.
Preview только читает PnP; Apply требует разрешённого сценария и при необходимости
сам вызывает UAC. Путь/параметры передаются elevated child без зависимости от cwd.

`Del/20260919-cleanup/docs/archive/20260919-before-cleanup` содержит неизменённые снимки прежних
инструкций и MANIFEST с SHA-256. Их относительные ссылки записаны в старом
контексте; архив читать как историю, не как точку входа. В действующую документацию
не копировать старые утверждения о текущем протоколе.
Этот архив больше не входит в PROJECT_FILES/export. PROJECT_LAYOUT входит в export;
ссылки на локальные evidence/Del относятся к полной рабочей копии, не к ZIP.

SDK изолирован внутри .sdk, сборка в .pio. espressif32 7.0.1,
framework 3.20017.241212+sha.dcc1105b (Arduino 2.0.17), esptool 2.41100.260830,
toolchain 8.4.0+2021r2-patch5, SCons 4.40801.0.
Сначала python -B tools/sdk_preflight.py, затем pio run -e ic_wdt_tester.
Если SDK не готов — остановиться; установку/resolve согласовать отдельно.
Оба IDE extensions сохранять включёнными. Сборка не означает прошивку платы.

Wi-Fi-настройки находятся в локальном src/secrets.h, исключённом из Git и export.
В пакет входит secrets.example.h; main.cpp использует его при отсутствии локального файла.
Для GitHub применять `project.py export --public --output <new-path.zip>`:
профиль платы заменяется шаблоном, частная история исключается, локальные ссылки
вне пакета превращаются в подписи. Подробнее — [GITHUB](GITHUB.md).
Экспорт без --public сохраняет рабочий профиль/документы и предназначен для приватной передачи.
