[Русский](#ru) · [中文](#zh) · [English](#en)

<a id="ru"></a>

## Русский

# Если что-то не работает

| Симптом | Что проверить и сделать |
| --- | --- |
| COM: Access denied | Закрыть свой Serial Monitor/терминал, дождаться окончания upload. Не завершать чужой процесс и не открывать второй UART |
| COM исчез или сменил номер | Проверить USB/PnP. Заново сопоставить factory BASE_MAC до записи; номер порта не идентифицирует плату |
| MD5 mismatch при записи | Запись не принята. Сохранить лог, проверить питание/кабель/выбор напряжения flash и проводку GPIO12. Не повторять загрузку вслепую |
| NVS Error 261 / Wi-Fi deinit 0x3001 | Сохранить полный boot log. Проверить доступность flash и таблицу разделов; не стирать NVS как первый шаг |
| Нечитаемые символы UART | Проверить 115200/8N1, UTF-8, питание, reset и единственного владельца порта |
| GPIO2 быстро, затем медленно мигает | Попытка подключения и ожидание; проверить secrets.h и доступность сети. Успешная связь даёт постоянный свет |
| LED показывает обратное поведение | Проверить полярность LED/модуля; код рассчитан на HIGH = включён |
| Wi-Fi есть, время null | NTP ещё не синхронизирован; проверить доступ к NTP. Использовать uptime для анализа |
| GPIO33 постоянно HIGH | Проверить реальное соединение: INPUT_PULLUP может удерживать HIGH даже с неподключённым проводом |
| Импульс есть, в истории пусто | Фильтр 40 мс может подавить короткий импульс. Проверить сигнал измерителем |
| Повторяются одинаковые номера событий | HISTORY — повтор: gpio_history/replay=true. Считать новые gpio_change либо удалять дубли внутри одной boot-сессии |
| GPIO25 читается HIGH после сброса | Нормально при внешней подтяжке и OE=0: тестер освободил линию, не выдаёт HIGH |
| SDK preflight FAIL | Сверить точный локальный SDK; не устанавливать случайную новую версию вместо закреплённой |
| dependency changed | Проверить причину изменения и обновить хеш только для согласованной source revision |

USB restart не гарантирует снятия питания и не завершает захватившее COM приложение.
Windows-инструмент пишет `usb-restart.log`, `usb-restart.jsonl`,
`usb-restart-events.jsonl` и отдельные receipts в корне. Для чтения последнего запуска:

```powershell
python -B tools/read_usb_restart_events.py --last-launch
```

Перед Apply закрыть монитор и убедиться, что прошивка не идёт.
[Подробности USB recovery](USB_COM_RECOVERY.md).

В отчёте об ошибке укажите модель платы, версию исходников/SHA образа,
команду, ожидаемый/фактический результат и обезличенный фрагмент журнала.
Не прикладывайте secrets.h, пароли, полный локальный runtime или firmware.bin
с рабочими Wi-Fi-настройками.

---

<a id="zh"></a>

## 中文

# 如果某些功能无法正常工作

| 症状 | 检查和操作 |
| --- | --- |
| COM: 访问被拒绝 | 关闭您的串行监视器/终端，等待上传完成。不要结束其他人的进程或打开第二个 UART |
| COM 缺失或更改了编号 | 检查 USB/PnP。写入之前重新核对出厂 BASE_MAC；端口号不能标识板卡 |
| 写入时 MD5 不一致 | 写入未被接受。保存日志，检查电源/电缆/闪存电压选择和 GPIO12 连接。不要盲目重复上传 |
| NVS 错误 261 / Wi-Fi deinit 0x3001 | 保存完整的启动日志。检查闪存的可访问性和分区表；不要首先清除 NVS |
| UART 显示不可读字符 | 检查 115200/8N1, UTF-8, 电源, reset 和单一端口所有者 |
| GPIO2 快速闪烁，然后缓慢闪烁 | 尝试连接并等待；检查 secrets.h 和网络可用性。成功连接将显示持续的光亮 |
| LED 显示相反的行为 | 检查 LED/模块极性；代码假设 HIGH = 开启 |
| Wi-Fi 存在，时间为空 | NTP 未同步；检查 NTP 访问。使用 uptime 进行分析 |
| GPIO33 始终为 HIGH | 检查实际连接：INPUT_PULLUP 可能即使没有连接导线也会保持 HIGH |
| 脉冲存在，历史记录为空 | 40ms 的滤波器可能抑制短暂脉冲。使用测量仪检查信号 |
| 相同事件编号重复出现 | HISTORY — 重播: gpio_history/replay=true. 计算新的 gpio_change 或在单次启动会话内删除重复项 |
| GPIO25 在复位后读取为 HIGH | 外部上拉和 OE=0 正常：测试仪释放了线路，不输出 HIGH |
| SDK 预检失败 | 比较精确的本地 SDK；不要用随机的新版本替换固定版本 |
| 依赖项更改 | 检查更改原因并仅针对已商定的源代码版本更新哈希 |

USB重启不能保证断电，也不能结束占用COM的应用程序。
Windows工具写入`usb-restart.log`、`usb-restart.jsonl`、
`usb-restart-events.jsonl`，并单独在根目录下生成收据。读取最近一次工具运行：

```powershell
python -B tools/read_usb_restart_events.py --last-launch
```

在应用之前，关闭串口监视器并确保没有正在进行的固件写入。
[USB恢复详细信息](USB_COM_RECOVERY.md)。

在错误报告中，请提供电路板型号、源代码版本/固件镜像SHA、
命令、预期结果和实际结果以及匿名的日志片段。不要附上secrets.h文件，密码，完整的本地运行时或带有工作Wi-Fi设置的firmware.bin。

---

<a id="en"></a>

## English

# If something is not working

| Symptom | What to check and do |
| --- | --- |
| COM: Access denied | Close your Serial Monitor/terminal, wait for upload completion. Do not terminate another's process or open a second UART |
| COM disappeared or changed number | Check USB/PnP. Re-match factory BASE_MAC before writing; port number does not identify the board |
| MD5 mismatch during write | Write is not accepted. Save log, check power/cable/voltage selection for flash and GPIO12 wiring. Do not blindly repeat upload |
| NVS Error 261 / Wi-Fi deinit 0x3001 | Save full boot log. Check access to flash and partition table; do not first erase NVS |
| UART displays unreadable characters | Check 115200/8N1, UTF-8, power, reset and single port owner |
| GPIO2 rapidly flashes then slowly | Attempt connection and wait; check secrets.h and network availability. Successful connection will show continuous light |
| LED shows opposite behavior | Check LED/module polarity; code assumes HIGH = on |
| Wi-Fi present, time null | NTP not yet synchronized; check NTP access. Use uptime for analysis |
| GPIO33 constantly HIGH | Check actual connection: INPUT_PULLUP may hold HIGH even with unconnected wire |
| Pulse exists, history empty | 40ms filter may suppress short pulse. Use meter to check signal |
| Same event numbers repeat | HISTORY — replay: gpio_history/replay=true. Count new gpio_change or remove duplicates within one boot session |
| GPIO25 reads HIGH after reset | Normal with external pullup and OE=0: tester released line, does not output HIGH |
| SDK preflight FAIL | Verify exact local SDK; do not install random new version instead of fixed |
| dependency changed | Check reason for change and update hash only for an agreed source revision |

USB restart does not guarantee power disconnection and does not terminate the COM application that has captured it.
The Windows tool writes `usb-restart.log`, `usb-restart.jsonl`,
`usb-restart-events.jsonl` and generates separate receipts in the root directory. To read the latest run:

```powershell
python -B tools/read_usb_restart_events.py --last-launch
```

Before applying, close the monitor and ensure that no firmware upload is in progress.
[USB recovery details](USB_COM_RECOVERY.md).

In the error report, please provide the board model, source revision/image SHA,
command, expected result and actual result as well as an anonymized log snippet. Do not attach secrets.h file, passwords, full local runtime or firmware.bin with working Wi-Fi settings.
