"""Bounded COM3 relay / COM4 EN qualification. Passive unless --exercise is set.

Never flashes, discovers an arbitrary board, sends product commands, or retries.
One process owns both ports and one monotonic receive clock. GPIO0 is not measured.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import runpy
import time

# Canonical logger lives alongside the probe project, not in tools/.
REDACT = runpy.run_path(str(Path(__file__).resolve().parent / 'vendor/com_session_logger.py'))['redact_line_safe']
MARKER = 'RELAY13-EN33-01'


def fields(line):
    return dict(re.findall(r'\b([A-Za-z_][A-Za-z_0-9]*)=([^\s]+)', line))


def released(rows, lease_id, reason):
    return any(r.get('type') == 'release' and r.get('reason') == reason
               and r.get('id') == lease_id and r.get('relay') == 'high' for r in rows)


def _integer(row, name):
    try:
        return int(row[name])
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError('Malformed ' + name) from error


def _parsed(records, role):
    result = []
    for record in records:
        if record.get('role') != role or record.get('kind') != 'rx':
            continue
        row = fields(record.get('text', ''))
        row['_text'] = record.get('text', '')
        row['_host'] = float(record.get('host_mono_s', 0))
        result.append(row)
    return result


def validate_bench_continuity(records):
    """Reject a bench reboot or its monotonic firmware clock going backwards."""
    rows = [r for r in _parsed(records, 'bench') if r.get('marker') == MARKER]
    if any(r.get('type') == 'boot' for r in rows):
        raise RuntimeError('Bench restarted inside qualification window')
    previous = None
    for row in rows:
        if 'esp_us' not in row:
            continue
        current = _integer(row, 'esp_us')
        if previous is not None and current < previous:
            raise RuntimeError('Bench clock regressed')
        previous = current
    return rows


def validate_lease_window(records, duration_ms, reason, previous_id=0):
    """Validate one bounded lease entirely from a saved transcript slice."""
    rows = validate_bench_continuity(records)
    acknowledgements = [r for r in rows if r.get('type') == 'response' and
                        r.get('command') == 'bypass' and r.get('ok') == '1' and
                        r.get('relay') == 'low']
    if len(acknowledgements) != 1:
        raise RuntimeError('Expected exactly one bypass acknowledgement')
    ack = acknowledgements[0]
    if _integer(ack, 'duration_ms') != duration_ms:
        raise RuntimeError('Bypass acknowledgement duration mismatch')
    lease_id = _integer(ack, 'id')
    if lease_id <= previous_id:
        raise RuntimeError('Lease id reset or did not progress')
    arm_us = _integer(ack, 'esp_us')
    releases = [r for r in rows if r.get('type') == 'release' and
                r.get('reason') == reason and _integer(r, 'id') == lease_id and
                r.get('relay') == 'high' and r.get('bypass') == '0']
    if len(releases) != 1:
        raise RuntimeError('Missing exact-id release evidence')
    release = releases[0]
    if release['_host'] <= ack['_host']:
        raise RuntimeError('Release record is not ordered after acknowledgement')
    if _integer(release, 'arm_esp_us') != arm_us:
        raise RuntimeError('Release arm timestamp does not match acknowledgement')
    elapsed_us = _integer(release, 'esp_us') - arm_us
    if elapsed_us <= 0:
        raise RuntimeError('Release duration is not positive')
    if reason == 'deadline' and not 1400000 <= elapsed_us <= 1600000:
        raise RuntimeError('Deadline release outside 1400..1600 ms')
    if reason == 'command' and elapsed_us >= 1000000:
        raise RuntimeError('Early release was not earlier than 1000 ms')
    statuses = [r for r in rows if r.get('type') == 'response' and
                r.get('command') == 'status' and r['_host'] > release['_host']]
    if len(statuses) != 1:
        raise RuntimeError('Missing fresh post-release status')
    status = statuses[0]
    _integer(status, 'seq')
    if status.get('timer_ready') != '1':
        raise RuntimeError('Bench timer unavailable')
    if (status.get('relay'), status.get('bypass'), status.get('en'),
        status.get('dropped'), status.get('txdrop')) != ('high', '0', '1', '0', '0'):
        raise RuntimeError('Unsafe post-release status')
    if _integer(status, 'esp_us') < _integer(release, 'esp_us'):
        raise RuntimeError('Post-release status is stale')
    return lease_id


def validate_live_bypass_ack(records, previous_id, now_host):
    rows = validate_bench_continuity(records)
    acks = [r for r in rows if r.get('command') == 'bypass' and r.get('ok') == '1' and r.get('relay') == 'low']
    if len(acks) != 1:
        raise RuntimeError('Missing startup bypass acknowledgement; no reset')
    ack = acks[0]
    if _integer(ack, 'id') <= previous_id or _integer(ack, 'duration_ms') != 1500:
        raise RuntimeError('Unexpected bypass identity/duration; no reset')
    sent = [r for r in records if r.get('role') == 'bench' and
            r.get('kind') == 'tx' and r.get('text') == 'bypass:1500']
    if len(sent) != 1 or not 0 <= now_host - float(sent[0]['host_mono_s']) <= 0.4:
        raise RuntimeError('Insufficient bypass timing margin; no reset')
    if any(r.get('type') == 'release' and r.get('id') == ack['id'] for r in rows):
        raise RuntimeError('Bypass already released; no reset')
    return ack


def validate_reset_inside_lease(records):
    rows = validate_bench_continuity(records)
    release = next(r for r in rows if r.get('type') == 'release' and r.get('reason') == 'deadline')
    edges = [r for r in rows if r.get('type') == 'edge']
    if len(edges) < 2 or [r.get('en') for r in edges[:2]] != ['0', '1']:
        raise RuntimeError('A/B EN reset pair missing')
    begin, end = _integer(release, 'arm_esp_us'), _integer(release, 'esp_us')
    if not begin < _integer(edges[0], 'esp_us') < _integer(edges[1], 'esp_us') < end:
        raise RuntimeError('A/B reset occurred outside relay lease')


def validate_reset_cycle(records, main_marker):
    """Require an exact EN reset pair and sustained post-boot WDT health."""
    bench = validate_bench_continuity(records)
    edges = [r for r in bench if r.get('type') == 'edge']
    if [r.get('en') for r in edges] != ['0', '1']:
        raise RuntimeError('Expected exactly one EN LOW/rise pair')
    low_seq, rise_seq = _integer(edges[0], 'seq'), _integer(edges[1], 'seq')
    if rise_seq != low_seq + 1:
        raise RuntimeError('EN edge sequence gap')
    rise_host = edges[1]['_host']
    statuses = [r for r in bench if 'txdrop' in r]
    if not statuses or any(r.get('dropped') != '0' or r.get('txdrop') != '0' or
                           r.get('timer_ready') != '1' for r in statuses):
        raise RuntimeError('Unknown bench capture loss or timer failure')
    if _integer(statuses[-1], 'seq') < rise_seq:
        raise RuntimeError('Final bench status predates EN rise')

    main = _parsed(records, 'main')
    boots = [r for r in main if r['_text'].startswith('WDT_SERIAL_BOOT ')]
    if len(boots) != 1 or boots[0].get('build') != main_marker or boots[0]['_host'] < rise_host:
        raise RuntimeError('Missing ordered single post-rise main boot')
    boot_host = boots[0]['_host']
    lives = [r for r in main if r['_text'].startswith('WDT_LIVE ') and r['_host'] > boot_host]
    if len(lives) < 2:
        raise RuntimeError('Need at least two post-boot WDT health records')
    previous_seq = previous_ms = previous_feed = None
    for row in lives:
        seq, esp_ms, feed_ok = (_integer(row, 'seq'), _integer(row, 'esp_ms'),
                                _integer(row, 'feed_ok'))
        if previous_seq is not None and (seq <= previous_seq or esp_ms <= previous_ms or
                                         feed_ok < previous_feed):
            raise RuntimeError('WDT uptime/sequence/feed regressed')
        if (row.get('subscribed'), row.get('feed_fail'), row.get('ic_pin_ok'),
            row.get('uart_drop')) != ('1', '0', '1', '0'):
            raise RuntimeError('Post-boot WDT health failed')
        previous_seq, previous_ms, previous_feed = seq, esp_ms, feed_ok
    if _integer(lives[-1], 'feed_ok') <= _integer(lives[0], 'feed_ok'):
        raise RuntimeError('WDT feed did not progress')
    end_host = max(float(r.get('host_mono_s', 0)) for r in records)
    if end_host - rise_host < 15.0 or lives[-1]['_host'] < end_host - 1.5:
        raise RuntimeError('WDT health does not cover the 15 s settle window')
    # A subscribed/feedable task and a pin-ok latch do not prove ISR progress.
    for series in ('TICK', 'EDGE', 'PULSE'):
        samples = [r for r in main if r['_text'].startswith('WDT_' + series + ' ')
                   and r['_host'] > boot_host]
        if len(samples) < 2 or _integer(samples[-1], 'seq') != _integer(lives[-1], 'seq'):
            raise RuntimeError('Missing final progressing WDT_' + series)
        previous_seq = previous_total = -1
        for row in samples:
            seq, total = _integer(row, 'seq'), _integer(row, 'total')
            if seq <= previous_seq or total <= previous_total or _integer(row, 'n') <= 0:
                raise RuntimeError('Nonprogressing WDT_' + series)
            previous_seq, previous_total = seq, total
        if samples[-1]['_host'] < end_host - 1.5:
            raise RuntimeError('Stale WDT_' + series)
    return {'low_seq': low_seq, 'rise_seq': rise_seq, 'boot_host': boot_host,
            'last_esp_ms': _integer(lives[-1], 'esp_ms')}


def validate_devices(devices, bench, main):
    expected = {bench: '1-10.1', main: '1-10.4'}
    if bench == main:
        raise RuntimeError('Ports must differ')
    for port, location in expected.items():
        matches = [d for d in devices if d.device == port]
        if len(matches) != 1 or (matches[0].vid, matches[0].pid, matches[0].location) != (0x1a86, 0x7523, location):
            raise RuntimeError('USB identity mismatch: ' + port)


class Session:
    def __init__(self, ports, output, clock=time.monotonic, sleep=time.sleep):
        self.ports, self.clock, self.sleep = ports, clock, sleep
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=False)
        self.log = (self.output / 'events.jsonl').open('w', encoding='utf8')
        self.start = clock()
        self.buffers = {k: b'' for k in ports}
        self.records = []
        self.identified = False
        self.release_verified = False

    def record(self, role, kind, text):
        now = datetime.now(timezone.utc)
        row = {'utc': now.isoformat(), 'local': now.astimezone().isoformat(),
               'host_mono_s': self.clock() - self.start, 'role': role,
               'kind': kind, 'text': REDACT(text)}
        self.log.write(json.dumps(row, ensure_ascii=False) + '\n')
        self.log.flush()
        self.records.append(row)

    def pump(self, seconds):
        until = self.clock() + seconds
        while self.clock() < until:
            for role, port in self.ports.items():
                data = port.read(min(port.in_waiting, 4096))
                buf = self.buffers[role] + data
                if len(buf) > 65536:
                    raise RuntimeError('Unframed UART overflow: ' + role)
                lines = buf.split(b'\n')
                self.buffers[role] = lines.pop()
                for raw in lines:
                    self.record(role, 'rx', raw.decode('utf8', errors='replace').rstrip('\r'))
            self.sleep(0.005)

    def send(self, command):
        if not self.identified or command not in ('status', 'release', 'bypass:1500', 'bypass:1000'):
            raise RuntimeError('Unidentified bench or command outside bounded plan')
        self.record('bench', 'tx', command)
        data = (command + '\n').encode('ascii')
        if self.ports['bench'].write(data) != len(data):
            raise RuntimeError('Short bench write')

    def rows(self, role, since=0):
        return [fields(r['text']) for r in self.records[since:]
                if r['role'] == role and r['kind'] == 'rx']

    def healthy(self, since=0):
        rows = [r for r in self.rows('bench', since) if r.get('marker') == MARKER and 'txdrop' in r]
        if not rows:
            raise RuntimeError('Missing bench status')
        if any(r.get('dropped') != '0' or r.get('txdrop') != '0' for r in rows):
            raise RuntimeError('Bench capture loss')
        last = rows[-1]
        _integer(last, 'seq')
        if (last.get('relay'), last.get('bypass'), last.get('en'),
            last.get('timer_ready')) != ('high', '0', '1', '1'):
            raise RuntimeError('Relay not released or main EN not HIGH')
        return last

    def identify(self, main_marker):
        self.pump(3)
        self.identified = any(r.get('marker') == MARKER for r in self.rows('bench'))
        if not self.identified:
            raise RuntimeError('Unexpected bench firmware; no commands sent')
        if not any(r.get('build') == main_marker for r in self.rows('main')):
            raise RuntimeError('Unexpected main firmware')
        baseline = self.healthy()
        return baseline

    def qualify(self, main_marker):
        baseline = self.identify(main_marker)
        previous_id = _integer(baseline, 'id')
        for duration, early_release in ((1500, False), (1000, True)):
            start = len(self.records)
            self.send('bypass:' + str(duration))
            self.pump(0.2)
            ack = [r for r in self.rows('bench', start) if r.get('command') == 'bypass' and r.get('ok') == '1' and r.get('relay') == 'low']
            if len(ack) != 1 or 'id' not in ack[0]:
                raise RuntimeError('No bypass acknowledgement')
            if early_release:
                self.send('release')
            self.pump(2)
            reason = 'command' if early_release else 'deadline'
            self.send('status')
            self.pump(0.2)
            previous_id = validate_lease_window(self.records[start:], duration, reason, previous_id)
        self.record('host', 'checkpoint', 'Relay protocol qualified; contact state and WDI not electrically measured')

    def reset_cycles(self, count, main_marker):
        for cycle in range(count):
            self.healthy()
            start = len(self.records)
            self.record('main', 'rts_reset_begin', str(cycle + 1))
            try:
                self.ports['main'].rts = True
                self.pump(0.12)
            finally:
                self.ports['main'].rts = False
                self.record('main', 'rts_reset_end', str(cycle + 1))
            self.pump(15)
            self.send('status')
            self.pump(0.2)
            self.healthy(start)
            validate_reset_cycle(self.records[start:], main_marker)
            self.record('host', 'checkpoint', 'cycle=' + str(cycle + 1) + ' EN transitions + main boot/ticks observed; WDI unmeasured')

    def reset_with_startup_bypass(self, main_marker):
        """One A/B experiment after normal reset showed an extra EN pulse.

        Relay opens for 1500 ms; its independent deadline is never renewed.
        This compares EN behavior, and never relaxes UART/health acceptance.
        """
        previous_id = _integer(self.healthy(), 'id')
        start = len(self.records)
        self.send('bypass:1500')
        self.pump(0.2)
        validate_live_bypass_ack(self.records[start:], previous_id, self.clock() - self.start)
        self.record('main', 'rts_reset_begin', 'startup_bypass')
        try:
            self.ports['main'].rts = True
            self.pump(0.12)
        finally:
            self.ports['main'].rts = False
            self.record('main', 'rts_reset_end', 'startup_bypass')
        self.pump(2)
        self.send('status')
        self.pump(0.2)
        validate_lease_window(self.records[start:], 1500, 'deadline', previous_id)
        validate_reset_inside_lease(self.records[start:])
        self.pump(13)
        self.send('status')
        self.pump(0.2)
        self.healthy(start)
        validate_reset_cycle(self.records[start:], main_marker)
        self.record('host', 'checkpoint', 'startup bypass reset health accepted; physical WDI unmeasured')

    def close(self):
        try:
            if self.identified:
                start = len(self.records)
                self.send('release')
                self.send('status')
                self.pump(1)
                self.healthy(start)
                self.release_verified = True
        except Exception as error:
            self.record('host', 'release_unverified', str(error))
        finally:
            for role, port in self.ports.items():
                try:
                    port.close()
                    self.record(role, 'closed', '')
                except Exception as error:
                    self.record(role, 'close_error', str(error))
            self.log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--bench', default='COM3', choices=['COM3'])
    parser.add_argument('--main', default='COM4', choices=['COM4'])
    parser.add_argument('--main-marker', default='ICWDT-FULL-ADD25C2A-STATE-TRACE')
    parser.add_argument('--exercise', action='store_true')
    parser.add_argument('--resets', type=int, choices=range(4), default=0)
    parser.add_argument('--startup-bypass-reset', action='store_true')
    parser.add_argument('--capture-seconds', type=int, choices=range(1,61), default=10)
    args = parser.parse_args()
    if (args.resets or args.startup_bypass_reset) and not args.exercise:
        parser.error('--resets requires --exercise')
    if args.resets and args.startup_bypass_reset:
        parser.error('Choose one reset experiment, never both')
    import serial
    from serial.tools.list_ports import comports
    validate_devices(comports(), args.bench, args.main)
    ports, session, error = {}, None, None
    try:
        for role, name in [('bench', args.bench), ('main', args.main)]:
            port = serial.Serial(port=None, baudrate=115200, timeout=0, write_timeout=0.2)
            ports[role] = port
            port.dtr = False
            port.rts = False
            port.port = name
            port.open()
        session = Session(ports, args.output)
        if args.exercise:
            if args.startup_bypass_reset:
                session.identify(args.main_marker)
                session.reset_with_startup_bypass(args.main_marker)
            else:
                session.qualify(args.main_marker)
                session.reset_cycles(args.resets, args.main_marker)
        session.pump(args.capture_seconds)
    except Exception as exc:
        error = REDACT(str(exc))
    finally:
        if session:
            session.close()
        else:
            for port in ports.values():
                port.close()
    if session:
        log = args.output / 'events.jsonl'
        result = {'status': 'ERROR' if error else 'COMPLETED', 'error': error,
                  'exercise': args.exercise, 'resets_requested': args.resets,
                  'startup_bypass_reset': args.startup_bypass_reset,
                  'release_verified': session.release_verified,
                  'sha256': hashlib.sha256(log.read_bytes()).hexdigest(),
                  'physical_WDI': 'NOT_MEASURED'}
        if args.exercise and not session.release_verified:
            result['status'] = 'ERROR'
        (args.output / 'receipt.json').write_text(json.dumps(result, indent=2), encoding='utf8')
        print(json.dumps(result))
        return int(result['status'] != 'COMPLETED')
    print(json.dumps({'status': 'ERROR', 'error': error}))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
