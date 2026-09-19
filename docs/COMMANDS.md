[Русский](#ru) · [中文](#zh) · [English](#en)

<a id="ru"></a>

## Русский

# Команды активного src/main.cpp

Этот справочник описывает **исходники**. Установленный протокол проверять через
HELP; последняя известная установка и сборка указаны в [ACCEPTANCE](ACCEPTANCE.md).
Serial 115200/8N1, UTF-8; CR или LF; регистр не важен; крайние пробелы удаляются;
максимум 31 символ. Неизвестная или слишком длинная строка не переключает выходы.

| Команда | Действие | Ответ |
| --- | --- | --- |
| `HELP` | Справка, без записи GPIO | Список/описания и capabilities, текст |
| `STS`, `STATUS` | Снимок состояния, без записи GPIO | Совместимая строка STS, обычный подробный вывод, `JSON` type=status |
| `ON` | GPIO13 HIGH; отменяет отложенный ON после сброса | `🟢 GPIO13`; проверить STS |
| `OFF` | GPIO13 LOW без таймера; отменяет отложенный ON | `🔴 GPIO13`; проверить STS |
| `RESET` | Реле OFF → GPIO25 OUTPUT LOW 1000 мс → INPUT (Hi-Z) → реле ON | Сообщения GPIO13/25; проверить ACTIVE/IDLE и конечное состояние |
| `RESET100` | GPIO25 OUTPUT LOW 100 мс → INPUT (Hi-Z); отдельная диагностическая команда | `RESET100 START`, затем `RESET100 DONE`; свежий STS IDLE |
| `RST` | Перезапуск самого тестера через ESP.restart | `RST REBOOT` перед рестартом; затем новая загрузка |
| `HISTORY` | Последние 10 подтверждённых переходов GPIO33 | Текст слева, JSON type=gpio_history справа, replay=true |
| `RESETDIAG` | Чтение PAD/LATCH/OE/IE/MUX GPIO25 и GPIO33 | Одна текстовая строка RESETDIAG; выходы не меняет |

OFF держится до явного ON, нового RESET или reboot. RESET включает реле в конце,
даже если оно было OFF до команды. ON/OFF во время импульса действуют сразу и
отменяют отложенный ON; GPIO25 всё равно будет отпущен по таймеру.
Повтор RESET/RESET100 заменяет длительность и начинает отсчёт заново. Отдельный
RESET100 не меняет реле; если заменяет активный RESET, наследует его отложенный ON.
Дополнительных пауз на механическое переключение реле нет. Длительности номинальные:
Serial/Wi-Fi и loop могут продлить импульс; контакты/сигнал отдельно измеряются.

RST перед перезагрузкой отпускает активный GPIO25 и завершает передачу ACK через
Serial.flush. После старта GPIO13 ON, GPIO25 INPUT без внутренней подтяжки; история/event_id/uptime и NTP
начинают новый цикл. ACK не доказывает, что контроллер уже загрузился.

GPIO33 — INPUT_PULLUP, фильтр 40 мс. При каждом подтверждённом переходе обычное
сообщение с Unix-временем слева, JSON type=gpio_change справа и таблица истории.
Таблица HISTORY откладывается во время активного RESET до отпускания GPIO25.
STS/STATUS, новые переходы GPIO33 и строки HISTORY имеют JSON; для остальных ответов
используется текстовый протокол/CurrentProtocol. [Контракт JSON](TELEMETRY.md).

---

<a id="zh"></a>

## 中文

# 活动 src/main.cpp 命令

本手册描述 **源代码**。安装的协议通过 HELP 查看；最近已知的固件安装和构建在 [ACCEPTANCE](ACCEPTANCE.md) 中列出。
串行通信：115200/8N1，UTF-8；CR 或 LF；大小写不敏感；删除首尾空格；最大 31 字符。未知或过长的字符串不会切换输出。

| 命令 | 动作 | 回复 |
| --- | --- | --- |
| `HELP` | 显示帮助，不写入 GPIO | 列表/描述和功能，文本形式 |
| `STS`, `STATUS` | 获取状态快照，不写入 GPIO | 兼容的 STS 字符串，常规详细输出，`JSON` type=status 类型 |
| `ON` | 设置 GPIO13 HIGH；取消在复位后的延迟 ON | `🟢 GPIO13`；检查 STS 状态 |
| `OFF` | 将 GPIO13 低电平设置为 LOW，不使用定时器；取消延迟的 ON | `🔴 GPIO13`；检查 STS 状态 |
| `RESET` | 继电器 OFF → GPIO25 输出 LOW 1000 毫秒 → 输入（Hi-Z）→ 继电器 ON | GPIO13/25 的消息；检查 ACTIVE/IDLE 和最终状态 |
| `RESET100` | 将 GPIO25 设置为输出 LOW 100 毫秒，然后设置为输入（Hi-Z）；独立的诊断命令 | `RESET100 START`，随后是 `RESET100 DONE`；最新的 STS IDLE 状态 |
| `RST` | 通过 ESP.restart 重启测试器本身 | 在重启前发送 `RST REBOOT`；然后重新加载 |
| `HISTORY` | 最近的 10 次确认 GPIO33 转换 | 左侧文本，右侧 JSON 类型=gpio_history，replay=true |
| `RESETDIAG` | 读取 PAD/LATCH/OE/IE/MUX 的 GPIO25 和 GPIO33 状态 | 单行文本 RESETDIAG；不改变输出状态 |

OFF 保持到明确的 ON、新的 RESET 或重启。RESET 在结束时开启继电器，即使命令执行前继电器已处于 OFF。脉冲期间的 ON/OFF 立即生效并取消延迟 ON；GPIO25 仍会按定时器释放。
重复 RESET/RESET100 会替换脉冲时长并重新开始计时。单独的 RESET100 不改变继电器；若替换正在进行的 RESET，则继承其延迟 ON。没有额外的继电器机械切换等待时间。时长是标称值：Serial/Wi-Fi 和 loop 可能延长脉冲；触点和信号须另行测量。

RST 在重启前释放处于激活状态的 GPIO25，并通过 Serial.flush 完成 ACK 发送。启动后 GPIO13 为 ON，GPIO25 为 INPUT 且不启用内部上拉；history/event_id/uptime 和 NTP 开始新周期。ACK 不证明控制器已经启动。

GPIO33 为 INPUT_PULLUP，滤波时间 40 ms。每次确认电平变化时，左侧输出带 Unix 时间的普通消息，右侧输出 JSON type=gpio_change，并输出历史表。RESET 激活期间，HISTORY 表推迟至 GPIO25 释放后输出。
STS/STATUS、新的 GPIO33 变化和 HISTORY 行包含 JSON；其他回复使用文本协议/CurrentProtocol。[JSON 协议](TELEMETRY.md)。

---

<a id="en"></a>

## English

# Active src/main.cpp Commands

This guide describes **sources**. The installed protocol can be checked via HELP; the latest known installation and build are listed in [ACCEPTANCE](ACCEPTANCE.md).
Serial: 115200/8N1, UTF-8; CR or LF; case insensitive; leading/trailing spaces removed; maximum of 31 characters. Unknown or too long strings do not switch outputs.

| Command | Action | Response |
| --- | --- | --- |
| `HELP` | Display help, no GPIO writes | List/descriptions and capabilities, text format |
| `STS`, `STATUS` | Take state snapshot, no GPIO writes | Compatible STS string, detailed output, `JSON` type=status |
| `ON` | Set GPIO13 HIGH; cancels delayed ON after reset | `🟢 GPIO13`; check STS status |
| `OFF` | Set GPIO13 LOW without timer; cancel delayed ON | `🔴 GPIO13`; check STS status |
| `RESET` | Relay OFF → GPIO25 output LOW 1000 ms → input (Hi-Z) → relay ON | Messages from GPIO13/25; check ACTIVE/IDLE and final state |
| `RESET100` | Set GPIO25 to output LOW for 100 ms, then set as input (Hi-Z); standalone diagnostic command | `RESET100 START`, followed by `RESET100 DONE`; fresh STS IDLE status |
| `RST` | Restart the tester itself via ESP.restart | Send `RST REBOOT` before restart; then a new boot |
| `HISTORY` | Last 10 confirmed GPIO33 transitions | Text on left, JSON type=gpio_history on right, replay=true |
| `RESETDIAG` | Read PAD/LATCH/OE/IE/MUX status of GPIO25 and GPIO33 | Single text line RESETDIAG; does not change output state |

OFF persists until an explicit ON, a new RESET or reboot. RESET turns the relay ON at the end even if it was OFF before the command. ON/OFF during a pulse act immediately and cancel delayed ON; GPIO25 is still released by the timer.
Repeating RESET/RESET100 replaces the duration and restarts timing. A standalone RESET100 does not change the relay; if it replaces an active RESET, it inherits its delayed ON. There are no additional waits for mechanical relay switching. Durations are nominal: Serial/Wi-Fi and loop may extend the pulse; contacts and signals require separate measurements.

Before reboot, RST releases active GPIO25 and completes ACK transmission through Serial.flush. After startup, GPIO13 is ON and GPIO25 is INPUT without an internal pull-up; history/event_id/uptime and NTP start a new cycle. ACK does not prove that the controller has already booted.

GPIO33 uses INPUT_PULLUP with a 40 ms filter. Each confirmed transition produces a normal message with Unix time on the left, JSON type=gpio_change on the right, and a history table. During active RESET, the HISTORY table is deferred until GPIO25 is released.
STS/STATUS, new GPIO33 transitions and HISTORY rows have JSON; other replies use the text protocol/CurrentProtocol. [JSON contract](TELEMETRY.md).
