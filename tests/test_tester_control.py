import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import tester_control as m


class FakePort:
    in_waiting = 0
    def __init__(self): self.writes = []; self.closed = False
    def write(self, data): self.writes.append(data); return len(data)
    def close(self): self.closed = True


class TesterTests(unittest.TestCase):
    def setUp(self):
        self.expected = {'chip_model': 'ESP32-D0WDQ6', 'base_mac': '02:00:00:00:00:01'}
        self.identity = dict(ok='1', marker=m.MARKER, chip_model='ESP32-D0WDQ6', base_mac='02:00:00:00:00:01', mac_type='efuse_base')
        self.status = dict(marker=m.MARKER, timer_ready='1', dropped='0', txdrop='0', rxdrop='0', mode='off_latched', relay='low', bypass='1', remaining_ms='0', id='1', seq='0', esp_us='1000')

    def test_identity_uses_factory_not_com(self):
        m.validate_identity(self.identity, self.expected)
        for key, wrong in [('base_mac', '02:00:00:00:00:02'), ('chip_model', 'ESP32-S3'), ('mac_type', 'wifi_sta'), ('marker', 'old')]:
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                m.validate_identity(dict(self.identity, **{key: wrong}), self.expected)

    def test_loss_and_state_fail_closed(self):
        m.validate_status(self.status, 'off_latched')
        for key, wrong in [('dropped', '1'), ('txdrop', '1'), ('rxdrop', '1'), ('relay', 'high'), ('mode', 'off_timed'), ('remaining_ms', '90000'), ('timer_ready', '0')]:
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                m.validate_status(dict(self.status, **{key: wrong}), 'off_latched')

    def test_close_preserves_off_even_after_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            port = FakePort()
            s = m.TesterSession({'bench': port}, Path(tmp)/'run', self.expected)
            s.identified = True
            s.send('function wdt off')
            (s.output / 'READY.json').write_text('{}')
            s.close()
            self.assertEqual(port.writes, [b'function wdt off\n'])
            self.assertTrue(port.closed)
            self.assertFalse((s.output / 'READY.json').exists())

    def test_on_invalidates_ready_before_first_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            port = FakePort()
            s = m.TesterSession({'bench': port}, Path(tmp)/'run', self.expected)
            (s.output / 'READY.json').write_text('{}')
            def failed_status():
                self.assertFalse((s.output / 'READY.json').exists())
                raise RuntimeError('disconnect')
            s.status = failed_status
            try:
                with self.assertRaisesRegex(RuntimeError, 'disconnect'): s.effect('on')
                self.assertEqual(port.writes, [])
            finally: s.close()

    def test_unidentified_and_arbitrary_commands_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            port = FakePort()
            s = m.TesterSession({'bench': port}, Path(tmp)/'run', self.expected)
            try:
                for command in ['function wdt off', 'function wdt on', 'bypass:90000']:
                    with self.assertRaises(RuntimeError): s.send(command)
                self.assertEqual(port.writes, [])
                s.send('identity')
                self.assertEqual(port.writes, [b'identity\n'])
            finally: s.close()

    def test_missing_ack_and_reboot_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            port = FakePort()
            s = m.TesterSession({'bench': port}, Path(tmp)/'run', self.expected)
            s.identified = True
            s.pump = lambda _: None
            try:
                with self.assertRaisesRegex(RuntimeError, 'ACK'): s.request('status', 'status')
                s.record('bench', 'rx', 'RELAY_BENCH marker='+m.MARKER+' type=boot')
                with self.assertRaisesRegex(RuntimeError, 'rebooted'): s.request('status', 'status')
            finally: s.close()

    def test_timed_release_requires_deadline_and_duration(self):
        ack = dict(id='7', esp_us='1000')
        release = dict(marker=m.MARKER, type='release', id='7', reason='deadline',
                       relay='high', bypass='0', arm_esp_us='1000', esp_us='1501000')
        self.assertEqual(m.validate_timed_release([release], ack), 1500000)
        for key, wrong in [('reason', 'malformed'), ('id', '6'), ('esp_us', '1001000'), ('arm_esp_us', '0')]:
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                m.validate_timed_release([dict(release, **{key: wrong})], ack)


if __name__ == '__main__': unittest.main()
