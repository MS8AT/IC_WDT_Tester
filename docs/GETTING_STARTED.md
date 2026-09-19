# Первый запуск

Рабочий маршрут проекта проверяется на Windows с PowerShell, Python 3.10+,
PlatformIO Core и g++ в PATH. USB-инструменты требуют Windows PowerShell 5.1+.
Python с PlatformIO должен иметь pyserial; offline-reader JSON использует только stdlib.
Установка программ и прошивка не выполняются при чтении документации или запуске check.

## 1. Настройки Wi-Fi

Из корня проекта создайте локальный файл, если его ещё нет:

```powershell
if (Test-Path src/secrets.h) { throw 'secrets.h already exists' }
Copy-Item src/secrets.example.h src/secrets.h -ErrorAction Stop
```

Не выполняйте копирование поверх уже заполненного secrets.h. Впишите SSID и пароль
в secrets.h; он исключён из Git и allowlist экспорта. main.cpp подключает его,
а при отсутствии использует пример с YOUR_WIFI_SSID/YOUR_WIFI_PASSWORD.
С примером сборка работает, но подключение к вашей сети не настроено.
Реле и UART могут работать без Wi-Fi; время до NTP будет null.
Часовой пояс локального отображения задаётся TZ_INFO в main.cpp; Unix-время — UTC.

## 2. Проверки без платы

```powershell
python -B tools/project.py check
python -B tools/project.py test
```

check сверяет SHA зависимостей. test запускает Python-тесты и C++ harnesses без COM.
Не исправляйте несовпадение lock вслепую: сначала выясните, какой исходник изменился.

Если при наличии локального SDK test сообщает `No module named 'serial'`, проверьте
выбранный Python: системный интерпретатор может отличаться от окружения PlatformIO.
На Windows с обычной установкой PlatformIO можно использовать уже готовое окружение:

```powershell
$pioPython = Join-Path $env:USERPROFILE '.platformio\penv\Scripts\python.exe'
& $pioPython -X utf8 -B tools/project.py test
```

Сначала убедитесь, что этот файл существует. Это выбор установленного интерпретатора,
а не команда установки пакетов. JSON offline-reader не требует pyserial.

## 3. Подготовка SDK

SDK не входит в GitHub snapshot. Текущий закреплённый набор:

| Компонент | Версия |
| --- | --- |
| PlatformIO Core, рабочее окружение | 6.1.19 |
| espressif32 | 7.0.1 |
| framework-arduinoespressif32 | 3.20017.241212+sha.dcc1105b, Arduino 2.0.17 |
| tool-esptoolpy | 2.41100.260830, esptool 4.11.0 |
| toolchain-xtensa-esp32 | 8.4.0+2021r2-patch5 |
| tool-scons | 4.40801.0 |

В исходном рабочем окружении tool-esptoolpy установлен из локального
`.sdk/esptool.tar.gz`. Наличие этого номера в публичном Registry не подтверждено.
Поэтому команда установки из Registry сама по себе не обеспечивает воспроизведение.

Для точного повторения получите проверенный каталог `.sdk` у сопровождающего
проекта и разместите его в корне новой копии. Внутри должны быть `platforms`,
`packages`, `core` и штатные metadata пакетов. Архив SDK не является частью
публичного ZIP. При подготовке пакетов из других источников сначала согласуйте
их версии и обновление preflight; не подменяйте локальный пакет молча.
PlatformIO поддерживает установку из локальных папок и TAR/ZIP:
[официальный pio pkg install](https://docs.platformio.org/en/latest/core/userguide/pkg/cmd_install.html).

```powershell
python -B tools/sdk_preflight.py
pio run -e ic_wdt_tester
```

После PASS образ находится в `.pio/build/ic_wdt_tester/firmware.bin`.
Окружение собирает только src/main.cpp. Публичный snapshot проверяется host-тестами;
сборка на совершенно новом компьютере без подготовленного SDK не заявляется.

## 4. Идентификация и прошивка

Сначала проверьте [проводку](WIRING.md). Определите ROM chip model, revision
и factory eFuse BASE_MAC конкретного тестера, затем заполните device-profile.json
по образцу device-profile.example.json. COM — транспорт, его номер может меняться.
Публичный профиль содержит SET_FACTORY_BASE_MAC: с ним guarded flash откажет в записи.
ROM-идентификация сама может перезапустить плату; не выполнять во время main flash.

Guarded uploader рассчитан на **обновление приложения при совпадающих bootloader
и partitions**. Он не является установщиком чистой/неизвестной flash:
несовпадение layout останавливает запись. Первичная установка требует отдельного
плана с проверенными диапазонами/образами; не стирайте NVS или всю flash автоматически.

Закройте Serial Monitor и проверьте отсутствие другой загрузки. Сначала preview:

```powershell
python -B tools/flash_tester.py --port COM3 --output .work/flash-new-run
```

Здесь COM3 — пример; подставьте проверенный порт. Preview не открывает COM.
В разрешённой сессии добавление `--execute` выполняет ROM identity, проверку
выбора 3,3 В, чтение boot/table, одну запись app и отдельный verify. Каталог output
должен быть новым. При ошибке не повторяйте команду до выяснения результата.
Полный backup по умолчанию отключён; `--backup` запрашивается явно.

## 5. Проверка UART

Откройте один Serial Monitor: 115200, 8N1, UTF-8, LF/CRLF. Введите HELP, затем STS.
Для новой версии HELP должен описывать GPIO25 INPUT (Hi-Z), JSON справа и GPIO2 LED.
RESETDIAG в покое должен показывать отключённый выход GPIO25 (OE=0);
уровень PAD зависит от внешней схемы. Не выполняйте RESET ради проверки текста HELP.

Сохраните журнал, SHA образа и проверенные факты. Успешный verify доказывает
содержимое flash, а не контакты реле или прохождение сброса до целевой платы.
[Дальнейшая работа](OPERATOR.md), [команды](COMMANDS.md).
