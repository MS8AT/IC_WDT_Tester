[Русский](#ru) · [中文](#zh) · [English](#en)

<a id="ru"></a>

## Русский

# Подготовка и публикация на GitHub

Публиковать следует чистый snapshot исходников и документации, а не всю рабочую папку.
Создание архива ниже не создаёт GitHub-репозиторий и ничего не отправляет в интернет.

## Состав

Входят README, инструкции, схемы Mermaid, активные и совместимые исходники,
тесты, инструменты, platformio.ini, dependency-lock, примеры Wi-Fi/identity.
Описание проекта и микросхем — русский → китайский → английский, построчно.
Включены [схема IN1232N/DS1232LP](IC_WDT_HARDWARE.md) и оригинальные PDF
с [источниками, редакциями и SHA-256](datasheets/README.md). Права на PDF остаются
у их правообладателей; лицензия собственного кода не переопределяет эти права.
Публичный device-profile.json заменяется безопасным шаблоном, который не разрешает
запись на конкретную плату. Частные ACCEPTANCE/HANDOFF/планы заменены памятками.

Не входят secrets.h, `.sdk`, `.pio`, `.work`, Del, рабочие журналы, дампы,
BIN/ELF, `.vscode` и Windows-ярлык с абсолютным путём. Ссылки только на отсутствующие
локальные документы превращаются в обычные подписи. SHA каждого включённого
файла записан в TRANSFER_MANIFEST.json.

`.gitattributes` сохраняет точные байты файлов без автоматической замены LF/CRLF:
это необходимо для проверки SHA в dependency-lock.json после clone на разных ОС.

## Создать архив

Из полной рабочей копии:

```powershell
python -B tools/project.py check
python -B tools/project.py test
New-Item -ItemType Directory -Path exports -Force
python -B tools/project.py export --public --output exports/ic-wdt-tester-github.zip
```

Имя ZIP должно быть новым; существующий архив не перезаписывается. Экспорт проверяет
allowlist, отсутствие локальных Wi-Fi-значений и заменяет профиль платы примером.
Это конкретная проверка известных настроек, не универсальный поиск всех секретов.
Обычный export без --public предназначен для приватной передачи рабочего контекста.

Распакуйте ZIP в отдельную новую папку. Проверьте README, примеры настроек,
device-profile.json и TRANSFER_MANIFEST.json. Выполните там check/test.
Для сборки потребуется подготовить SDK по [GETTING_STARTED](GETTING_STARTED.md).
Новые бинарники могут содержать Wi-Fi-настройки: не добавляйте их к публичному Release.

## Загрузить подготовленную папку

Создайте пустой репозиторий GitHub с выбранным именем и видимостью.
В терминале **распакованной чистой папки**:

```powershell
git init
git add .
git status --short
git diff --cached --stat
git commit -m "Initial IC WDT Tester source and documentation"
git branch -M main
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git
git push -u origin main
```

Замените YOUR_ACCOUNT/YOUR_REPOSITORY, используйте свою настроенную GitHub-аутентификацию.
Не вставляйте токен в URL или исходники. Не выполняйте эти команды в корне WorckBook.
Если репозиторий уже существует, сначала проверьте его историю и remote вместо
повторного initial push; force-push здесь не требуется.

## Чек-лист перед публикацией

- [ ] Выбрать имя, аккаунт и видимость репозитория.
- [ ] Проверить LICENSE (MIT) и область применения в LICENSING.md; сторонние материалы сохраняют свои условия.
- [ ] Убедиться, что публикуется распакованный --public snapshot.
- [ ] Проверить примеры и staged-файлы, отсутствие secrets.h, BIN и рабочих логов.
- [ ] Выполнить check/test в распакованной папке.
- [ ] Указать, что SDK не включён и содержит локальный пакет esptool.
- [ ] Не объявлять hardware PASS только по успешной сборке.
- [ ] После push проверить отображение README, ссылок и Mermaid на GitHub.

Исходный код и документация готовятся отдельно от фактической публикации;
её результат подтверждается ссылкой на созданный репозиторий и commit.

---

<a id="zh"></a>

## 中文

# 准备和发布到GitHub

应当只上传干净的源代码快照和文档，而不是整个工作目录。
下面创建的存档不会生成GitHub仓库或向互联网发送任何内容。

## 内容

包含README、说明、Mermaid图表、活动且兼容的源代码、
测试、工具、platformio.ini、依赖锁定文件、Wi-Fi/身份示例等。
项目描述和芯片说明为俄语→中文→英语，逐行翻译。
包括[IN1232N/DS1232LP电路图](IC_WDT_HARDWARE.md)及原始PDF
从[来源、版本和 SHA-256](datasheets/README.md)。PDF的版权仍归其所有者；
开源许可不重新定义这些权利。
公共device-profile.json被替换为一个安全模板，该模板不允许
在特定板上进行写入操作。私人ACCEPTANCE/HANDOFF/计划被替换为备忘录。

未包含secrets.h、`.sdk`、`.pio`、`.work`、Del、工作日志、
转储文件、BIN/ELF、`.vscode`和带有绝对路径的Windows快捷方式。仅指向缺失本地文档的链接将转换为普通文字标签。
每个包含文件的SHA值记录在TRANSFER_MANIFEST.json中。

`.gitattributes`保留了文件的确切字节，不自动替换LF/CRLF：
这在克隆到不同操作系统后检查dependency-lock.json中的SHA时是必需的。

## 创建存档

从完整的工作副本开始：

```powershell
python -B tools/project.py check
python -B tools/project.py test
New-Item -ItemType Directory -Path exports -Force
python -B tools/project.py export --public --output exports/ic-wdt-tester-github.zip
```

ZIP文件名必须是新的；现有存档不会被覆盖。导出会检查allowlist，确保没有本地Wi-Fi值，并替换板卡配置为示例。
这是对已知设置的具体验证，而不是通用的查找所有秘密的方法。普通的export（不使用--public选项）旨在用于私有工作环境传输。

将ZIP文件解压到一个新的单独目录中。检查README、设置示例、device-profile.json和TRANSFER_MANIFEST.json。在该目录内执行check/test操作。
构建需要准备SDK，参考[GETTING_STARTED](GETTING_STARTED.md)进行操作。新的二进制文件可能包含Wi-Fi配置：不要将其添加到公共发布版本中。

## 上传准备好的文件夹

创建一个空的GitHub仓库，选择名称和可见性。
在**解压后的干净目录**终端内执行以下命令：
```powershell
git init
git add .
git status --short
git diff --cached --stat
git commit -m "Initial IC WDT Tester source and documentation"
git branch -M main
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git
git push -u origin main
```

替换YOUR_ACCOUNT/YOUR_REPOSITORY，并使用您已配置好的GitHub身份验证。不要将令牌放入URL或源代码中。不要在WorckBook根目录下运行这些命令。
如果仓库已经存在，请先检查其历史记录和远程设置，而不是重新执行初始推送；这里不需要强制推送。

## 发布前的检查清单

- [ ] 选择仓库名称、账户和可见性。
- [ ] 检查 LICENSE（MIT）以及在 LICENSING.md 中的应用范围；第三方材料保留其条件。
- [ ] 确保发布解压后的 --public 快照。
- [ ] 检查示例文件和 staged 文件，确保没有 secrets.h、BIN 和工作日志。
- [ ] 在解压的目录中执行 check/test。
- [ ] 指出 SDK 不包含在内，并且包含本地 esptool 包。
- [ ] 不仅因为构建成功就宣布硬件通过测试。
- [ ] 推送后检查 README、链接和 Mermaid 在 GitHub 上的显示情况。

原始代码和文档独立于实际发布准备；其结果由创建的仓库链接和提交确认。

---

<a id="en"></a>

## English

# Preparation and Publishing to GitHub

Only a clean snapshot of the source code and documentation should be uploaded, not the entire working directory.
The archive created below does not create a GitHub repository or send anything to the internet.

## Contents

Includes README, instructions, Mermaid diagrams, active and compatible sources,
tests, tools, platformio.ini, dependency-lock, Wi-Fi/identity examples. Project description and IC documentation are in Russian → Chinese → English, line by line.
Includes [IN1232N/DS1232LP schematic](IC_WDT_HARDWARE.md) and original PDFs
from [sources, revisions, and SHA-256](datasheets/README.md). Copyright for the PDFs remains with their owners; open-source license does not override these rights.
Public device-profile.json is replaced by a safe template that does not allow writing to a specific board. Private ACCEPTANCE/HANDOFF/plans are replaced by memos.

Not included: secrets.h, `.sdk`, `.pio`, `.work`, Del, working logs, dumps,
BIN/ELF, `.vscode` and Windows shortcut with absolute path. Links only to missing local documents are converted into plain text labels.
The SHA of each included file is recorded in TRANSFER_MANIFEST.json.

`.gitattributes` preserves the exact bytes of files without automatic LF/CRLF replacement: this is necessary for verifying SHA in dependency-lock.json after cloning on different OSes.

## Create Archive

From a full working copy:

```powershell
python -B tools/project.py check
python -B tools/project.py test
New-Item -ItemType Directory -Path exports -Force
python -B tools/project.py export --public --output exports/ic-wdt-tester-github.zip
```

The ZIP filename must be new; the existing archive is not overwritten. Export checks allowlist, ensures no local Wi-Fi values and replaces board profile with an example.
This is a specific validation of known settings, not a universal search for all secrets. A regular export without --public option aims at private context transfer.

Unzip the ZIP file into a new separate directory. Check README, configuration examples, device-profile.json and TRANSFER_MANIFEST.json. Perform check/test within that directory.
The build requires preparing SDK according to [GETTING_STARTED](GETTING_STARTED.md). New binaries may contain Wi-Fi configurations: do not add them to public release versions.

## Upload the Prepared Folder

Create an empty GitHub repository with chosen name and visibility.
In the terminal of a **clean unzipped directory**:
```powershell
git init
git add .
git status --short
git diff --cached --stat
git commit -m "Initial IC WDT Tester source and documentation"
git branch -M main
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git
git push -u origin main
```

Replace YOUR_ACCOUNT/YOUR_REPOSITORY, use your configured GitHub authentication. Do not put token in URL or source code. Do not run these commands at WorckBook root directory.
If repository already exists, first check its history and remote settings instead of re-executing initial push; no forced push is needed here.

## Checklist Before Publishing

- [ ] Choose the repository name, account, and visibility.
- [ ] Check LICENSE (MIT) and scope of use in LICENSING.md; third-party materials retain their conditions.
- [ ] Ensure that a --public unpacked snapshot is published.
- [ ] Check example files and staged files for absence of secrets.h, BIN, and working logs.
- [ ] Perform check/test in the unpacked directory.
- [ ] Indicate that SDK is not included and contains local esptool package.
- [ ] Do not declare hardware PASS solely based on successful build.
- [ ] After push, verify README, links, and Mermaid display on GitHub.

The source code and documentation are prepared separately from the actual release; its result is confirmed by a link to the created repository and commit.
