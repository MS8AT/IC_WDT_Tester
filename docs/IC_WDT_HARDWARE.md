# IN1232N / DS1232LP — IC WDT

RU: Описание, схема и настройка: русский → 中文（简体）→ English, каждый перевод с новой строки.  
中文：说明、电路及设置按俄语 → 简体中文 → 英语排列，每种语言单独一行。  
EN: Description, circuit and settings use Russian → Simplified Chinese → English, one language per line.

## 1. Назначение / 用途 / Purpose

RU: IN1232N производства «ИНТЕГРАЛ» — отдельная микросхема контроля питания со сторожевым таймером. Она вызывает сброс при понижении питания, прекращении импульсов ST или нажатии кнопки PBRST. Тестер ESP32 управляет реле и наблюдает EN; импульсы ST должно выдавать проверяемое устройство.  
中文：INTEGRAL 的 IN1232N 是带看门狗定时器的独立电源监控芯片。供电下降、ST 脉冲停止或按下 PBRST 按钮时会触发复位。ESP32 测试器控制继电器并监测 EN；ST 喂狗脉冲由被测设备产生。  
EN: INTEGRAL IN1232N is a separate supply supervisor with a watchdog. It asserts reset on undervoltage, missing ST pulses or a PBRST button press. The ESP32 tester controls the relay and observes EN; the device under test must generate ST pulses.

RU: Зарубежный вариант здесь — Dallas/Maxim DS1232LP. В документации ADI 111899 маркировка восьмивыводного корпуса указана как DS1232L. Сверяйте полное обозначение и корпус: схема ниже только для 8 выводов. Каталог «ИНТЕГРАЛ» 2005 относит IN1232N к корпусу 2101.8-А и указывает прототип DS1232; это не подтверждение полной взаимозаменяемости с любым DS1232L.  
中文：本文比较的国外型号是 Dallas/Maxim DS1232LP。ADI 的 111899 版资料将八引脚封装标记列为 DS1232L。必须核对完整型号和封装；下图仅适用于八引脚器件。INTEGRAL 2005 年目录将 IN1232N 列为 2101.8-А 封装，并以 DS1232 为参考型号；这不代表它与所有标为 DS1232L 的器件完全兼容。  
EN: The foreign part discussed here is Dallas/Maxim DS1232LP. ADI revision 111899 lists DS1232L as its eight-pin package marking. Check the full part number and package; this circuit covers eight pins only. INTEGRAL's 2005 catalog lists IN1232N in package 2101.8-А with DS1232 as its prototype; this does not establish universal drop-in compatibility.

RU: Источники и сохранённые PDF: [реестр документации](datasheets/README.md). Значения ниже относятся к указанным там редакциям и условиям таблиц, а не к измерению установленной микросхемы. В старом IN1232 есть опечатка: рисунок второго корпуса имеет 16 выводов, но подпись «SO-14». Эту картинку для разводки не использовать.  
中文：来源及已保存的 PDF 见[资料目录](datasheets/README.md)。下列数值来自指定版本及其表格条件，并非已安装芯片的实测结果。旧版 IN1232 资料的第二个封装图画了 16 个引脚，却标成“SO-14”；不要据此绘制 PCB。  
EN: See the [document register](datasheets/README.md) for sources and saved PDFs. Values below belong to those revisions and table conditions, not measurements of the installed chip. The old IN1232 document draws a 16-pin second package but labels it “SO-14”; do not use that drawing for a PCB footprint.

## 2. Схема / 电路 / Circuit

RU: Это проект подключения к ESP32 с EN, активным LOW. Фактический монтаж не проверен. VCC микросхемы подключается к контролируемой линии +5 В; земля общая. Номера ниже — физические выводы микросхемы, не GPIO ESP32.  
中文：这是用于 EN 低电平复位的 ESP32 的接线方案，实际接线尚未验证。监控芯片 VCC 接被监测的 +5 V 电源，各部分共地。下列编号是芯片物理引脚，不是 ESP32 GPIO 编号。  
EN: This is a proposed circuit for an ESP32 with active-low EN; actual wiring is unverified. Connect the supervisor VCC to the monitored +5 V rail and use a common ground. Numbers below are IC pins, not ESP32 GPIO numbers.

