"""Explicit tester-only app flash after ROM factory identity and layout checks.

Requires an exclusive, authorized tester session. No port scan, retries or main IO.
Boot/table must match the built images; only app offset 0x10000 is written.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha(data): return hashlib.sha256(data).hexdigest()


def disable_write_retry(esp):
    # Native write_flash catches SerialException and can reconnect silently.
    # A class setting survives esptool.main creating another stub instance.
    type(esp).WRITE_FLASH_ATTEMPTS = 1


def validate_rom(description, mac, expected):
    exact = expected['chip_model'] + ' (revision ' + expected['chip_revision'] + ')'
    if description != exact or mac.lower() != expected['base_mac'].lower():
        raise RuntimeError('ROM chip/base MAC mismatch; no flash write')


def validate_flash_voltage(strap, efuse, rtc):
    # Read-only guard for this ESP32 tester's normal 3.3V configuration.
    # GPIO12 is also the external reset output: the attached EN pull-up can
    # select 1.8V during tester ROM entry, before main.cpp configures outputs.
    if rtc & (1 << 22):
        raise RuntimeError('Unexpected RTC flash-voltage override; no flash write')
    if efuse & (1 << 16):
        selected_33v = (efuse & ((1 << 14) | (1 << 15))) == ((1 << 14) | (1 << 15))
    else:
        selected_33v = not (strap & (1 << 5))
    if not selected_33v:
        raise RuntimeError('Flash voltage is not selected as 3.3V; check tester GPIO12 wiring before flash')
    return '3.3V'


def validate_backup(data, images):
    if len(data) != 4194304:
        raise RuntimeError('Incomplete 4 MiB backup')
    validate_layout({name: data[offset:offset+len(images[name])]
                     for name, offset in [('bootloader.bin', 0x1000), ('partitions.bin', 0x8000)]}, images)


def validate_layout(installed, images):
    for name in ('bootloader.bin', 'partitions.bin'):
        payload = images[name]
        if installed[name] != payload:
            raise RuntimeError('Installed ' + name + ' differs; no app write')
    if not 0 < len(images['firmware.bin']) <= 0x140000:
        raise RuntimeError('App exceeds confirmed partition')


def read_layout(read_flash, images):
    return {name: read_flash(offset, len(images[name]))
            for name, offset in [('bootloader.bin', 0x1000), ('partitions.bin', 0x8000)]}


def backup_setting(path):
    value = json.loads(path.read_text(encoding='utf-8'))['full_backup_before_flash']
    if type(value) is not bool:
        raise ValueError('full_backup_before_flash must be a boolean')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--backup', action='store_true', help='Explicitly request a full backup for this run')
    args = parser.parse_args()
    full_backup = args.backup or backup_setting(ROOT/'flash-settings.json')
    expected = json.loads((ROOT/'device-profile.json').read_text())['tester']
    build = ROOT/'.pio/build/ic_wdt_tester'
    images = {name: (build/name).read_bytes() for name in ['firmware.bin', 'bootloader.bin', 'partitions.bin']}
    artifact = {k: {'bytes': len(v), 'sha256': sha(v)} for k,v in images.items()}
    if not args.execute:
        print(json.dumps({'mode': 'offline', 'expected': expected, 'artifact': artifact, 'full_backup': full_backup}))
        return 0
    args.output.mkdir(parents=True, exist_ok=False)
    for name, data in images.items(): (args.output/name).write_bytes(data)
    receipt = {'utc': datetime.now(timezone.utc).isoformat(), 'port': args.port,
               'expected': expected, 'artifact': artifact, 'write': 'NOT_RUN', 'verify': 'NOT_RUN',
               'full_backup_enabled': full_backup}
    tool = ROOT/'.sdk/packages/tool-esptoolpy'
    sys.path.insert(0, str(tool/'_contrib'))
    sys.path.insert(0, str(tool))
    import esptool
    import serial
    if esptool.__version__ != '4.11.0': raise RuntimeError('Unexpected esptool version')
    port = serial.Serial(port=None, baudrate=115200, timeout=1, write_timeout=3)
    try:
        port.dtr = False; port.rts = False; port.port = args.port; port.open()
        esp = esptool.detect_chip(port, connect_attempts=1)
        description = esp.get_chip_description()
        mac = ':'.join('%02x' % value for value in esp.read_mac('BASE_MAC'))
        receipt['actual'] = {'chip_description': description, 'base_mac': mac, 'mac_type': 'BASE_MAC'}
        validate_rom(description, mac, expected)
        print(json.dumps({'factory_identity': receipt['actual']}), flush=True)
        regs = {name: esp.read_reg(getattr(esp, name)) for name in
                ('GPIO_STRAP_REG', 'EFUSE_VDD_SPI_REG', 'RTC_CNTL_SDIO_CONF_REG')}
        receipt['voltage_registers'] = {key: hex(value) for key, value in regs.items()}
        receipt['flash_voltage_selection'] = validate_flash_voltage(*regs.values())
        stub = esp.run_stub()
        disable_write_retry(stub)
        # The stub is already resident; prevent main() uploading it a second time.
        common = ['--chip', 'esp32', '--port', args.port, '--baud', '115200', '--no-stub', '--before', 'no_reset', '--after', 'no_reset_stub']
        if full_backup:
            backup = args.output/'before-4MiB.bin'
            esptool.main(common+['read_flash', '--no-progress', '0', '0x400000', str(backup)], esp=stub)
            data = backup.read_bytes()
            validate_backup(data, images)
            receipt['backup'] = {'bytes': len(data), 'sha256': sha(data)}
        else:
            def read_required_range(offset, length):
                target = args.output/('layout-%06x.bin' % offset)
                esptool.main(common+['read_flash', '--no-progress', str(offset), str(length), str(target)], esp=stub)
                return target.read_bytes()
            installed = read_layout(read_required_range, images)
            validate_layout(installed, images)
            receipt['backup'] = {'status': 'DISABLED_BY_SETTING'}
            receipt['layout_reads'] = {name: {'bytes': len(data), 'sha256': sha(data)}
                                       for name, data in installed.items()}
        # Stable frozen payload, never a mutable build-path input to the write.
        app = args.output/'firmware.bin'
        if sha(app.read_bytes()) != artifact['firmware.bin']['sha256']: raise RuntimeError('Artifact drift')
        receipt['write'] = 'STARTED'
        (args.output/'receipt.json').write_text(json.dumps(receipt, indent=2))
        esptool.main(common+['write_flash', '--flash_mode', 'keep', '--flash_freq', 'keep', '--flash_size', 'keep', '0x10000', str(app)], esp=stub)
        receipt['write'] = 'PASS'
        esptool.main(common+['verify_flash', '0x10000', str(app)], esp=stub)
        receipt['verify'] = 'PASS'
        stub.hard_reset()
        receipt['reset'] = 'issued after verified app write'
        return 0
    except Exception as error:
        receipt['error'] = str(error)
        raise
    finally:
        port.close()
        receipt['port_closed'] = True
        (args.output/'receipt.json').write_text(json.dumps(receipt, indent=2))


if __name__ == '__main__': raise SystemExit(main())
