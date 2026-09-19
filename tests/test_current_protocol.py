import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from current_protocol import CurrentProtocol, parse_status


def line(uptime=123, relay='OFF', reset='IDLE'):
    return f'STS GPIO13={relay} RESET={reset} GPIO33=HIGH WIFI=DISCONNECTED NTP=WAIT UPTIME_MS={uptime}'


class Fake:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.records, self.sent = [], []
        self.ports = {'bench': self}
    def record(self, role, kind, text):
        self.records.append(dict(role=role, kind=kind, text=text))
    def pump(self, seconds):
        pass
    def write(self, payload):
        self.sent.append(payload.decode().strip())
        reply = next(self.responses)
        if reply:
            self.record('bench', 'rx', reply)
        return len(payload)


class Checks(unittest.TestCase):
    def test_real_firmware_help_and_legacy_gpio12_capabilities(self):
        import re
        source = (Path(__file__).resolve().parents[1] / 'src/main.cpp').read_text(encoding='utf-8')
        help_body = source.split('void printHelp() {', 1)[1].split('\n}', 1)[0]
        current_lines = re.findall(r'Serial.println\("([^"\n]*)"\);', help_body)
        legacy_lines = ['HELP | STS (STATUS) | ON | OFF | RESET',
                        'RESET100: external RESET GPIO12 LOW for 100 ms; diagnostic pulse',
                        'RESETDIAG: GPIO12 pad/latch/config and GPIO33 levels; read-only']
        for help_lines in (current_lines, legacy_lines):
            class HelpFake(Fake):
                def write(self, payload):
                    if payload == b'HELP\n':
                        self.sent.append('HELP')
                        for text in help_lines: self.record('bench', 'rx', text)
                        return len(payload)
                    return super().write(payload)
            client = CurrentProtocol(HelpFake([line(100)]))
            client.qualify()
            self.assertTrue(client.short_reset_supported and client.resetdiag_supported)

    def test_rst_requires_qualification_and_capability(self):
        for qualified, supported in ((False, False), (True, False), (False, True)):
            fake = Fake([])
            client = CurrentProtocol(fake)
            client.qualified, client.reboot_supported = qualified, supported
            with self.assertRaises(RuntimeError): client.write('RST')
            self.assertEqual(fake.sent, [])

    def test_rst_capability_and_invalidation_after_send(self):
        class RebootFake(Fake):
            def write(self, payload):
                if payload == b'HELP\n':
                    self.sent.append('HELP')
                    for text in ('HELP | STS (STATUS) | ON | OFF | RESET',
                                 'RST: reboot this tester; relay ON after boot; RAM history cleared'):
                        self.record('bench', 'rx', text)
                    return len(payload)
                return super().write(payload)
        fake = RebootFake([line(100), 'RST REBOOT', line(1)])
        client = CurrentProtocol(fake)
        client.qualify()
        self.assertTrue(client.reboot_supported)
        client.write('RST')
        self.assertFalse(client.qualified or client.reboot_supported)
        self.assertIsNone(client.last_status)
        for command in ('ON', 'OFF', 'RESET', 'RESET100', 'RST'):
            with self.assertRaises(RuntimeError): client.write(command)
        self.assertEqual(fake.sent, ['HELP', 'STS', 'RST'])
        client.qualify()
        self.assertTrue(client.qualified and client.reboot_supported)
        self.assertEqual(client.last_status['uptime_ms'], 1)

    def test_extended_status_keeps_legacy_adapter_compatible(self):
        class ExtendedFake(Fake):
            def write(self, payload):
                count = super().write(payload)
                for text in ('📶 ✅', '🌐 IP: 192.168.88.46', '📶 RSSI: -22 dBm',
                             '🕒 NTP ✅', '{"schema":1,"type":"status","unix_time":1789746536}'):
                    self.record('bench', 'rx', text)
                return count
        client = CurrentProtocol(ExtendedFake([line()]))
        self.assertEqual(client.status(), parse_status(line()))

    def test_caught_status_failure_blocks_later_effects(self):
        for response in (None, 'STS malformed', line(relay='ON'), line(1)):
            fake = Fake([response])
            client = CurrentProtocol(fake)
            client.qualified = client.short_reset_supported = True
            client.history_supported = client.resetdiag_supported = True
            client.last_status = parse_status(line(100))
            with self.assertRaises(RuntimeError): client.status(relay='OFF')
            for command in ('ON', 'OFF', 'RESET', 'RESET100'):
                with self.assertRaises(RuntimeError): client.write(command)
            self.assertEqual(fake.sent, ['STS'])
            self.assertFalse(client.history_supported or client.resetdiag_supported)

    def test_transport_failure_blocks_later_effects(self):
        class Broken(Fake):
            def write(self, payload):
                raise OSError('disconnected')
        fake = Broken([])
        client = CurrentProtocol(fake); client.qualified = True
        with self.assertRaises(OSError): client.write('STS')
        with self.assertRaises(RuntimeError): client.write('RESET')
        self.assertFalse(client.qualified)

    def test_diagnostic_capability_and_pad_latch_distinction(self):
        fake = Fake([])
        client = CurrentProtocol(fake)
        with self.assertRaises(RuntimeError): client.reset_diagnostics()
        self.assertEqual(fake.sent, [])
        response = 'RESETDIAG ACTIVE=1 EXPECTED=LOW PAD=HIGH LATCH=LOW OE=1 IE=1 MUX=2 PAD_VALID=1 EN_RAW=HIGH EN_STABLE=HIGH ELAPSED_MS=50'
        fake = Fake([response]); client = CurrentProtocol(fake); client.resetdiag_supported = True
        result = client.reset_diagnostics()
        self.assertEqual((result['pad'], result['latch']), ('HIGH', 'LOW'))
        self.assertEqual(fake.sent, ['RESETDIAG'])

    def test_short_reset_requires_capability(self):
        fake = Fake([])
        client = CurrentProtocol(fake); client.qualified = True
        with self.assertRaises(RuntimeError): client.write('RESET100')
        self.assertEqual(fake.sent, [])

    def test_short_reset_ack_order_and_missing(self):
        for acks, success in [(['RESET100 START', 'RESET100 DONE'], True),
                              (['RESET100 START'], False),
                              (['RESET100 DONE', 'RESET100 START'], False)]:
            class ShortFake(Fake):
                def write(self, payload):
                    if payload == b'RESET100\n':
                        self.sent.append('RESET100')
                        for ack in acks: self.record('bench', 'rx', ack)
                        return len(payload)
                    return super().write(payload)
            fake = ShortFake([line(100), line(700)])
            client = CurrentProtocol(fake)
            client.qualified = client.short_reset_supported = True
            if success:
                self.assertEqual(client.reset100('OFF')['requested_duration_ms'], 100)
                self.assertEqual(fake.sent, ['STS', 'RESET100', 'STS'])
            else:
                with self.assertRaises(RuntimeError): client.reset100('OFF')
                self.assertEqual(fake.sent, ['STS', 'RESET100'])

    def test_exact_status(self):
        self.assertEqual(parse_status(line())['uptime_ms'], 123)
        for invalid in (line()+' extra', line().replace('OFF', 'LOW'), 'STS GPIO13=OFF'):
            with self.assertRaises(RuntimeError): parse_status(invalid)
    def test_no_effect_without_protocol(self):
        fake = Fake([])
        with self.assertRaises(RuntimeError): CurrentProtocol(fake).set_relay('OFF')
        self.assertEqual(fake.sent, [])
    def test_old_firmware_refused(self):
        fake = Fake(['ON | OFF | RESET'])
        with self.assertRaises(RuntimeError): CurrentProtocol(fake).qualify()
        self.assertEqual(fake.sent, ['HELP'])
    def test_reset_detected_without_recovery(self):
        fake = Fake([line(200), line(1)])
        client = CurrentProtocol(fake)
        client.status()
        with self.assertRaises(RuntimeError): client.status()
        self.assertEqual(fake.sent, ['STS', 'STS'])
    def test_wrong_relay_refused(self):
        fake = Fake([line(relay='ON')])
        with self.assertRaises(RuntimeError): CurrentProtocol(fake).status(relay='OFF')
    def test_timeout_no_on(self):
        fake = Fake([None])
        with self.assertRaises(RuntimeError): CurrentProtocol(fake).status()
        self.assertEqual(fake.sent, ['STS'])


if __name__ == '__main__': unittest.main()