```text
                     U1: IN1232N / DS1232LP, DIP-8
                            top view / notch
                           +------u------+
 GND ---[SW1 button]--------|1 PBRST_N VCC 8|---- +5V_MON
 J1: GND / OPEN / +5V_MON --|2 TD     ST_N 7|<--- TARGET_HEARTBEAT
 J2: GND / +5V_MON ---------|3 TOL   RST_N 6|---- WDT_RESET_N
 GND ----------------------|4 GND     RST 5|---- NC
                           +-------------+

 +5V_MON ----+---- U1.8               TARGET_3V3
             |                            |
          C1 100nF                     R1 10k (*)
             |                            |
 GND --------+---- U1.4                    +------ TARGET_EN
                                          |
 U1.6 WDT_RESET_N ---[K1 dry contact]-------+
                                          +------ TESTER_GPIO25 (LOW / Hi-Z)
                                          +------ TESTER_GPIO33 (input)

 TESTER_GPIO13 ---> [3.3V-compatible relay driver/module] ---> K1 coil
 TARGET_GND ------- TESTER_GND ------- U1.4 ------- relay control GND
```

RU: `_N` означает активный LOW; NC здесь означает «не подключать». K1 — сухой контакт в пути сброса, замкнутый при логическом ON тестера. Конкретные NO/NC/COM выбирают по реле и проверяют прозвонкой. Катушку нельзя питать от GPIO13; нужен драйвер или готовый модуль.  
中文：`_N` 表示低电平有效；此处 NC 表示不连接。K1 是复位路径中的无源触点，测试器逻辑 ON 时应闭合。具体 NO/NC/COM 接法需按继电器型号确定并测量确认。线圈不能直接由 GPIO13 驱动，必须使用驱动电路或继电器模块。  
EN: `_N` means active low; NC here means leave unconnected. K1 is a dry contact in the reset path, closed when the tester commands ON. Select and verify the actual NO/NC/COM terminals for your relay. GPIO13 needs a relay driver/module; it must not power the coil directly.

RU: (*) R1 = 10 кОм и C1 = 100 нФ — предлагаемые значения схемы, не регулирующие порог/таймаут. R1 может уже быть на целевой плате; проверить её EN-цепь и RC. Подтяжка EN только к 3,3 В. Вывод 6 — открытый сток; не соединять его с выводом 5. На готовом WDT-модуле проверить отсутствие подтяжки RESET к 5 В.  
中文：(*) R1 = 10 kΩ、C1 = 100 nF 是电路建议值，不用于调节阈值或超时。目标板可能已有 R1，需核对 EN 电路及 RC。EN 只能上拉至 3.3 V。引脚 6 为开漏输出，不能与引脚 5 相连。使用成品 WDT 模块时，必须确认 RESET 没有被上拉至 5 V。  
EN: (*) R1 = 10 kΩ and C1 = 100 nF are proposed circuit values, not threshold/timeout controls. The target board may already provide R1; check its EN and RC network. Pull EN up to 3.3 V only. Pin 6 is open drain; never tie it to pin 5. Check that a ready-made WDT module does not pull RESET up to 5 V.

