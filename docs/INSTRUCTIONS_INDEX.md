[Русский](#ru) · [中文](#zh) · [English](#en)

<a id="ru"></a>

## Русский

# Карта инструкций

## Действующие документы

| Документ | Когда читать |
| --- | --- |
| [README](../README.md) | Вход для человека, пины, запуск |
| [Future](FUTURE.md) | О проекте / 项目介绍 / About the project |
| [Галерея / 图库 / Gallery](GALLERY.md) | Фото и модели / 照片与型号 / Photos and models |
| [Лицензия / 许可 / License](LICENSING.md) | MIT и свободное применение / MIT 与自由使用 / MIT and free use |
| [Коммерческие документы / 商务文件 / Commercial documents](commercial/INDEX.md) | Русский → 中文 → English |
| [Оплата / 付款 / Payment](PAYMENT.md) | Реквизиты и запрос счёта / 收款资料与账单 / Accounts and invoice requests |
| [GETTING_STARTED](GETTING_STARTED.md) | Новый компьютер, Wi-Fi, SDK, сборка и первая проверка |
| [WIRING](WIRING.md) | Подключение GPIO, общая земля и схема |
| [IC_WDT_HARDWARE](IC_WDT_HARDWARE.md) | RU/中文/EN: IN1232N, DS1232LP, схема, TOL, TD, проверка |
| [Datasheets](datasheets/README.md) | Оригинальные PDF, редакции, зеркала и SHA-256 |
| [VALIDATION_20260919](VALIDATION_20260919.md) | Проверки, команды, USB и выявленные аппаратные ограничения |
| [HOW_IT_WORKS](HOW_IT_WORKS.md) | Цикл, реле, RESET, история, Wi-Fi и LED |
| [TROUBLESHOOTING](TROUBLESHOOTING.md) | Ошибки USB/UART, flash, сети и времени |
| [GITHUB](GITHUB.md) | Публичный snapshot и инструкции публикации |
| [CONTRIBUTING](../CONTRIBUTING.md) | Порядок изменения исходников и проверок |
| [AGENTS](../AGENTS.md) | Границы проекта для ИИ |
| [AI_QUICKSTART](AI_QUICKSTART.md) | Первое чтение другого ИИ |
| [COMMANDS](COMMANDS.md) | Все команды активного исходника и ответы |
| [TELEMETRY](TELEMETRY.md) | JSON-контракт и offline-парсер |
| [OPERATOR](OPERATOR.md) | Разрешённая live-сессия, транспорт, действия/ошибки |
| [USB_COM_RECOVERY](USB_COM_RECOVERY.md) | USB Serial, выбор портов, UAC и журнал |
| [USB_RESTART_PLAN](../USB_RESTART_PLAN.md) | Перед USB-командами: план, дорожная карта, чек-лист и фактический итог |
| [CODE_STYLE](CODE_STYLE.md) | Код и обязательные offline-проверки |
| [PROJECT_LAYOUT](PROJECT_LAYOUT.md) | Полная карта файлов, совместимость, опись и Del |
| [NVS_RECOVERY_PLAN](../NVS_RECOVERY_PLAN.md) | GPIO25, точный образ и незавершённая установка |
| [PORTABILITY](PORTABILITY.md) | Перенос, allowlist, зависимости |
| [HANDOFF](HANDOFF.md) | Состояние и следующий шаг |
| [ACCEPTANCE](ACCEPTANCE.md) | Подтверждения сборки/установки/live |
| [Проектный навык](../skills/esp32-ic-wdt-tester/SKILL.md) | Переносимые правила работы с тестером |

## История и совместимость

- [LEGACY_LATCH02](LEGACY_LATCH02.md) — только отдельно подтверждённая старая прошивка.
- [RECHECK_20260918](RECHECK_20260918.md) — датированные опыты, не текущая инструкция.
- Архив до очистки (local workspace reference) — прежние документы с SHA-256.

В полном WorckBook общие правила: AI_MASTER (local workspace reference).
Протокол установленной платы всегда проверяется HELP; наличие команды в таблице
исходников не доказывает её наличие на устройстве.

---

<a id="zh"></a>

## 中文

# 指令地图

## 生效文档

| 文档 | 何时阅读 |
| --- | --- |
| [README](../README.md) | 用户入口、引脚与启动 |
| [Future](FUTURE.md) | 关于项目 / 项目介绍 / About the project |
| [Галерея / 图库 / Gallery](GALLERY.md) | 照片与型号 / Photos and models |
| [Лицензия / 许可 / License](LICENSING.md) | MIT 和自由使用 / MIT and free use |
| [Коммерческие документы / 商务文件 / Commercial documents](commercial/INDEX.md) | 俄文 → 中文 → 英文 |
| [Оплата / 付款 / Payment](PAYMENT.md) | 收款资料与账单请求 / Accounts and invoice requests |
| [GETTING_STARTED](GETTING_STARTED.md) | 新计算机、Wi-Fi、SDK、编译和首次验证 |
| [WIRING](WIRING.md) | GPIO连接、公共地线和电路图 |
| [IC_WDT_HARDWARE](IC_WDT_HARDWARE.md) | RU/中文/EN: IN1232N, DS1232LP, 电路图, TOL, TD, 验证 |
| [Datasheets](datasheets/README.md) | 原始PDF、版本、镜像和SHA-256 |
| [VALIDATION_20260919](VALIDATION_20260919.md) | 验证、命令、USB和发现的硬件限制 |
| [HOW_IT_WORKS](HOW_IT_WORKS.md) | 循环、继电器、RESET、历史记录、Wi-Fi和LED |
| [TROUBLESHOOTING](TROUBLESHOOTING.md) | USB/UART错误、闪存问题、网络和时间问题 |
| [GITHUB](GITHUB.md) | 公共快照和发布指南 |
| [CONTRIBUTING](../CONTRIBUTING.md) | 更改源代码的顺序和验证 |
| [AGENTS](../AGENTS.md) | 项目边界与AI |
| [AI_QUICKSTART](AI_QUICKSTART.md) | 另一个AI的第一读取 |
| [COMMANDS](COMMANDS.md) | 活动源代码的所有命令和响应 |
| [TELEMETRY](TELEMETRY.md) | JSON协议与离线解析器 |
| [OPERATOR](OPERATOR.md) | 允许的实时会话、传输、动作/错误 |
| [USB_COM_RECOVERY](USB_COM_RECOVERY.md) | USB串行，端口选择，UAC和日志 |
| [USB_RESTART_PLAN](../USB_RESTART_PLAN.md) | 在USB命令之前：计划、路线图、检查表和实际结果 |
| [CODE_STYLE](CODE_STYLE.md) | 代码与强制性离线验证 |
| [PROJECT_LAYOUT](PROJECT_LAYOUT.md) | 文件完整地图、兼容性、清单和Del |
| [NVS_RECOVERY_PLAN](../NVS_RECOVERY_PLAN.md) | GPIO25, 精确映像和未完成安装 |
| [PORTABILITY](PORTABILITY.md) | 可移植性、allowlist、依赖项 |
| [HANDOFF](HANDOFF.md) | 状态与下一步 |
| [ACCEPTANCE](ACCEPTANCE.md) | 编译/安装/live确认 |
| [项目技能](../skills/esp32-ic-wdt-tester/SKILL.md) | 测试器可移植规则 |

## 历史和兼容性

- [LEGACY_LATCH02](LEGACY_LATCH02.md) — 只有单独验证的老固件。
- [RECHECK_20260918](RECHECK_20260918.md) — 日期标记的实验，不是当前指南。
- 清理前的存档（本地工作区引用）— 带 SHA-256 的旧文档。

在完整的 WorckBook 中，通用规则是：AI_MASTER (本地工作区引用)。安装板的协议始终由 HELP 检查；源代码表中的命令存在并不证明设备上也存在这些命令。

---

<a id="en"></a>

## English

# Instruction Map

## Active Documents

| Document | When to read |
| --- | --- |
| [README](../README.md) | Entry point for users, pins and startup |
| [Future](FUTURE.md) | About the project |
| [Галерея / 图库 / Gallery](GALLERY.md) | Photos and models |
| [Лицензия / 许可 / License](LICENSING.md) | MIT and free use |
| [Коммерческие документы / 商务文件 / Commercial documents](commercial/INDEX.md) | Russian → Chinese → English |
| [Оплата / 付款 / Payment](PAYMENT.md) | Accounts and invoice requests |
| [GETTING_STARTED](GETTING_STARTED.md) | New computer, Wi-Fi, SDK, build and first validation |
| [WIRING](WIRING.md) | GPIO connection, common ground and circuit diagram |
| [IC_WDT_HARDWARE](IC_WDT_HARDWARE.md) | RU/Chinese/EN: IN1232N, DS1232LP, schematic, TOL, TD, validation |
| [Datasheets](datasheets/README.md) | Original PDFs, revisions, mirrors and SHA-256 |
| [VALIDATION_20260919](VALIDATION_20260919.md) | Validations, commands, USB and discovered hardware limitations |
| [HOW_IT_WORKS](HOW_IT_WORKS.md) | Cycle, relay, RESET, history, Wi-Fi and LED |
| [TROUBLESHOOTING](TROUBLESHOOTING.md) | USB/UART errors, flash issues, network and time problems |
| [GITHUB](GITHUB.md) | Public snapshot and publication instructions |
| [CONTRIBUTING](../CONTRIBUTING.md) | Order of source code changes and validations |
| [AGENTS](../AGENTS.md) | Project boundaries for AI |
| [AI_QUICKSTART](AI_QUICKSTART.md) | First read of another AI |
| [COMMANDS](COMMANDS.md) | All commands of active source code and responses |
| [TELEMETRY](TELEMETRY.md) | JSON contract and offline parser |
| [OPERATOR](OPERATOR.md) | Allowed live session, transport, actions/errors |
| [USB_COM_RECOVERY](USB_COM_RECOVERY.md) | USB serial, port selection, UAC and log |
| [USB_RESTART_PLAN](../USB_RESTART_PLAN.md) | Before USB commands: plan, roadmap, checklist and actual outcome |
| [CODE_STYLE](CODE_STYLE.md) | Code and mandatory offline validations |
| [PROJECT_LAYOUT](PROJECT_LAYOUT.md) | Full file map, compatibility, inventory and Del |
| [NVS_RECOVERY_PLAN](../NVS_RECOVERY_PLAN.md) | GPIO25, precise image and unfinished installation |
| [PORTABILITY](PORTABILITY.md) | Portability, allowlist, dependencies |
| [HANDOFF](HANDOFF.md) | Status and next step |
| [ACCEPTANCE](ACCEPTANCE.md) | Build/install/live acceptance |
| [Project Skill](../skills/esp32-ic-wdt-tester/SKILL.md) | Portable rules for tester |

## History and Compatibility

- [LEGACY_LATCH02](LEGACY_LATCH02.md) — only separately verified old firmware.
- [RECHECK_20260918](RECHECK_20260918.md) — dated experiments, not current instructions.
- Archive before cleanup (local workspace reference) — old documents with SHA-256.

In the full WorckBook, general rules are: AI_MASTER (local workspace reference). The protocol of installed board is always checked by HELP; presence of commands in source table does not prove their existence on device.
