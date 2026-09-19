"""Bounded current main.cpp adapter over the canonical Session transport.

No implicit ON, RESET, release, port open/close, or legacy identity protocol.
Caller owns factory identity, continuous handles, wiring and scenario gates.
"""
import re
from functools import wraps


def invalidate_on_error(method):
    """Any failed transaction withdraws permission for subsequent effects."""
    @wraps(method)
    def guarded(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception:
            self.qualified = False
            self.short_reset_supported = False
            self.history_supported = False
            self.resetdiag_supported = False
            self.reboot_supported = False
            raise
    return guarded

STATUS = re.compile(r'STS GPIO13=(ON|OFF) RESET=(ACTIVE|IDLE) GPIO33=(HIGH|LOW) WIFI=(CONNECTED|DISCONNECTED) NTP=(SYNCED|WAIT) UPTIME_MS=([0-9]+)')


def parse_status(line):
    match = STATUS.fullmatch(line)
    if not match:
        raise RuntimeError('Malformed current-protocol status')
    values = match.groups()
    return dict(zip(('relay', 'reset', 'en', 'wifi', 'ntp', 'uptime_ms'),
                    (*values[:5], int(values[5]))))


class CurrentProtocol:
    def __init__(self, session):
        self.session = session
        self.last_status = None
        self.qualified = False
        self.short_reset_supported = False
        self.history_supported = False
        self.resetdiag_supported = False
        self.reboot_supported = False

    @invalidate_on_error
    def write(self, command):
        if command not in ('HELP', 'STS', 'ON', 'OFF', 'RESET', 'RESET100', 'HISTORY', 'RESETDIAG', 'RST'):
            raise ValueError('Command outside authorized protocol')
        if command in ('ON', 'OFF', 'RESET', 'RESET100', 'RST') and not self.qualified:
            raise RuntimeError('HELP and initial STS required before effects')
        if command == 'RESET100' and not self.short_reset_supported:
            raise RuntimeError('RESET100 capability not confirmed')
        if command == 'HISTORY' and not self.history_supported:
            raise RuntimeError('HISTORY capability not confirmed')
        if command == 'RESETDIAG' and not self.resetdiag_supported:
            raise RuntimeError('RESETDIAG capability not confirmed')
        if command == 'RST' and not self.reboot_supported:
            raise RuntimeError('RST capability not confirmed')
        payload = (command + '\n').encode('ascii')
        self.session.record('bench', 'tx', command)
        if self.session.ports['bench'].write(payload) != len(payload):
            raise RuntimeError('Short serial write; outcome unknown')
        if command == 'RST':
            # A sent reboot invalidates the old session state, even without ACK.
            self.qualified = False
            self.short_reset_supported = False
            self.history_supported = False
            self.resetdiag_supported = False
            self.reboot_supported = False
            self.last_status = None

    @invalidate_on_error
    def status(self, relay=None, reset=None):
        # Drain already-received input before issuing the next status request.
        self.session.pump(0.03)
        start = len(self.session.records)
        self.write('STS')
        self.session.pump(0.25)
        for _ in range(7):
            rows = [r['text'] for r in self.session.records[start:]
                    if r['role'] == 'bench' and r['kind'] == 'rx'
                    and r['text'].startswith('STS ')]
            if rows:
                if len(rows) != 1:
                    raise RuntimeError('Ambiguous status response')
                state = parse_status(rows[0])
                if self.last_status and state['uptime_ms'] <= self.last_status['uptime_ms']:
                    raise RuntimeError('Tester uptime stopped/regressed; new effects forbidden')
                self.last_status = state
                if relay is not None and state['relay'] != relay:
                    raise RuntimeError('Unexpected GPIO13 state')
                if reset is not None and state['reset'] != reset:
                    raise RuntimeError('Unexpected RESET state')
                return state
            self.session.pump(0.25)
        raise RuntimeError('Tester status timeout; no implicit recovery command')

    @invalidate_on_error
    def qualify(self):
        start = len(self.session.records)
        self.write('HELP')
        self.session.pump(1)
        if not any(r['role'] == 'bench' and r['kind'] == 'rx'
                   and r['text'] == 'HELP | STS (STATUS) | ON | OFF | RESET'
                   for r in self.session.records[start:]):
            raise RuntimeError('Current HELP protocol not confirmed')
        state = self.status(reset='IDLE')
        self.short_reset_supported = any(r['role'] == 'bench' and r['kind'] == 'rx'
            and r['text'] in (
                'RESET100: external RESET GPIO12 LOW for 100 ms; diagnostic pulse',
                'RESET100: external RESET GPIO25 LOW for 100 ms, then INPUT (Hi-Z)')
            for r in self.session.records[start:])
        help_lines = {r['text'] for r in self.session.records[start:]
                      if r['role'] == 'bench' and r['kind'] == 'rx'}
        self.history_supported = 'HISTORY: last 10 GPIO33 changes with time; no output changes' in help_lines
        self.resetdiag_supported = bool(help_lines.intersection({
            'RESETDIAG: GPIO12 pad/latch/config and GPIO33 levels; read-only',
            'RESETDIAG: GPIO25 pad/latch/config and GPIO33 levels; read-only'}))
        self.reboot_supported = 'RST: reboot this tester; relay ON after boot; RAM history cleared' in help_lines
        self.qualified = True
        return state

    @invalidate_on_error
    def set_relay(self, relay):
        if relay not in ('ON', 'OFF'):
            raise ValueError('Invalid relay request')
        self.write(relay)
        return self.status(relay=relay, reset='IDLE')

    @invalidate_on_error
    def reset_diagnostics(self):
        start = len(self.session.records)
        self.write('RESETDIAG')
        for _ in range(6):
            self.session.pump(.05)
            rows = [r['text'] for r in self.session.records[start:]
                    if r['role'] == 'bench' and r['kind'] == 'rx'
                    and r['text'].startswith('RESETDIAG ')]
            if rows:
                if len(rows) != 1:
                    raise RuntimeError('Ambiguous RESETDIAG response')
                match = re.fullmatch(r'RESETDIAG ACTIVE=([01]) EXPECTED=(HIGH|LOW) PAD=(HIGH|LOW) LATCH=(HIGH|LOW) OE=([01]) IE=([01]) MUX=([0-7]) PAD_VALID=([01]) EN_RAW=(HIGH|LOW) EN_STABLE=(HIGH|LOW) ELAPSED_MS=([0-9]+)', rows[0])
                if not match:
                    raise RuntimeError('Malformed RESETDIAG response')
                return dict(zip(('active', 'expected', 'pad', 'latch', 'oe', 'ie', 'mux', 'pad_valid', 'en_raw', 'en_stable', 'elapsed_ms'), match.groups()))
        raise RuntimeError('RESETDIAG timeout')

    @invalidate_on_error
    def reset100(self, relay):
        self.status(relay=relay, reset='IDLE')
        start = len(self.session.records)
        self.write('RESET100')
        self.session.pump(0.5)
        acknowledgements = [r['text'] for r in self.session.records[start:]
            if r['role'] == 'bench' and r['kind'] == 'rx' and r['text'].startswith('RESET100 ')]
        if acknowledgements != ['RESET100 START', 'RESET100 DONE']:
            raise RuntimeError('Short reset acknowledgement missing or ambiguous')
        return {'requested_duration_ms': 100,
                'acknowledgements': acknowledgements,
                'released': self.status(relay=relay, reset='IDLE')}