RU: PBRST внутри подтянут к VCC = 5 В: кнопку подключают к GND, а GPIO ESP32 напрямую туда не подключают. ST допускает HIGH от 2,0 В, поэтому сигнал 3,3 В подходит при штатном питании. При независимом отключении питания плат нужно отдельно проверить токи через входы или добавить согласование с защитой от обратного питания. Работа RESET при VCC ниже 2 В этим описанием не гарантируется.  
中文：PBRST 内部上拉至 VCC = 5 V，按钮接 GND，不要把 ESP32 GPIO 直接接到该输入。ST 的高电平门限为 2.0 V，因此正常供电时可接受 3.3 V 信号。若各板可独立断电，必须另行检查输入电流或使用防反向供电的电平转换。本文不保证 VCC 低于 2 V 时 RESET 的行为。  
EN: PBRST has an internal pull-up to VCC = 5 V: connect its button to GND, not directly to an ESP32 GPIO. ST accepts HIGH from 2.0 V, so a 3.3 V signal works under normal powered conditions. Independently powered boards require input-current checks or translation with back-power protection. This description does not guarantee RESET behavior below 2 V VCC.

RU: Размыкание K1 блокирует весь выход микросхемы — и watchdog, и сброс по питанию. Это режим испытательного стенда. Для постоянной защиты путь сброса должен оставаться подключённым. GPIO25 находится на стороне EN: только LOW → INPUT без активного HIGH.  
中文：断开 K1 会阻断芯片的全部复位输出，包括看门狗复位和欠压复位；这是测试台模式。持续保护时复位路径必须保持连接。GPIO25 接在 EN 一侧，只执行 LOW → INPUT，不主动输出 HIGH。  
EN: Opening K1 masks the entire IC reset output, including watchdog and undervoltage resets; this is a bench mode. Continuous protection requires the reset path to remain connected. GPIO25 connects on the EN side and uses LOW → INPUT, never actively driving HIGH.

## 3. Порог питания: TOL / 电压阈值：TOL / Supply threshold: TOL

RU: Для сброса при более низком напряжении соединить TOL (вывод 3) с VCC, а не GND. Менять соединения при выключенном питании. Таблица одинакова в сохранённых электрических характеристиках IN1232 и DS1232LP.  
中文：若希望在更低电压时才复位，将 TOL（引脚 3）接 VCC，而不是 GND。必须断电后更改接线。已保存的 IN1232 与 DS1232LP 电气参数表给出相同的以下数值。  
EN: To reset at a lower supply voltage, connect TOL (pin 3) to VCC instead of GND. Change wiring with power off. The saved IN1232 and DS1232LP electrical tables give the same values below.

| TOL | Режим / 模式 / Mode | MIN V | TYP V | MAX V |
| --- | --- | ---: | ---: | ---: |
| GND | 5% | 4.50 | 4.62 | 4.74 |
| VCC | 10% | 4.25 | 4.37 | 4.49 |

RU: «5% / 4,75 В» и «10% / 4,5 В» — названия диапазонов в описании; реальный порог имеет разброс из таблицы. TOL нельзя оставлять неподключённым. Это два выбора, а не плавная регулировка. TD порог напряжения не меняет.  
中文：“5% / 4.75 V”和“10% / 4.5 V”是资料中的范围名称，实际触发阈值有表中所列偏差。TOL 不能悬空。这是两档选择，并非连续可调。TD 不改变电压阈值。  
EN: “5% / 4.75 V” and “10% / 4.5 V” are range labels in the description; the actual trip point varies as shown. Do not leave TOL floating. There are two settings, not continuous adjustment. TD does not change the voltage threshold.

RU: Номинальное питание U1 — 5 В, рабочий диапазон 4,5–5,5 В. U1 не предназначена для питания от 3,3 В. Если нужно отслеживать падение именно линии ESP32 3,3 В, например до 3,0 В, требуется супервизор с подходящим порогом или отдельный компаратор. Делитель на VCC не является корректной заменой. Контроль 5 В перед стабилизатором не обнаруживает все неисправности выхода 3,3 В.  
中文：U1 标称供电为 5 V，工作范围为 4.5–5.5 V，不适合由 3.3 V 供电。如果需要检测 ESP32 的 3.3 V 电源是否降到例如 3.0 V，应选用相应阈值的监控器或独立比较器。在 VCC 上加分压器不是正确替代方案。监测稳压器前的 5 V 并不能发现所有 3.3 V 输出故障。  
EN: U1 uses nominal 5 V power, with a 4.5–5.5 V operating range; it is not a 3.3 V-powered supervisor. To monitor the ESP32 3.3 V rail down to, for example, 3.0 V, use a supervisor with the appropriate threshold or a separate comparator. A divider on VCC is not a valid substitute. Monitoring 5 V upstream of the regulator cannot detect every 3.3 V output fault.

