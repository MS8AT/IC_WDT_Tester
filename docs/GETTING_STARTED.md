[Русский](#ru) · [中文](#zh) · [English](#en)

<a id="ru"></a>

## Русский

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

---

<a id="zh"></a>

## 中文

# 第一次启动

项目的工作路径在 Windows 上使用 PowerShell、Python 3.10+、PlatformIO 核心和 g++ 进行检查，这些工具都必须位于 PATH 中。USB 工具需要 Windows PowerShell 5.1+。带有 PlatformIO 的 Python 应该安装 pyserial；离线阅读器 JSON 只使用标准库。在阅读文档或运行 check 时不会执行程序的安装和固件更新。

## 1. Wi-Fi 设置

从项目根目录创建一个本地文件，如果它还没有的话：

```powershell
if (Test-Path src/secrets.h) { throw 'secrets.h already exists' }
Copy-Item src/secrets.example.h src/secrets.h -ErrorAction Stop
```

不要覆盖已经填写好的 secrets.h 文件。将 SSID 和密码写入 secrets.h；这个文件被 Git 排除，并且不在 allowlist 导出中。main.cpp 会加载它，在没有找到的情况下使用 YOUR_WIFI_SSID/YOUR_WIFI_PASSWORD 的示例。即使构建可以工作，但你的网络连接未配置。

继电器和 UART 可以在没有 Wi-Fi 的情况下运行；NTP 同步前时间为 null。本地显示的时区由 main.cpp 中的 TZ_INFO 设置；Unix 时间是 UTC。

## 2. 不带板卡的检查

```powershell
python -B tools/project.py check
python -B tools/project.py test
```

check 检查依赖项的 SHA 哈希值。test 运行 Python 测试和 C++ harnesses，但不使用 COM 端口。不要盲目地修复 lock 的不匹配：首先确定哪个源代码发生了变化。

如果在存在本地 SDK 的情况下 test 报告 `No module named 'serial'`，请检查所选的 Python：系统解释器可能与 PlatformIO 环境不同。在 Windows 上，使用普通安装的 PlatformIO 可以使用已有的环境：

```powershell
$pioPython = Join-Path $env:USERPROFILE '.platformio\penv\Scripts\python.exe'
& $pioPython -X utf8 -B tools/project.py test
```

首先确保这个文件存在。这是已经安装的解释器的选择，而不是包管理命令。JSON 离线阅读器不需要 pyserial。

## 3. SDK 准备

SDK 不包含在 GitHub 快照中。当前固定集：

| 组件 | 版本 |
| --- | --- |
| PlatformIO 核心，工作环境 | 6.1.19 |
| espressif32 | 7.0.1 |
| framework-arduinoespressif32 | 3.20017.241212+sha.dcc1105b, Arduino 2.0.17 |
| tool-esptoolpy | 2.41100.260830, esptool 4.11.0 |
| toolchain-xtensa-esp32 | 8.4.0+2021r2-patch5 |
| tool-scons | 4.40801.0 |

在原始工作环境中，tool-esptoolpy 是从本地 `.sdk/esptool.tar.gz` 安装的。此编号是否存在于公共注册表中尚未得到证实。因此，仅通过注册表安装命令本身并不能保证可重复性。

为了实现精确复现，请获取项目支持人员提供的验证目录 `.sdk`，并将其放置在新副本的根目录下。内部应包含`platforms`、`packages` 和 `core` 以及标准包元数据。公开 ZIP 不包含 SDK 存档。
当从其他来源准备软件包时，首先协商其版本和preflight 检查的更新；不要默默地替换本地包。
PlatformIO 支持从本地文件夹和 TAR/ZIP 安装：[官方 pio pkg install](https://docs.platformio.org/en/latest/core/userguide/pkg/cmd_install.html)。

```powershell
python -B tools/sdk_preflight.py
pio run -e ic_wdt_tester
```

在 PASS 后，固件映像位于 `.pio/build/ic_wdt_tester/firmware.bin` 中。环境仅编译 src/main.cpp。公共快照通过主机测试进行验证；完全新的计算机上没有预先准备的 SDK 的构建不被声明。

## 4. 身份识别与刷写

首先检查[布线](WIRING.md)。确定测试器的具体ROM芯片型号、修订版本和工厂eFuse BASE_MAC，然后根据device-profile.example.json的示例填写device-profile.json文件。COM是传输介质，其编号可能会变化。公共配置包含SET_FACTORY_BASE_MAC：使用它会导致guarded flash拒绝写入。

ROM 识别本身可能导致板卡重启；不要在主板刷写期间执行此操作。

Guarded上传程序旨在用于**当引导加载程序和分区匹配时更新应用程序**。它不是空白或状态未知的闪存的安装程序：布局不匹配会阻止写入。初次安装需要单独计划，包括经过验证的范围/映像；不要自动擦除NVS或整个闪存。

关闭串行监视器并检查是否有其他加载过程。首先预览：
```powershell
python -B tools/flash_tester.py --port COM3 --output .work/flash-new-run
```
这里COM3是一个示例，请使用已验证的端口替换它。预览不会打开COM。在许可会话中添加`--execute`执行ROM身份识别、选择3.3V检查、读取引导/表，写入一个应用程序并单独验证。输出目录必须是新的。如果出现错误，请不要重复命令直到确定结果为止。默认情况下禁用完整备份；需要明确请求`--backup`。

## 5. UART检查

打开一个串行监视器：115200，8N1，UTF-8，LF/CRLF。输入HELP，然后输入STS。对于新版本的HELP应描述GPIO25 INPUT（Hi-Z），右侧JSON和GPIO2 LED。在RESETDIAG静止状态下，应该显示GPIO25输出禁用（OE=0）；PAD电平取决于外部电路设计。不要为了检查文本HELP而执行RESET。

保存日志，固件映像的 SHA和验证的事实。成功的 verify 证明了
闪存的内容而不是继电器触点或重置到目标板的路径。
[进一步工作](OPERATOR.md)，[命令](COMMANDS.md).

---

<a id="en"></a>

## English

# First Launch

The project's working path is verified on Windows using PowerShell, Python 3.10+, PlatformIO Core and g++ in PATH. USB tools require Windows PowerShell 5.1+. Python with PlatformIO should have pyserial; the offline-reader JSON uses only stdlib. No program installation or firmware update takes place when reading documentation or running check.

## 1. Wi-Fi Settings

Create a local file from the project root if it does not exist yet:

```powershell
if (Test-Path src/secrets.h) { throw 'secrets.h already exists' }
Copy-Item src/secrets.example.h src/secrets.h -ErrorAction Stop
```

Do not overwrite an already filled secrets.h file. Write SSID and password into secrets.h; this file is excluded by Git and not in allowlist export. main.cpp loads it, using YOUR_WIFI_SSID/YOUR_WIFI_PASSWORD example when missing. The build can work even if your network connection is unconfigured.

Relays and UART can run without Wi-Fi; time is null before NTP synchronization. Local display timezone set by TZ_INFO in main.cpp; Unix time is UTC.

## 2. Checks Without Board

```powershell
python -B tools/project.py check
python -B tools/project.py test
```

check verifies SHA of dependencies. test runs Python tests and C++ harnesses but not using COM port. Do not blindly fix lock mismatch: first determine which source code has changed.

If in the presence of a local SDK, test reports `No module named 'serial'`, check selected Python: system interpreter may differ from PlatformIO environment. On Windows with regular installation of PlatformIO, you can use existing environment:

```powershell
$pioPython = Join-Path $env:USERPROFILE '.platformio\penv\Scripts\python.exe'
& $pioPython -X utf8 -B tools/project.py test
```

First ensure this file exists. This is the choice of installed interpreter, not a package management command. JSON offline-reader does not require pyserial.

## 3. SDK Preparation

SDK is not included in the GitHub snapshot. The current pinned set:

| Component | Version |
| --- | --- |
| PlatformIO Core, working environment | 6.1.19 |
| espressif32 | 7.0.1 |
| framework-arduinoespressif32 | 3.20017.241212+sha.dcc1105b, Arduino 2.0.17 |
| tool-esptoolpy | 2.41100.260830, esptool 4.11.0 |
| toolchain-xtensa-esp32 | 8.4.0+2021r2-patch5 |
| tool-scons | 4.40801.0 |

In the original working environment, tool-esptoolpy is installed from a local `.sdk/esptool.tar.gz`. The presence of this number in the public registry has not been confirmed. Therefore, installing via the registry alone does not ensure reproducibility.

To achieve precise reproducibility, obtain the verified directory `.sdk` provided by the project support team and place it at the root of a new copy. Inside should be `platforms`, `packages`, and `core` along with standard package metadata. The SDK archive is not part of the public ZIP.
When preparing packages from other sources, first negotiate their versions and preflight updates; do not silently replace a local package.
PlatformIO supports installation from local folders and TAR/ZIP: [official pio pkg install](https://docs.platformio.org/en/latest/core/userguide/pkg/cmd_install.html).

```powershell
python -B tools/sdk_preflight.py
pio run -e ic_wdt_tester
```

After PASS, the image is located in `.pio/build/ic_wdt_tester/firmware.bin`. The environment compiles only src/main.cpp. Public snapshots are verified by host tests; building on a completely new computer without pre-prepared SDK is not claimed.

## 4. Identification and flashing

First, check the [wiring](WIRING.md). Determine the specific ROM chip model, revision and factory eFuse BASE_MAC of the tester, then fill in device-profile.json according to the example device-profile.example.json. COM is the transport medium; its number may change. The public profile contains SET_FACTORY_BASE_MAC: using it will cause guarded flash to refuse writing.

ROM identification itself may restart the board; do not perform this during main flash.

The guarded uploader is designed for **updating applications when the bootloader and partitions match**. It is not an installer for clean/unknown flash: layout mismatch stops writing. Initial installation requires a separate plan with verified ranges/images; do not automatically erase NVS or the entire flash.

Close the Serial Monitor and ensure no other upload is running. First preview:
```powershell
python -B tools/flash_tester.py --port COM3 --output .work/flash-new-run
```
Here COM3 is an example, replace it with a validated port. Preview does not open COM. In an authorized session adding `--execute` performs ROM identity, 3.3V selection verification, reading boot/table, writing one application and separate verify. The output directory must be new. If there's an error, do not repeat the command until the result is determined. Full backup is disabled by default; explicit request for `--backup` is required.

## 5. UART Check

Open a serial monitor: 115200, 8N1, UTF-8, LF/CRLF. Enter HELP, then enter STS. For the new version of HELP should describe GPIO25 INPUT (Hi-Z), JSON on right and GPIO2 LED. In the static state of RESETDIAG, it should show GPIO25 output disabled (OE=0); PAD level depends on external circuit design. Do not perform a RESET to check text HELP.

Save the log, image SHA and verified facts. A successful verify proves
the content of the flash, not relay contacts or reset paths to the target board.
[Further work](OPERATOR.md), [commands](COMMANDS.md).
