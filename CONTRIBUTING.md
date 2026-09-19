[Русский](#ru) · [中文](#zh) · [English](#en)

<a id="ru"></a>

## Русский

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

---

<a id="zh"></a>

## 中文

# 项目变更

从 [AGENTS](AGENTS.md)，[指令索引](docs/INSTRUCTIONS_INDEX.md)
和 [工作描述](docs/HOW_IT_WORKS.md) 开始。为了设置，请参阅 [GETTING_STARTED](docs/GETTING_STARTED.md).

1. 在修改之前执行 `python -B tools/project.py check`.
2. 保持 CurrentProtocol 和单独的 LATCH-02 的兼容性。
3. GPIO25: 只能 LOW → INPUT，不启用上拉；GPIO12 不用作 RESET.
4. 不要在工作循环中添加延迟。新的 JSON 字段需要反映在协议和解析器中。
5. 仅对故意更改的依赖项更新 dependency-lock.
6. 执行 `python -B tools/project.py test`; 对于固件，还需要 SDK preflight 和构建。
7. 在变更描述中区分 source/test/build/flash/UART/hardware.

不要提交 Wi-Fi 设置源代码：本地 secrets.h 被忽略。使用 secrets.example.h 作为示例。
通过 `project.py export --public` 创建公共包；完整的开发工作目录不添加到 Git 中。

不要仅仅因为不在活动构建过滤器中就删除 legacy 文件：它们可能被 IC_WDT_Probe 引用。
根据带有 SHA 的清单移动旧材料，保留回滚和硬件测试结果。

固件、RESET/RST/ON/OFF 命令需要明确的操作方案、明确的板卡、接线以及单一的 COM 所有者。此项目的测试不打开 COM.

---

<a id="en"></a>

## English

# Project Changes

Start with [AGENTS](AGENTS.md), [instruction map](docs/INSTRUCTIONS_INDEX.md)
and [description of operation](docs/HOW_IT_WORKS.md). For setup, refer to [GETTING_STARTED](docs/GETTING_STARTED.md).

1. Execute `python -B tools/project.py check` before making changes.
2. Maintain compatibility with CurrentProtocol and individual LATCH-02.
3. GPIO25: only LOW → INPUT without pull-up; do not use GPIO12 as RESET.
4. Do not add delay in the working cycle. Reflect new JSON fields in the contract and parser.
5. Update dependency-lock only for intentionally modified dependencies.
6. Execute `python -B tools/project.py test`; for firmware, also perform SDK preflight and build.
7. Distinguish source/test/build/flash/UART/hardware in change descriptions.

Do not commit Wi-Fi setup sources: local secrets.h is ignored. Use secrets.example.h as an example.
Create public packages via `project.py export --public`; do not add the full development working directory to Git.

Do not delete legacy files just because they are not in active build filters: they may be referenced by IC_WDT_Probe.
Move old materials according to a manifest with SHA, preserving rollback and hardware test results.

Firmware, RESET/RST/ON/OFF commands require a clear operating scenario, specific boards, wiring, and one COM owner. This project's tests do not open COM.