## 4. Время watchdog: TD / 看门狗超时：TD / Watchdog timeout: TD

RU: Вывод TD (2) задаёт время от последнего спада HIGH → LOW на ST (7) до watchdog-сброса. На старте отсчёт начинается после отпускания RESET микросхемой. Таблица применима к обоим сохранённым даташитам; OPEN означает оставить TD неподключённым.  
中文：TD（引脚 2）设置从 ST（引脚 7）最后一个 HIGH → LOW 下降沿到看门狗复位的超时时间。上电时，芯片释放 RESET 后开始计时。该表适用于两个已保存的数据手册；OPEN 表示 TD 悬空。  
EN: TD (pin 2) selects the watchdog interval from the last HIGH → LOW edge on ST (pin 7) to reset. At startup, timing starts when the IC releases RESET. The table applies to both saved datasheets; OPEN means leave TD unconnected.

| TD | MIN ms | TYP ms | MAX ms |
| --- | ---: | ---: | ---: |
| GND | 62.5 | 150 | 250 |
| OPEN | 250 | 600 | 1000 |
| VCC | 500 | 1200 | 2000 |

RU: Для надёжного обслуживания интервал между спадами ST выбирают меньше MIN с запасом на задержки программы, а не меньше TYP. Постоянный LOW или HIGH не обслуживает watchdog. Ширина LOW-импульса ST — не менее 20 нс; практический импульс может быть существенно длиннее. Время загрузки устройства также должно укладываться в выбранный режим.  
中文：可靠喂狗时，相邻 ST 下降沿的间隔必须小于 MIN，并为程序延迟留出余量，不能按 TYP 设计。持续 LOW 或 HIGH 都不能喂狗。ST 低电平脉冲宽度至少为 20 ns，实际脉冲可明显更长。设备启动时间也必须满足所选模式。  
EN: For reliable feeding, keep ST falling-edge intervals below MIN with software-latency margin, not merely below TYP. Holding ST constantly LOW or HIGH does not feed the watchdog. ST LOW pulse width must be at least 20 ns; practical pulses may be much longer. Device startup must also fit the selected mode.

RU: Эти микросхемы не дают произвольный таймаут 5/10/30 секунд изменением резистора или команды Serial. Для другого диапазона нужна другая схема/микросхема. Генератор ST должен зависеть от исправной работы проверяемой программы; независимое мигание таймера может скрывать зависание.  
中文：这些芯片不能通过更换电阻或发送串口命令获得任意的 5/10/30 秒超时；其他范围需要不同电路或芯片。ST 应由被测程序的正常运行驱动，独立定时器持续产生脉冲可能掩盖程序死锁。  
EN: These chips cannot provide arbitrary 5/10/30-second timeouts through a resistor change or Serial command; other ranges need a different circuit or IC. ST should depend on healthy execution of the monitored program; an independent timer that keeps toggling can hide a software hang.

## 5. Три разных времени / 三种不同时间 / Three separate times

| Параметр / 参数 / Parameter | IN1232 | DS1232LP |
| --- | --- | --- |
| Watchdog TD, TYP | 150 / 600 / 1200 ms | 150 / 600 / 1200 ms |
| RESET active, MIN / TYP / MAX | 250 / 610 / 1000 ms | 250 / 610 / 1000 ms |
| VCC fail → RESET, TYP / MAX | 100 / 175 µs | 50 / 175 µs |

