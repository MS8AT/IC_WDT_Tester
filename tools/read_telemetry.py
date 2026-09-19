"""Filter saved tester text/stdin into validated JSON Lines. Never opens COM."""
import argparse
from contextlib import ExitStack
from datetime import datetime
import json
from pathlib import Path
import sys


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError('Non-finite JSON number')


def parse_telemetry_line(line, *, allow_unprefixed=False):
    """Return a record, None for human text, or raise ValueError for bad telemetry."""
    line = line.rstrip('\r\n')
    if line.startswith('JSON '):
        payload = line[5:]
    elif ' | JSON ' in line:
        payload = line.split(' | JSON ', 1)[1]
    elif allow_unprefixed and line.startswith('{'):
        payload = line
    else:
        return None
    row = json.loads(payload, object_pairs_hook=_object, parse_constant=_invalid_constant)
    if not isinstance(row, dict) or type(row.get('schema')) is not int or row['schema'] != 1:
        raise ValueError('Unsupported telemetry schema')
    kind = row.get('type')
    if kind not in ('status', 'gpio_change', 'gpio_history', 'wdt_pin'):
        raise ValueError('Unsupported telemetry type')

    def boolean(key):
        if type(row.get(key)) is not bool:
            raise ValueError('Invalid boolean: ' + key)

    def integer(key, low=0, high=None):
        value = row.get(key)
        if type(value) is not int or value < low or (high is not None and value > high):
            raise ValueError('Invalid integer: ' + key)

    def level(key):
        if row.get(key) not in ('HIGH', 'LOW'):
            raise ValueError('Invalid GPIO level: ' + key)

    if kind == 'wdt_pin':
        if (row.get('source') != 'relay_bench' or row.get('subsystem') != 'WDT'
                or 'wdt_triggered' not in row or row['wdt_triggered'] is not None):
            raise ValueError('Invalid WDT observation identity')
        integer('gpio')
        if row['gpio'] not in (13, 33):
            raise ValueError('Unsupported WDT pin')
        if row.get('signal') != ('EN' if row['gpio'] == 33 else 'relay_control'):
            raise ValueError('Invalid WDT pin role')
        integer('level', high=1)
        integer('uptime_us', high=0x7FFFFFFFFFFFFFFF)
        integer('event_id', high=0xFFFFFFFF)
        boolean('time_valid')
        if row['time_valid'] or 'unix_time' not in row or row['unix_time'] is not None:
            raise ValueError('Legacy firmware has no synchronized wall clock')
        if row.get('event') not in ('edge', 'status', 'release', 'command', 'boot'):
            raise ValueError('Invalid WDT event')
        if row.get('reason') not in ('snapshot', 'observed', 'filtered', 'startup', 'off',
                'bypass', 'flash-bypass', 'deadline', 'command', 'malformed',
                'rx_overflow', 'timer_failure', 'busy', 'none'):
            raise ValueError('Invalid WDT reason')
        return row

    if 'source' in row or 'subsystem' in row:
        if row.get('source') != 'ic_wdt_tester' or row.get('subsystem') != 'WDT':
            raise ValueError('Invalid tester identity')
    for key in ('time_valid', 'relay_on', 'reset_active'):
        boolean(key)
    integer('uptime_ms', high=0xFFFFFFFF)
    if 'unix_time' not in row:
        raise ValueError('Missing Unix time')
    if row['time_valid']:
        integer('unix_time')
    elif row['unix_time'] is not None:
        raise ValueError('Unsynchronized time must be null')
    if kind in ('gpio_change', 'gpio_history'):
        integer('event_id')
        integer('gpio', low=33, high=33)
        level('old')
        level('new')
        if row['old'] == row['new']:
            raise ValueError('GPIO change must change level')
        if kind == 'gpio_history' or 'replay' in row:
            boolean('replay')
            if row['replay'] != (kind == 'gpio_history'):
                raise ValueError('Invalid history replay flag')
        if 'source' in row:
            if row.get('signal') != 'EN' or 'wdt_triggered' not in row or row['wdt_triggered'] is not None:
                raise ValueError('EN level does not identify reset cause')
    else:
        for key in ('relay_on_after_reset', 'wifi_connected', 'ntp_synced'):
            boolean(key)
        for key in ('gpio12', 'gpio33', 'gpio33_raw'):
            level(key)
        if 'reset_gpio' in row or 'gpio25' in row:
            integer('reset_gpio', low=25, high=25)
            level('gpio25')
        if 'reset_drive' in row and row['reset_drive'] != ('LOW' if row['reset_active'] else 'HI_Z'):
            raise ValueError('Inconsistent reset drive mode')
        integer('events_total')
        integer('history_count', high=10)
        if row['ntp_synced'] != row['time_valid']:
            raise ValueError('Inconsistent time validity')
        if 'local_time' not in row or 'ip' not in row or 'rssi_dbm' not in row:
            raise ValueError('Missing status details')
        if row['time_valid']:
            if not isinstance(row['local_time'], str):
                raise ValueError('Invalid local time')
            datetime.strptime(row['local_time'], '%d.%m.%Y %H:%M:%S')
        elif row['local_time'] is not None:
            raise ValueError('Unsynchronized local time must be null')
        if row['wifi_connected']:
            from ipaddress import IPv4Address
            if not isinstance(row['ip'], str):
                raise ValueError('Invalid IP')
            IPv4Address(row['ip'])
            integer('rssi_dbm', low=-200, high=0)
        elif row['ip'] is not None or row['rssi_dbm'] is not None:
            raise ValueError('Disconnected IP/RSSI must be null')
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='UTF-8 raw Serial text; default stdin')
    parser.add_argument('--output', type=Path, help='New JSONL file; default stdout')
    parser.add_argument('--allow-unprefixed', action='store_true', help='Accept earlier bare JSON records')
    args = parser.parse_args(argv)
    errors = 0
    try:
        with ExitStack() as stack:
            source = stack.enter_context(args.input.open(encoding='utf-8-sig')) if args.input else sys.stdin
            target = stack.enter_context(args.output.open('x', encoding='utf-8')) if args.output else sys.stdout
            for number, line in enumerate(source, 1):
                try:
                    row = parse_telemetry_line(line, allow_unprefixed=args.allow_unprefixed)
                except ValueError as error:
                    errors += 1
                    print(f'Line {number}: invalid telemetry ({error})', file=sys.stderr)
                    continue
                if row is not None:
                    target.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
    except (OSError, UnicodeError) as error:
        parser.exit(2, f'Telemetry I/O failed: {error}\n')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
