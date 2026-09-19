[Русский](#ru) · [中文](#zh) · [English](#en)

<a id="ru"></a>

## Русский

# Перезапуск USB/COM: оператор и ИИ

Проектный скрипт: [tools/restart_usb_port.ps1](../tools/restart_usb_port.ps1).
Он основан на прежнем `restart_com4.ps1`, но не содержит старого InstanceId,
номера порта или пути рабочего компьютера. Параметры выбирают ровно один
USB serial adapter класса Ports. Другие USB, хабы и контроллеры не перезапускаются.

Это PnP-перезапуск устройства через Windows `pnputil /restart-device`.
Отключение питания USB не гарантируется. ESP32 может перезагрузиться;
тестер после reboot возвращает реле ON. Команда прошивки `RST` отдельно
перезапускает сам ESP32, не Windows USB-адаптер.

## Запуск ярлыком из корня

`restart_usb_port.ps1.lnk` открывает Windows PowerShell и запускает
[restart_usb_interactive.ps1](../tools/restart_usb_interactive.ps1).
Сразу создаётся или дописывается **`usb-restart.log` в корне проекта** — даже
если пользователь затем отменит действие или preview завершится ошибкой.
Окно остаётся открытым после завершения, чтобы можно было прочитать результат.

Launcher автоматически находит все USB Serial (класс Ports, USB InstanceId),
показывает порт и точный target каждого. Корневой ярлык передаёт `-All -Apply`:
он запускает перезапуск всех найденных; при необходимости подтвердите UAC.
При запуске launcher без `-Apply` есть текстовый вопрос `RESTART ALL`;
пустой ввод отменяет действие.
Перезапуски последовательные; при первой ошибке или неподтверждённом PnP OK
оставшиеся порты не обрабатываются. Устройства, подключённые после поиска,
в текущий запуск не добавляются. При реальном запросе перезапуска дополнительно
пишутся `usb-restart.jsonl` и отдельный JSON-отчёт, описанные ниже.
Ярлык не хранит номер порта или USB identity. После переноса проекта Windows-ярлык
нужно пересоздать; сам launcher использует пути относительно проекта.

В `usb-restart.log` этапы START/DISCOVERED/TARGET/APPLY/RESULT/ERROR/END имеют время
и общий launch_id. RESULT указывает COM, USB target, код команды и PnP после неё.
Полный JSON receipt содержит `command`, `steps`, stdout pnputil и ошибки.
Журнал дописывается, предыдущие запуски остаются доступными.

### Команды для ИИ и терминала

Каждое событие launcher видно в терминале как **`JSON {...}`** и дописывается
без префикса в **`usb-restart-events.jsonl` в корне проекта**, UTF-8, один объект
на строку. В отличие от `usb-restart.jsonl` (только Apply), этот файл включает
обнаружение, preview, отмену, результат и ошибки. Человеческий `.log` сохраняется.

Схема `schema=1`, `type=usb_restart_event`:

| Поле | Значение |
| --- | --- |
| utc, launch_id, sequence | Время UTC, идентификатор запуска, порядковый номер события |
| action, level | START, DISCOVERED, TARGET, APPLY, RESULT, ERROR, END и др.; info/error |
| port, target | COM и USB InstanceId, либо null вне конкретного устройства |
| message | Читаемое описание |
| data | Параметры, выбранные устройства и ответ команды |
| error | null либо message, exception_type, id, category, phase |

В RESULT `data.response` содержит полный receipt: код возврата, stdout Windows,
команду, steps, PnP-статусы, receipt_path и operation_id. В ERROR ответ и пути
прикладываются, если есть новый receipt именно этого запроса; отсутствие ответа
не означает exit_code=0. Старый существовавший receipt не считается новым результатом.
END содержит `data.outcome`: COMPLETED, PREVIEW_ONLY, CANCELLED или ERROR,
а также `completed_ports`. При обрыве процесса END может отсутствовать — результат
нужно сверять, а не повторять команду. Даже COMPLETED не означает проверку UART.

Машинный журнал открывается до операций и имеет одного writer на весь запуск.
При невозможности открыть журнал выводится JSON-ошибка в терминал, USB не меняется.
Текстовые сообщения PowerShell вне префикса JSON не нужно разбирать как события.

Готовый offline-reader не обращается к устройствам. По умолчанию сам находит журнал
в корне проекта; выдаёт JSONL и ненулевой код при повреждённом/недочитанном JSON:

```powershell
python -B tools/read_usb_restart_events.py --last-launch
python -B tools/read_usb_restart_events.py --last-launch --errors
python -B tools/read_usb_restart_events.py --launch-id <id>
# Просмотр новых событий непосредственно из файла:
Get-Content .\usb-restart-events.jsonl -Tail 10 -Wait
```

Сначала проверять exit code reader. Пустой вывод `--errors` означает только
отсутствие ERROR среди сохранённых событий; успех подтверждается RESULT и END.

```powershell
# Только обнаружение; ничего не перезапускает:
.\tools\restart_usb_port.ps1 -ListPorts
# Проверка всех найденных с записью в usb-restart.log:
.\tools\restart_usb_interactive.ps1 -All -PreviewOnly
# Разрешённый перезапуск всех найденных без текстового вопроса (UAC остаётся):
.\tools\restart_usb_interactive.ps1 -All -Apply
# Разрешённый перезапуск только выбранного порта:
.\tools\restart_usb_interactive.ps1 -Port COM4 -Apply
# Последние записи для просмотра:
Get-Content .\usb-restart.log -Tail 100
```

Перед Apply действуют правила владельца COM и отсутствия прошивки из OPERATOR.
Автообнаружение USB Serial не определяет роль платы и не проверяет занятость COM.
План и результаты: [USB_RESTART_PLAN](../USB_RESTART_PLAN.md).

## Предварительный просмотр

Windows PowerShell 5.1+; команды ниже выполняются из корня проекта.
COM4 — только пример: использовать текущий порт нужной платы.

```powershell
$preview = & .\tools\restart_usb_port.ps1 -Port COM4
$preview | Format-List
```

Без `-Apply` скрипт только читает PnP: не открывает COM, не вызывает UAC,
не создаёт receipt и не перезапускает устройства. Проверить `port`, `name`,
`target` и связь с нужной платой. PnP ID не заменяет chip model/factory BASE_MAC.

## Разрешённый перезапуск

Можно запустить из обычного PowerShell/терминала VS Code. При `-Apply`
скрипт сам вызывает окно Windows UAC: нажать «Да». Административный дочерний
PowerShell запускается скрытым и повторно сверяет устройство перед перезапуском.
Если текущий PowerShell уже административный, дополнительного окна нет.
Preview без `-Apply` не вызывает UAC. Пример из корня проекта:

```powershell
$preview = & .\tools\restart_usb_port.ps1 -Port COM4
$preview | Format-List
# После проверки target и готовности стенда:
& .\tools\restart_usb_port.ps1 -Port COM4 -ExpectedInstanceId $preview.target -Apply
Get-Content -LiteralPath .\usb-restart.jsonl -Tail 2
```

При `-Apply` скрипт дописывает журнал `usb-restart.jsonl` **в корне проекта**,
независимо от текущего каталога терминала. Каждая операция получает две JSON-строки
с одним `operation_id`: STARTED и результат либо STOP с ошибкой. Сохраняются время UTC,
порт, ожидаемый target и путь отдельного отчёта; при успехе — также содержимое отчёта.
Отказ UAC и ошибки предварительных проверок тоже попадают в журнал. Если процесс
прерван и осталась только STARTED, результат неизвестен — читать отчёт, не повторять
перезапуск вслепую. Preview журнал не создаёт и не изменяет.

Без `-ReceiptPath` отдельный отчёт автоматически создаётся рядом:
`usb-restart-<operation_id>.json`. Явный `-ReceiptPath` позволяет выбрать другое место,
но общий журнал остаётся в корне. Он открывается до попытки перезапуска; ошибка записи
или занятый другим запуском журнал останавливает новую операцию. Родитель ведёт журнал
во время UAC, дочерний процесс пишет только отдельный отчёт.

ReceiptPath должен быть новым файлом в существующем каталоге.
Скрипт проверяет возможность записи до перезапуска,
отказывается перезаписывать старый receipt и повторно сверяет target перед вызовом.
Пути не зависят от местоположения исходного WorckBook; `ReceiptPath` разрешается
от текущего каталога PowerShell. Старый runtime-скрипт не изменён.

## Порядок для ИИ

1. Прочитать [OPERATOR](OPERATOR.md), уточнить в текущей задаче роль платы,
   порт, владельца COM и разрешённый сценарий восстановления. Добавление этого
   скрипта в проект само по себе не разрешает перезапуск. Уже данное разрешение
   на точный сценарий действует; повторного подтверждения не требовать.
2. Сохранить исходную ошибку. PnP Status OK не доказывает рабочий UART.
   Проверить отсутствие прошивки/ROM-операции и активной работы другого владельца.
   Освободить собственные handles штатно; чужие процессы не завершать.
   Скрипт не определяет владельца COM и не проверяет занятость порта.
3. Выполнить preview, сверить конкретное устройство с текущим подключением.
   Не подставлять старый COM4/InstanceId из истории. Не перебирать все Ports,
   не использовать wildcard и не перезапускать родительский хаб.
4. Для разрешённого действия использовать точный ExpectedInstanceId;
   ReceiptPath можно опустить для автоматического отчёта в корне.
   Неадминистративный `-Apply` автоматически запускает дочерний
   PowerShell через `Start-Process -Verb RunAs -WindowStyle Hidden -Wait`.
   Окно UAC подтверждает оператор. Аргументы передаются литералами PowerShell
   внутри UTF-16 EncodedCommand, путь receipt заранее становится абсолютным.
   Служебный ElevatedChild предотвращает повторный запрос UAC при отсутствии
   повышенного токена; вручную его передавать не нужно.
   Отмена UAC или ошибка запуска — остановка без retry; receipt может отсутствовать.
   После завершения родитель проверяет exit code и result/target/port в receipt.
5. Ошибка сопоставления/прав/receipt до native-вызова означает остановку без
   перезапуска. STOP с `restart_attempted=true` означает неопределённый или
   неуспешный результат уже запрошенного действия: прочитать receipt, не повторять
   автоматически. Ненулевой код, включая требование перезагрузки Windows,
   не вызывает перезагрузку компьютера автоматически.
6. RESTART_COMMAND_SUCCEEDED подтверждает только код 0 от pnputil. Перечитать
   mapping; отсутствие `after_status` или наличие `after_error` требует новой проверки PnP.
   Затем в разрешённой сессии проверить реальные данные Serial 115200, HELP/STS,
   uptime и build marker. `uart_verified=false` остаётся честным результатом
   самого скрипта: UART он не открывает. Новая прошивка требует свежей factory identity.
7. Записать receipt и границы результата в [ACCEPTANCE](ACCEPTANCE.md).
   Не считать USB restart подтверждением GPIO/WDI/контактов или исправлением firmware.

## Проверки без оборудования

`python -B tools/project.py test` включает изолированные PowerShell-тесты
с подменой PnP/admin/native call. Они не обращаются к USB или COM.
На системе без PowerShell соответствующая проверка явно пропускается.
Живой preview читает PnP; live Apply — отдельная операция по правилам выше.

---

<a id="zh"></a>

## 中文

# USB/COM重启：操作员和AI

项目脚本：[tools/restart_usb_port.ps1](../tools/restart_usb_port.ps1)。
它基于之前的`restart_com4.ps1`，但不包含旧的InstanceId、端口编号或工作站路径。参数选择一个USB串行适配器（Ports类）。其他USB设备、集线器和控制器不会被重启。

这是通过Windows `pnputil /restart-device`进行即插即用设备重启。
断电USB电源不能保证。ESP32可能会重新启动；测试仪在重置后返回继电器ON状态。固件命令`RST`单独重启ESP32，而不是Windows USB适配器。

## 从根目录通过快捷方式运行

`restart_usb_port.ps1.lnk`打开Windows PowerShell并运行[restart_usb_interactive.ps1](../tools/restart_usb_interactive.ps1)。
立即在项目根目录中创建或追加**`usb-restart.log`**——即使用户随后取消了操作或预览以错误结束。窗口保持打开，以便可以阅读结果。

启动器会自动发现所有USB串行（端口类，USB实例ID），显示每个端口及其确切目标。根目录快捷方式传递`-All -Apply`：它将重新启动所有找到的；如有必要，请确认UAC。如果没有`-Apply`，在启动时会有文本问题`RESTART ALL`；空输入会取消操作。
重新启动是连续进行的；在第一次错误或未确认PnP OK的情况下，其余端口将不会被处理。在搜索之后连接的设备在当前启动中不会添加。在实际请求重新启动时，还会额外写入`usb-restart.jsonl`和单独的JSON报告，如下所述。
快捷方式不保存端口号或USB标识符。移动Windows项目后，需要重建项目中的Windows快捷方式；而启动器使用相对于项目的路径。

在`usb-restart.log`阶段，START/DISCOVERED/TARGET/APPLY/RESULT/ERROR/END具有时间和共同的launch_id。RESULT指示COM、USB目标、命令代码和其后的PnP状态。
完整的JSON收据包含`command`、`steps`、stdout pnputil输出以及错误信息。日志会追加，以前的启动仍然可用。

### AI 与终端命令

启动器的每个事件都在终端显示为 **`JSON {...}`**，并以不带前缀的形式追加到**项目根目录的 `usb-restart-events.jsonl`**，使用 UTF-8，每行一个对象。与仅记录 Apply 的 `usb-restart.jsonl` 不同，此文件包括发现、预览、取消、结果和错误。面向用户的 `.log` 仍保留。

结构 `schema=1`、`type=usb_restart_event`：

| 字段 | 值 |
| --- | --- |
| utc, launch_id, sequence | UTC 时间，启动 ID，事件序列号 |
| action, level | START, DISCOVERED, TARGET, APPLY, RESULT, ERROR, END 等；info/error |
| port, target | COM 和 USB InstanceId，或者在特定设备之外为 null |
| message | 可读描述 |
| data | 参数、选定的设备和命令响应 |
| error | null 或 message, exception_type, id, category, phase |

在 RESULT `data.response` 中包含完整的收据：返回代码，Windows stdout，
命令，步骤，PnP 状态，收据路径和操作 ID。在 ERROR 响应中附加路径，
如果存在新请求的收据；无响应不意味着 exit_code=0。旧存在的收据不被视为新的结果。
END 包含 `data.outcome`：COMPLETED, PREVIEW_ONLY, CANCELLED 或者 ERROR，
以及 `completed_ports`。在进程中断的情况下 END 可能不存在——需要验证结果而不是重复命令。
即使 COMPLETED 也不意味着 UART 的检查。

机器日志在操作前打开，并在整个启动过程中只有一个 writer。如果无法打开日志，则输出 JSON 错误到终端，USB 不会改变。
PowerShell 中非 JSON 前缀的文本消息不需要解析为事件。

离线阅读器不与设备交互。默认情况下，在项目根目录中找到日志；
返回 JSONL 和非零代码如果 JSON 损坏或未读完：
```powershell
python -B tools/read_usb_restart_events.py --last-launch
python -B tools/read_usb_restart_events.py --last-launch --errors
python -B tools/read_usb_restart_events.py --launch-id <id>
# 直接从文件查看新事件：
Get-Content .\usb-restart-events.jsonl -Tail 10 -Wait
```

首先检查读取器的退出码。空输出 `--errors` 只表示
没有 ERROR 在保存的事件中；成功由 RESULT 和 END 确认。

```powershell
# 仅发现设备，不执行重启：
.\tools\restart_usb_port.ps1 -ListPorts
# 检查全部已发现设备，并写入 usb-restart.log：
.\tools\restart_usb_interactive.ps1 -All -PreviewOnly
# 经授权重启全部已发现设备，不显示文本询问（仍需 UAC）：
.\tools\restart_usb_interactive.ps1 -All -Apply
# 仅对选定端口执行经授权的重启：
.\tools\restart_usb_interactive.ps1 -Port COM4 -Apply
# 查看最新记录：
Get-Content .\usb-restart.log -Tail 100
```

执行 Apply 前，须遵守 OPERATOR 中的 COM 所有权规则，并确认没有正在进行的固件写入。
自动检测 USB Serial 不确定板卡的角色且不检查 COM 是否被占用。
计划与结果：[USB_RESTART_PLAN](../USB_RESTART_PLAN.md)。

## 预览

Windows PowerShell 5.1+；以下命令从项目根目录执行。
COM4 只是一个示例：使用当前板卡的端口。

```powershell
$preview = & .\tools\restart_usb_port.ps1 -Port COM4
$preview | Format-List
```

没有 `-Apply`，脚本只读取 PnP：不打开 COM，不调用 UAC，
不创建收据且不重启设备。检查 `port`、`name`、`target` 和与所需板卡的连接。
PnP ID 不替代芯片型号/工厂 BASE_MAC。

## 允许的重置

可以从普通 PowerShell/VS Code 终端启动。在 `-Apply` 时，
脚本会自动调用 Windows UAC 窗口：点击“是”。一个隐藏的管理员子 Power Shell 被启动，并且在重启设备前重新验证设备。
如果当前的 PowerShell 已经是管理员，则不会有额外窗口。
预览没有 `-Apply` 不会调用 UAC。从项目根目录示例：

```powershell
$preview = & .\tools\restart_usb_port.ps1 -Port COM4
$preview | Format-List
# 确认 target 和测试台准备就绪后：
& .\tools\restart_usb_port.ps1 -Port COM4 -ExpectedInstanceId $preview.target -Apply
Get-Content -LiteralPath .\usb-restart.jsonl -Tail 2
```

在`-Apply`脚本会追加日志到`usb-restart.jsonl` **项目根目录**，
无论当前终端目录如何。每次操作都会获得两条JSON字符串
带有同一个`operation_id`：STARTED和结果，或者STOP带错误。记录UTC时间、
端口、预期目标以及单独报告的路径；如果成功，则还包括报告的内容。
UAC失败和预检查中的任何错误也会被记录到日志中。如果进程
被中断且只有STARTED存在，结果未知——查看报告而不是盲目重启。
预览日志不会创建或修改。

没有`-ReceiptPath`单独的报告会自动在旁边生成：
`usb-restart-<operation_id>.json`。明确指定的`-ReceiptPath`允许选择其他位置，
但总体日志仍保留在根目录中。它会在尝试重启之前打开；写入错误
或被另一个启动占用的日志将阻止新的操作。父进程在UAC期间记录日志，子进程只记录单独报告。

ReceiptPath必须是现有目录中的新文件。脚本会检查是否可以写入，在重启前，
拒绝覆盖旧的receipt，并重新验证目标在调用之前。路径不依赖于原始WorckBook的位置；`ReceiptPath`从当前PowerShell目录解析。
旧的运行时脚本未更改。

## 用于AI的顺序

1. 阅读[OPERATOR](OPERATOR.md)，在当前任务中明确板卡的角色、端口、COM的所有者以及允许的恢复场景。仅将此脚本添加到项目本身并不授权重启。针对该具体场景已授予的许可继续有效；无需重复确认。
2. 保存原始错误。PnP状态为OK并不能证明UART正常工作。确认没有正在进行的固件写入/ROM 操作，也没有其他所有者正在操作。按常规释放自己的句柄；不要终止其他进程。此脚本不识别COM的所有者且不会验证端口的占用情况。
3. 执行预览，将具体设备与当前连接进行对比。不要从历史记录中使用旧的COM4/InstanceId。不要遍历所有端口、不要使用通配符或重启父级中心。
4. 对于允许的操作，使用精确的ExpectedInstanceId；ReceiptPath可以省略以自动在根目录生成报告。非管理员`-Apply`会通过`Start-Process -Verb RunAs -WindowStyle Hidden -Wait`自动启动子PowerShell。UAC 窗口由操作员确认。PowerShell中的UTF-16 EncodedCommand传递参数字面值，receipt路径提前转换为绝对路径。辅助的ElevatedChild在没有提升令牌的情况下防止再次请求UAC；无需手动传入 ElevatedChild。取消UAC或启动错误会导致停止且不重试；receipt可能不存在。完成之后，父级会检查exit code和receipt中的结果/目标/端口。
5. 在原生调用之前出现的映射/权限/receipt错误意味着停止而不会重启。使用`restart_attempted=true`的STOP表示已请求的操作未成功或不确定：读取receipt但不自动重复操作。非零代码，包括要求重新启动Windows的情况，不会导致计算机自动重启。
6. RESTART_COMMAND_SUCCEEDED仅确认pnputil返回0码。重读映射；缺少`after_status`或存在`after_error`需要新的PnP检查。然后在允许的会话中验证实际数据：Serial 115200，HELP/STS，运行时间和构建标记。`uart_verified=false`保持为脚本本身的诚实结果：它不会打开UART。新固件要求新鲜的工厂身份。
7. 在[ACCEPTANCE](ACCEPTANCE.md)中记录receipt和结果边界。不要将USB重启视为GPIO/WDI/触点验证或固件修正。

## 不使用设备的检查

`python -B tools/project.py test` 包括隔离的 PowerShell 测试，
通过替换 PnP/admin/native 调用。它们不访问 USB 或 COM。
在没有 PowerShell 的系统上，相应的测试会被明确跳过。
实时预览读取 PnP；实时应用是根据上述规则进行的操作。

---

<a id="en"></a>

## English

# USB/COM Restart: Operator and AI

Project script: [tools/restart_usb_port.ps1](../tools/restart_usb_port.ps1).
It is based on the previous `restart_com4.ps1` but does not contain the old InstanceId, port number or workstation path. Parameters select exactly one USB serial adapter of class Ports. Other USB devices, hubs and controllers are not restarted.

This is a PnP device restart through Windows `pnputil /restart-device`.
USB power-off is not guaranteed. ESP32 may reboot; the tester returns relay ON after reboot. The firmware command `RST` separately reboots the ESP32, not the Windows USB adapter.

## Launch from root via shortcut

`restart_usb_port.ps1.lnk` opens Windows PowerShell and runs [restart_usb_interactive.ps1](../tools/restart_usb_interactive.ps1).
Immediately creates or appends **`usb-restart.log` in project root** — even if the user cancels the action or preview ends with an error. The window remains open to read results.

The launcher automatically discovers all USB Serial (Port class, USB InstanceId), displays each port and its exact target. The root shortcut passes `-All -Apply`: it launches a restart of all found; if necessary, confirm UAC. Without `-Apply`, there is a text question `RESTART ALL` when launching; an empty input cancels the action.
Reboots are sequential; after the first error or unconfirmed PnP OK, remaining ports will not be processed. Devices connected after the search in the current launch will not be added. In addition to writing `usb-restart.jsonl` and a separate JSON report as described below when an actual request for reboot is made.
The shortcut does not store port number or USB identity. After moving the Windows project, the Windows shortcut within the project needs to be recreated; the launcher uses paths relative to the project.

In `usb-restart.log` stages, START/DISCOVERED/TARGET/APPLY/RESULT/ERROR/END have time and a common launch_id. RESULT indicates COM, USB target, command code, and PnP status after it.
The full JSON receipt contains `command`, `steps`, stdout pnputil output, and error messages. The log is appended; previous launches remain available.

### Commands for AI and the terminal

Each launcher event appears in the terminal as **`JSON {...}`** and is appended without the prefix to **`usb-restart-events.jsonl` in the project root**, in UTF-8, one object per line. Unlike `usb-restart.jsonl` (Apply only), this file includes discovery, preview, cancellation, results and errors. The human-readable `.log` is retained.

Schema `schema=1`, `type=usb_restart_event`:

| Field | Value |
| --- | --- |
| utc, launch_id, sequence | UTC time, launch ID, event sequence number |
| action, level | START, DISCOVERED, TARGET, APPLY, RESULT, ERROR, END and more; info/error |
| port, target | COM and USB InstanceId, or null outside specific device |
| message | Readable description |
| data | Parameters, selected devices, and command response |
| error | null or message, exception_type, id, category, phase |

In RESULT `data.response` contains the full receipt: return code, Windows stdout,
command, steps, PnP statuses, receipt path, and operation ID. In ERROR responses attach paths,
if there is a new receipt for this request; no response does not mean exit_code=0. An old existing receipt is not considered a new result.
END contains `data.outcome`: COMPLETED, PREVIEW_ONLY, CANCELLED or ERROR,
as well as `completed_ports`. In case of process interruption END may be missing — the result
needs to be verified rather than repeating the command. Even COMPLETED does not mean UART check.

The machine log opens before operations and has one writer for the entire launch.
If unable to open the log, a JSON error is output to the terminal; USB does not change.
Text messages from PowerShell outside of the JSON prefix do not need to be parsed as events.

A ready offline reader does not interact with devices. By default, it finds the log in the project root;
it outputs JSONL and non-zero code if JSON is damaged or unread:
```powershell
python -B tools/read_usb_restart_events.py --last-launch
python -B tools/read_usb_restart_events.py --last-launch --errors
python -B tools/read_usb_restart_events.py --launch-id <id>
# View new events directly from the file:
Get-Content .\usb-restart-events.jsonl -Tail 10 -Wait
```

First, check the reader exit code. An empty output from `--errors` only indicates
the absence of ERROR among saved events; success is confirmed by RESULT and END.

```powershell
# Discovery only; does not restart anything:
.\tools\restart_usb_port.ps1 -ListPorts
# Preview all discovered devices and write usb-restart.log:
.\tools\restart_usb_interactive.ps1 -All -PreviewOnly
# Authorized restart of all discovered devices without a text prompt (UAC remains):
.\tools\restart_usb_interactive.ps1 -All -Apply
# Authorized restart of the selected port only:
.\tools\restart_usb_interactive.ps1 -Port COM4 -Apply
# View the latest entries:
Get-Content .\usb-restart.log -Tail 100
```

Before Apply, follow the COM ownership rules in OPERATOR and ensure no firmware upload is in progress.
The automatic detection of USB Serial does not determine the role of the board and does not check if COM is occupied.
Plan and results: [USB_RESTART_PLAN](../USB_RESTART_PLAN.md).

## Preview

Windows PowerShell 5.1+; commands below are executed from the project root directory.
COM4 is just an example: use the current port of the required board.

```powershell
$preview = & .\tools\restart_usb_port.ps1 -Port COM4
$preview | Format-List
```

Without `-Apply`, the script only reads PnP: does not open COM, does not call UAC,
does not create a receipt and does not restart devices. Check `port`, `name`, `target` and connection with required board.
A PnP ID does not replace chip model/factory BASE_MAC.

## Allowed Restart

Can be launched from regular PowerShell/VS Code terminal. When `-Apply`,
the script itself calls the Windows UAC window: click 'Yes'. A hidden administrative child Power Shell is started, and re-verifies the device before restarting it.
If the current PowerShell is already administrative, there will not be an additional window.
Preview without `-Apply` does not call UAC. Example from project root:

```powershell
$preview = & .\tools\restart_usb_port.ps1 -Port COM4
$preview | Format-List
# After checking target and bench readiness:
& .\tools\restart_usb_port.ps1 -Port COM4 -ExpectedInstanceId $preview.target -Apply
Get-Content -LiteralPath .\usb-restart.jsonl -Tail 2
```

When `-Apply`, the script appends logs to `usb-restart.jsonl` **in the project root directory**,
regardless of the current terminal directory. Each operation receives two JSON strings
with one `operation_id`: STARTED and result or STOP with an error. UTC time is recorded along with
the port, expected target, and path to a separate report; if successful, it also includes the content of the report.
UAC failure and any errors in pre-checks are also logged. If the process is interrupted and only STARTED remains,
the result is unknown—read the report rather than blindly restarting. Preview does not create or modify the log.

Without `-ReceiptPath`, a separate report will be automatically generated nearby:
`usb-restart-<operation_id>.json`. An explicit `-ReceiptPath` allows choosing another location,
but the overall log remains in the root directory. It opens before attempting to restart; write errors or logs occupied by another start prevent new operations. The parent process logs during UAC, while the child process only logs the separate report.

ReceiptPath must be a new file within an existing directory. The script checks for write permission before restarting,
denies overwriting the old receipt and re-verifies the target before calling. Paths are independent of the original WorckBook location; `ReceiptPath` is resolved from the current PowerShell directory.
The old runtime script has not been changed.

## Order for AI

1. Read [OPERATOR](OPERATOR.md), clarify the role of the board, port, COM owner and allowed recovery scenario in the current task. Adding this script to a project alone does not authorize a restart. An existing permission for the exact scenario remains valid; do not request it again.
2. Save the original error. PnP status OK does not prove working UART. Check absence of firmware/ROM operation and active work by another owner. Release own handles normally; do not terminate other processes. The script does not identify COM owner or check port occupancy.
3. Perform preview, compare specific device with current connection. Do not use old COM4/InstanceId from history. Do not iterate all ports, do not use wildcard or restart parent hub.
4. For permitted action, use exact ExpectedInstanceId; ReceiptPath can be omitted for automatic report at root. Non-administrative `-Apply` automatically launches child PowerShell via `Start-Process -Verb RunAs -WindowStyle Hidden -Wait`. The operator confirms the UAC prompt. Arguments are passed as literal PowerShell UTF-16 EncodedCommand, receipt path becomes absolute in advance. Auxiliary ElevatedChild prevents repeated UAC request without elevated token; do not pass ElevatedChild manually. Cancellation of UAC or launch error stops without retry; receipt may be absent. After completion, parent checks exit code and result/target/port in receipt.
5. Mapping/permissions/receipt errors before native call mean stop without restart. STOP with `restart_attempted=true` means undefined or unsuccessful result already requested action: read receipt but do not automatically repeat operation. Non-zero code including requirement for Windows reboot does not cause computer automatic reboot.
6. RESTART_COMMAND_SUCCEEDED confirms only code 0 from pnputil. Re-read mapping; absence of `after_status` or presence of `after_error` requires new PnP check. Then in permitted session, verify actual data: Serial 115200, HELP/STS, uptime and build marker. `uart_verified=false` remains honest result of script itself: it does not open UART. New firmware requires fresh factory identity.
7. Record receipt and result boundaries in [ACCEPTANCE](ACCEPTANCE.md). Do not consider USB restart as GPIO/WDI/contact validation or firmware correction.

## Checks without equipment

`python -B tools/project.py test` includes isolated PowerShell tests,
with substitution of PnP/admin/native calls. They do not access USB or COM.
On a system without PowerShell, the corresponding test is explicitly skipped.
Live preview reads PnP; live apply is a separate operation according to rules above.