RU: При плохом питании сброс удерживается активным; после восстановления добавляется выдержка 250–1000 мс при условиях даташита. TOL выбирает порог, TD — watchdog-интервал; они не регулируют ширину RESET или задержку обнаружения просадки. Команда тестера RESET отдельно держит GPIO25 LOW номинально 1000 мс; RESET100 — 100 мс. Эти команды не программируют U1.  
中文：欠压期间复位保持有效；电源恢复后，在数据手册规定条件下继续保持 250–1000 ms。TOL 选择阈值，TD 选择看门狗间隔，二者都不调节 RESET 脉宽或欠压检测延迟。测试器的 RESET 命令独立地将 GPIO25 拉低标称 1000 ms，RESET100 为 100 ms；它们不对 U1 编程。  
EN: Reset stays asserted during undervoltage; after recovery, it remains active for 250–1000 ms under datasheet conditions. TOL selects the threshold and TD selects the watchdog interval; neither adjusts RESET width or brownout detection delay. The tester RESET command separately pulls GPIO25 LOW for nominally 1000 ms; RESET100 uses 100 ms. These commands do not program U1.

## 6. Проверка / 检查 / Verification

RU: Ниже план измерений, а не уже выполненный тест. Изменение GPIO33 в JSON показывает уровень EN; поле `wdt_triggered: null` не позволяет автоматически назвать причиной watchdog.  
中文：以下是测量计划，并非已完成测试。JSON 中的 GPIO33 变化表示 EN 电平；`wdt_triggered: null` 不能被自动解释为看门狗已触发。  
EN: This is a measurement plan, not a completed test. GPIO33 JSON records the EN level; `wdt_triggered: null` must not be interpreted as a confirmed watchdog cause.

- [ ] RU: Без питания сверить маркировку, DIP-8, выводы 5/6, землю, TOL/TD и отсутствие 5 В на EN.  
  中文：断电核对型号、DIP-8、引脚 5/6、地线、TOL/TD，并确认 EN 无 5 V 上拉。  
  EN: With power off, verify marking, DIP-8, pins 5/6, ground, TOL/TD and absence of a 5 V EN pull-up.
- [ ] RU: При исправном питании измерить ST и EN; убедиться, что импульсы приходят раньше MIN выбранного режима.  
  中文：正常供电时测量 ST 和 EN，确认喂狗间隔小于所选模式的 MIN。  
  EN: With healthy power, measure ST and EN and confirm feeding intervals are below the selected MIN.
- [ ] RU: Остановить ST в разрешённом опыте; осциллографом измерить задержку сброса и длительность LOW.  
  中文：在获准的测试中停止 ST，用示波器测量复位延迟和 LOW 持续时间。  
  EN: Stop ST in an authorized test; measure reset latency and LOW duration with an oscilloscope.
- [ ] RU: Для проверки просадки продолжать ST, плавно снизить контролируемые 5 В лабораторным источником, записать реальный порог и отпускание при восстановлении. Исключить подпитку через USB и другие источники.  
  中文：欠压测试时保持 ST 脉冲，用实验室电源逐渐降低被监测的 5 V，记录实际阈值及恢复后的释放时间，排除 USB 和其他电源的反向供电。  
  EN: For undervoltage testing, maintain ST pulses, gradually lower the monitored 5 V using a bench supply, and record the actual threshold and release after recovery. Exclude back-power from USB and other supplies.
- [ ] RU: Сохранить TOL, TD, маркировку U1, схему, осциллограммы и JSON отдельно от результата сборки прошивки.  
  中文：将 TOL、TD、U1 型号、接线、波形和 JSON 与固件编译结果分别保存。  
  EN: Record TOL, TD, U1 marking, wiring, waveforms and JSON separately from firmware build results.

RU: Связанные документы: [подключение тестера](WIRING.md), [команды](COMMANDS.md), [JSON](TELEMETRY.md).  
中文：相关文档：[测试器接线](WIRING.md)、[命令](COMMANDS.md)、[JSON](TELEMETRY.md)。  
EN: Related documents: [tester wiring](WIRING.md), [commands](COMMANDS.md), [JSON](TELEMETRY.md).
