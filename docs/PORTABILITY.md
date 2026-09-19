[Русский](#ru) · [中文](#zh) · [English](#en)

<a id="ru"></a>

## Русский

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

---

<a id="zh"></a>

## 中文

# 项目迁移

无COM检查:

```powershell
python -B tools/project.py check
python -B tools/project.py test
python -B tools/project.py export --output <new-absolute-path.zip>
```

需要Python 3.10+和g++. ZIP包含allowlist源代码、测试和文档，TRANSFER_MANIFEST.json带有SHA-256。.sdk/.pio/.work,旧日志和Del被排除在外。解压后验证SHA，执行check/test。历史外部链接不需要用于构建。flash/live脚本需要单独的许可和pyserial。AI_QUICKSTART、COMMANDS、TELEMETRY、read_telemetry.py和scoped AGENTS包含在allowlist中；仅需Python标准库和保存的字符串来读取遥测数据。导出包括restart_usb_port.ps1及其离线测试，以及USB_COM_RECOVERY.md。

`Del/20260919-cleanup/docs/archive/20260919-before-cleanup`包含未修改的历史指令快照和带有SHA-256的MANIFEST。它们的相对链接记录在旧上下文中；将存档视为历史记录，而不是入口点。不要复制有关当前协议的老声明到现行文档中。

此存档不再包含于PROJECT_FILES/export中。PROJECT_LAYOUT包含在导出中；指向本地evidence/Del的链接适用于完整的工作副本，而非ZIP。

USB 恢复需要 Windows PowerShell 5.1+，不需要 pyserial。Preview 只读取 PnP；Apply 需要已获授权的操作方案，并在必要时自行触发 UAC。路径和参数传给提权子进程，不依赖当前工作目录。

SDK 隔离在 .sdk 内部，构建在 .pio 中。espressif32 版本为 7.0.1，
框架版本为 3.20017.241212+sha.dcc1105b (Arduino 2.0.17)，esptool 版本为 2.41100.260830，
toolchain 版本为 8.4.0+2021r2-patch5，SCons 版本为 4.40801.0。
首先运行 python -B tools/sdk_preflight.py，然后运行 pio run -e ic_wdt_tester。如果 SDK 不准备就绪，则停止；安装/resolve 需要单独协商。
两个 IDE 扩展程序需要保持启用状态。构建并不意味着对板子进行编程。

Wi-Fi 设置位于本地 src/secrets.h 中，该文件被从 Git 和导出中排除。
包内包含 secrets.example.h 文件；main.cpp 在没有本地文件的情况下使用它。
对于 GitHub，请应用 `project.py export --public --output <new-path.zip>`：
板卡配置文件将替换为模板，私人历史记录将被排除，外部于包的本地链接
将转换为普通文字标签。更多详情请参阅 [GITHUB](GITHUB.md)。
导出时不使用 --public 可以保留工作配置/文档，并且适合私密传输。

---

<a id="en"></a>

## English

# Project Transfer

No COM checks:

```powershell
python -B tools/project.py check
python -B tools/project.py test
python -B tools/project.py export --output <new-absolute-path.zip>
```

Requires Python 3.10+ and g++. ZIP contains allowlist source code, tests, and documentation, TRANSFER_MANIFEST.json with SHA-256. .sdk/.pio/.work, old logs, and Del are excluded. After unpacking, verify the SHA, run check/test. Historical external links are not needed for building. Flash/live scripts require separate permission and pyserial. AI_QUICKSTART, COMMANDS, TELEMETRY, read_telemetry.py, and scoped AGENTS are included in allowlist; only Python standard library and saved strings are required to read telemetry data. Export includes restart_usb_port.ps1 along with its offline test and USB_COM_RECOVERY.md.

`Del/20260919-cleanup/docs/archive/20260919-before-cleanup` contains unmodified snapshots of previous instructions and a MANIFEST with SHA-256. Their relative links are recorded in the old context; treat the archive as history, not an entry point. Do not copy old claims about current protocol into active documentation.

This archive is no longer included in PROJECT_FILES/export. PROJECT_LAYOUT is included in export; links to local evidence/Del refer to a full working copy, not ZIP.

USB recovery requires Windows PowerShell 5.1+ and does not need pyserial. Preview only reads PnP; Apply requires an authorized scenario and invokes UAC itself if needed. Paths and parameters are passed to the elevated child independently of the working directory.

The SDK is isolated inside .sdk, built in .pio. espressif32 version 7.0.1,
framework version 3.20017.241212+sha.dcc1105b (Arduino 2.0.17), esptool version 2.41100.260830,
toolchain version 8.4.0+2021r2-patch5, SCons version 4.40801.0.
First run python -B tools/sdk_preflight.py, then pio run -e ic_wdt_tester. If the SDK is not ready — stop; installation/resolve needs to be negotiated separately.
Both IDE extensions need to remain enabled. Building does not imply programming the board.

Wi-Fi settings are located in local src/secrets.h, excluded from Git and export.
The package includes secrets.example.h; main.cpp uses it if there is no local file.
For GitHub, apply `project.py export --public --output <new-path.zip>`:
the board configuration profile will be replaced by a template, private history will be excluded, external links outside the package
will become plain text labels. More details can be found at [GITHUB](GITHUB.md).
Export without --public retains working configurations/documents and is intended for private transmission.
