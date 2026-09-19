"""Single-tester workflow using the canonical Session transport, never opens main.

Explicit port is a transport only. Relay effects require factory identity match.
Closing the session does NOT send ON. The firmware owns timed expiration.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from relay_bench_session import Session, fields, _integer

ROOT = Path(__file__).resolve().parents[1]
MARKER = 'RELAY13-EN33-LATCH-02'


def validate_identity(row, expected):
    if (row.get('ok'), row.get('marker'), row.get('chip_model'),
        row.get('base_mac', '').lower(), row.get('mac_type')) != (
            '1', MARKER, expected['chip_model'], expected['base_mac'].lower(), 'efuse_base'):
        raise RuntimeError('Factory chip/base MAC mismatch; no relay command')
    return row


def validate_status(row, mode=None):
    if row.get('marker') != MARKER or row.get('timer_ready') != '1':
        raise RuntimeError('Wrong firmware or timer unavailable')
    if any(row.get(k) != '0' for k in ('dropped', 'txdrop', 'rxdrop')):
        raise RuntimeError('Capture loss; stop next effect')
    actual = row.get('mode')
    states = {'on': ('high', '0'), 'off_timed': ('low', '1'), 'off_latched': ('low', '1')}
    if actual not in states or (row.get('relay'), row.get('bypass')) != states[actual]:
        raise RuntimeError('Inconsistent relay state')
    if mode is not None and actual != mode:
        raise RuntimeError('Unexpected relay mode')
    if actual != 'off_timed' and row.get('remaining_ms') != '0':
        raise RuntimeError('Unexpected timer deadline')
    for key in ('id', 'seq', 'esp_us'):
        if _integer(row, key) < 0:
            raise RuntimeError('Negative ' + key)
    return row


def validate_timed_release(rows, ack):
    matches = [r for r in rows if r.get('marker') == MARKER and
               r.get('type') == 'release' and r.get('id') == ack.get('id')]
    if len(matches) != 1:
        raise RuntimeError('Missing unique timed release')
    row = matches[0]
    elapsed = _integer(row, 'esp_us') - _integer(ack, 'esp_us')
    if (row.get('reason'), row.get('relay'), row.get('bypass'), row.get('arm_esp_us')) != (
            'deadline', 'high', '0', ack.get('esp_us')) or not 1400000 <= elapsed <= 1600000:
        raise RuntimeError('Timed release reason/identity/duration mismatch')
    return elapsed


class TesterSession(Session):
    def __init__(self, ports, output, expected, clock=time.monotonic, sleep=time.sleep):
        super().__init__(ports, output, clock, sleep)
        self.expected = expected
        self.identity = None
        self.last_esp_us = -1
        self.verified_record = 0

    def send(self, command):
        allowed = ('identity', 'status', 'function wdt on', 'function wdt off',
                   'function wdt timed 1500')
        if command not in allowed or (command != 'identity' and not self.identified):
            raise RuntimeError('Unidentified tester or command outside plan')
        self.record('bench', 'tx', command)
        data = (command + '\n').encode('ascii')
        if self.ports['bench'].write(data) != len(data):
            raise RuntimeError('Short tester write')

    def request(self, command, ack_command):
        start = len(self.records)
        self.send(command)
        self.pump(0.25)
        rows = self.rows('bench', start)
        continuity = self.rows('bench', self.verified_record)
        self.verified_record = len(self.records)
        if any(r.get('type') == 'boot' for r in continuity):
            raise RuntimeError('Tester rebooted during command')
        if command == 'identity':
            hits = [r for r in rows if 'base_mac' in r]
        else:
            hits = [r for r in rows if r.get('type') == 'response' and r.get('command') == ack_command]
        if len(hits) != 1:
            raise RuntimeError('Missing unique fresh ACK: ' + command)
        row = hits[0]
        if row.get('marker') != MARKER:
            raise RuntimeError('ACK firmware mismatch')
        if command != 'status' and row.get('ok') != '1':
            raise RuntimeError('Command rejected')
        for sample in continuity:
            if 'esp_us' in sample and sample.get('marker') == MARKER and sample.get('type') in ('status', 'response'):
                now = _integer(sample, 'esp_us')
                if now < self.last_esp_us:
                    raise RuntimeError('Tester clock regressed')
                self.last_esp_us = now
        return row

    def identify_tester(self):
        self.pump(1.2)
        self.verified_record = len(self.records)
        self.identity = validate_identity(self.request('identity', 'identity'), self.expected)
        self.identified = True
        return self.status()

    def status(self, mode=None):
        return validate_status(self.request('status', 'status'), mode)

    def effect(self, action):
        if action != 'off':
            self.invalidate_ready()
        self.status()  # Fresh health before every effect.
        command = {'off': 'function wdt off', 'on': 'function wdt on',
                   'timed': 'function wdt timed 1500'}[action]
        ack = self.request(command, 'bypass' if action == 'timed' else action)
        expected = 'on' if action == 'on' else 'off_latched' if action == 'off' else 'off_timed'
        if ack.get('relay') != ('high' if action == 'on' else 'low'):
            raise RuntimeError('ACK relay mismatch')
        status = self.status(expected)
        if _integer(ack, 'id') != _integer(status, 'id'):
            raise RuntimeError('ACK/status command id mismatch')
        return ack, status

    def invalidate_ready(self):
        ready = self.output / 'READY.json'
        if ready.exists():
            ready.replace(self.output / 'READY.invalid.json')

    def qualify_timed(self):
        start = len(self.records)
        ack, _ = self.effect('timed')
        self.pump(1.7)
        self.status('on')
        return validate_timed_release(self.rows('bench', start), ack)

    def close(self):
        # Explicit ON is separate. Never restore WDT as exception cleanup.
        self.invalidate_ready()
        for role, port in self.ports.items():
            try:
                port.close()
                self.record(role, 'closed', 'relay state preserved; close may electrically reset some adapters')
            except Exception as error:
                self.record(role, 'close_error', str(error))
        self.log.close()


def write_ready(session, ack, status):
    result = {
        'utc': datetime.now(timezone.utc).isoformat(), 'base_mac': session.expected['base_mac'],
        'mac_type': 'BASE_MAC', 'chip_model': session.rom_identity['chip_description'],
        'chip_model_base': session.expected['chip_model'],
        'rom_identity_receipt': session.rom_receipt_path,
        'port': session.ports['bench'].port,
        'chip_revision': session.expected['chip_revision'], 'relay': status['relay'],
        'mode': 'latched_off', 'timer_active': False, 'release_requires_on': True,
        'exclusive_owner': True, 'owner': session.owner, 'marker': MARKER,
        'command_ack': ack, 'status': status, 'evidence_path': str((session.output / 'events.jsonl').resolve()),
        'evidence_dir': str(session.output.resolve()),
        'contact_measurement': 'NOT_VERIFIED', 'wdi_waveform': 'NOT_MEASURED',
    }
    pending = session.output / 'READY.pending.json'
    pending.write_text(json.dumps(result, indent=2), encoding='utf8')
    pending.replace(session.output / 'READY.json')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--action', choices=['status', 'timed', 'off', 'on', 'qualify', 'reboot-check'], default='status')
    parser.add_argument('--hold-seconds', type=int, default=0)
    parser.add_argument('--rom-receipt', type=Path)
    parser.add_argument('--owner', help='Current explicitly agreed exclusive tester owner')
    args = parser.parse_args()
    if not 0 <= args.hold_seconds <= 1800 or (args.hold_seconds and args.action != 'off'):
        parser.error('hold 0..1800 allowed only for explicit off')
    if args.action == 'off' and args.rom_receipt is None:
        parser.error('off requires verified --rom-receipt')
    if args.action == 'off' and not args.owner:
        parser.error('off requires current --owner after exclusive handoff')
    import serial
    expected = json.loads((ROOT / 'device-profile.json').read_text())['tester']
    rom = None
    if args.rom_receipt:
        from flash_tester import validate_rom
        receipt = json.loads(args.rom_receipt.read_text())
        rom = receipt['actual']
        validate_rom(rom['chip_description'], rom['base_mac'], expected)
        if receipt.get('verify') != 'PASS' or rom.get('mac_type') != 'BASE_MAC':
            raise RuntimeError('Unverified ROM/flash receipt')
    port = serial.Serial(port=None, baudrate=115200, timeout=0, write_timeout=0.2)
    session = None
    try:
        port.dtr = False
        port.rts = False
        port.port = args.port
        port.open()
        session = TesterSession({'bench': port}, args.output, expected)
        session.rom_identity = rom
        session.owner = args.owner
        session.rom_receipt_path = str(args.rom_receipt.resolve()) if args.rom_receipt else None
        initial = session.identify_tester()
        print(json.dumps({'identity': session.identity, 'status': initial}), flush=True)
        if args.action == 'reboot-check':
            session.effect('off')
            before_reset = session.status('off_latched')
            reset_start = len(session.records)
            session.invalidate_ready()
            session.record('host', 'tester_reset_begin', 'explicit reboot behavior qualification; no main flash in progress')
            try:
                port.rts = True
                session.sleep(0.15)
            finally:
                port.rts = False
            session.identified = False
            session.last_esp_us = -1
            session.identify_tester()
            after_reset = session.status('on')
            boots = [r for r in session.rows('bench', reset_start) if r.get('type') == 'boot' and r.get('marker') == MARKER]
            if not boots and _integer(after_reset, 'esp_us') >= _integer(before_reset, 'esp_us'):
                raise RuntimeError('No boot marker or clock reset evidence')
            session.record('host', 'tester_reset_verified', 'factory identity same; default on after reboot; Hi-Z/contact waveform not measured')
        elif args.action == 'qualify':
            session.status('on')
            session.qualify_timed()
            session.effect('off')
            session.pump(6)
            session.status('off_latched')
            session.effect('on')
        elif args.action == 'timed':
            session.qualify_timed()
        elif args.action != 'status':
            ack, status = session.effect(args.action)
            if args.action == 'off':
                session.pump(6)
                status = session.status('off_latched')
                print(json.dumps(write_ready(session, ack, status)), flush=True)
                deadline = session.clock() + args.hold_seconds
                while session.clock() < deadline:
                    session.pump(0.7)
                    status = session.status('off_latched')
                    # Only this explicit file command requests ON after main owner completes.
                    on_request = session.output / 'ON.request'
                    if on_request.exists():
                        if on_request.read_text().strip() != 'function wdt on':
                            raise RuntimeError('Invalid ON request')
                        session.effect('on')
                        break
                    write_ready(session, ack, status)
        print(json.dumps({'result': 'PASS', 'final_status': session.status()}), flush=True)
        return 0
    except Exception as error:
        if session:
            session.record('host', 'FAILED', str(error))
            (session.output / 'FAILED.json').write_text(json.dumps({'error': str(error)}))
            ready = session.output / 'READY.json'
            if ready.exists():
                ready.rename(session.output / 'READY.invalid.json')
        print(json.dumps({'result': 'FAIL', 'error': str(error), 'automatic_on': False}), flush=True)
        return 1
    finally:
        if session:
            session.close()
        else:
            port.close()


if __name__ == '__main__':
    raise SystemExit(main())
