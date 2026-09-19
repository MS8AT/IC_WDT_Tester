"""Offline fake-I/O safety tests, never opens a real COM port."""
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location('relay_session', Path(__file__).resolve().parents[1] / 'tools/relay_bench_session.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class FakeClock:
    now = 0
    def __call__(self): return self.now
    def sleep(self, seconds): self.now += seconds


class FakePort:
    in_waiting = 0
    rts = False
    closed = False
    fail_read = False
    def __init__(self): self.writes = []
    def read(self, _):
        if self.fail_read: raise OSError('read failed')
        return b''
    def write(self, data): self.writes.append(data); return len(data)
    def close(self): self.closed = True


class RelaySessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = FakeClock()
        self.ports = {'bench': FakePort(), 'main': FakePort()}
        self.s = m.Session(self.ports, Path(self.tmp.name)/'run', self.clock, self.clock.sleep)
        self.addCleanup(lambda: self.s.close() if not self.s.log.closed else None)

    def test_identity_checks_ports_locations(self):
        ds = [SimpleNamespace(device=p, vid=0x1a86, pid=0x7523, location=l) for p,l in [('COM3','1-10.1'),('COM4','1-10.4')]]
        m.validate_devices(ds, 'COM3', 'COM4')
        ds[0].location = '1-10.4'
        with self.assertRaises(RuntimeError): m.validate_devices(ds, 'COM3', 'COM4')
        with self.assertRaises(RuntimeError): m.validate_devices(ds, 'COM4', 'COM4')

    def test_unidentified_never_commands(self):
        with self.assertRaises(RuntimeError): self.s.send('bypass:1000')
        self.s.close()
        self.assertEqual(self.ports['bench'].writes, [])
        self.assertTrue(all(p.closed for p in self.ports.values()))

    def test_no_arbitrary_product_or_relay_commands(self):
        self.s.identified = True
        for cmd in ['update:0','hreset','bypass:5001','bypass:5000','release\nbypass:1000']:
            with self.assertRaises(RuntimeError): self.s.send(cmd)

    def test_stale_release_not_accepted(self):
        rows = [{'type':'release','reason':'deadline','id':'1','relay':'high'}]
        self.assertFalse(m.released(rows,'2','deadline'))
        self.assertFalse(m.released(rows,'1','command'))
        self.assertTrue(m.released(rows,'1','deadline'))

    def test_loss_and_low_prevent_next_cycle(self):
        for extra in ['relay=low bypass=1 en=1 dropped=0 txdrop=0', 'relay=high bypass=0 en=0 dropped=0 txdrop=0', 'relay=high bypass=0 en=1 dropped=1 txdrop=0', 'relay=high bypass=0 en=1 dropped=0 txdrop=2', 'relay=high bypass=0 en=1 dropped=0 txdrop=0 timer_ready=0']:
            start = len(self.s.records)
            self.s.record('bench','rx','marker='+m.MARKER+' seq=1 id=0 timer_ready=1 '+extra)
            with self.assertRaises(RuntimeError): self.s.healthy(start)

    def test_reset_exception_releases_rts_and_closes_ports(self):
        self.s.record('bench','rx','marker='+m.MARKER+' relay=high bypass=0 en=1 dropped=0 txdrop=0 timer_ready=1 seq=1 id=0')
        self.ports['bench'].fail_read = True
        with self.assertRaises(OSError): self.s.reset_cycles(1, 'main-marker')
        self.assertFalse(self.ports['main'].rts)
        self.s.identified = True
        self.s.close()
        self.assertEqual(self.ports['bench'].writes, [b'release\n', b'status\n'])
        self.assertTrue(all(p.closed for p in self.ports.values()))
        self.assertFalse(self.s.release_verified)

    def test_startup_bypass_missing_ack_never_asserts_rts(self):
        self.s.identified = True
        self.s.record('bench','rx','marker='+m.MARKER+' relay=high bypass=0 en=1 dropped=0 txdrop=0 timer_ready=1 seq=1 id=0')
        with self.assertRaisesRegex(RuntimeError, 'acknowledgement'):
            self.s.reset_with_startup_bypass('main-marker')
        self.assertFalse(self.ports['main'].rts)
        self.assertFalse(any(r['kind']=='rts_reset_begin' for r in self.s.records))
        self.assertEqual(self.ports['bench'].writes, [b'bypass:1500\n'])

    def test_startup_bypass_read_failure_releases_rts(self):
        from unittest.mock import patch
        self.s.identified = True
        self.s.record('bench','rx','marker='+m.MARKER+' relay=high bypass=0 en=1 dropped=0 txdrop=0 timer_ready=1 seq=1 id=0')
        calls = []
        def pump(seconds):
            calls.append(seconds)
            if len(calls) == 1:
                self.s.record('bench','rx','marker='+m.MARKER+' type=response command=bypass ok=1 duration_ms=1500 esp_us=1 id=1 relay=low')
            else:
                self.assertTrue(self.ports['main'].rts)
                raise OSError('injected UART fault during reset')
        with patch.object(self.s, 'pump', side_effect=pump):
            with self.assertRaises(OSError): self.s.reset_with_startup_bypass('main-marker')
        self.assertFalse(self.ports['main'].rts)

    def test_uart_log_has_dual_host_time_and_redaction(self):
        self.s.record('main','rx','password=hidden esp_us=123')
        row = self.s.records[-1]
        self.assertNotIn('hidden', row['text'])
        for field in ['utc','local','host_mono_s']: self.assertIn(field,row)
        self.assertEqual(m.fields(row['text'])['esp_us'],'123')


def transcript(role, host, text):
    return {'role': role, 'kind': 'rx', 'host_mono_s': host, 'text': text}


def lease_trace(release_us=2500000, reason='deadline', timer_ready='1', duration_ms=1500):
    return [
        transcript('bench', 0.0, 'RELAY_BENCH marker='+m.MARKER+
                   f' type=response command=bypass ok=1 duration_ms={duration_ms} esp_us=1000000 id=7 relay=low'),
        transcript('bench', 1.5, 'RELAY_BENCH marker='+m.MARKER+
                   f' type=release reason={reason} esp_us={release_us} arm_esp_us=1000000 id=7 relay=high bypass=0'),
        transcript('bench', 1.6, 'RELAY_BENCH marker='+m.MARKER+
                   f' type=response command=status esp_us={release_us + 1000} relay=high bypass=0 remaining_ms=0 en=1 edges=4 seq=4 dropped=0 txdrop=0 timer_ready={timer_ready} id=7'),
    ]


def reset_trace():
    rows = [
        transcript('bench', 0.10, 'RELAY_BENCH marker='+m.MARKER+
                   ' type=edge esp_us=100000 en=0 seq=10'),
        transcript('bench', 0.20, 'RELAY_BENCH marker='+m.MARKER+
                   ' type=edge esp_us=200000 en=1 seq=11'),
        transcript('main', 0.30, 'WDT_SERIAL_BOOT build=MAIN-TRACE esp_us=1000 reset_reason=1 timer_init=1 serial_requested=1'),
        transcript('main', 0.50, 'WDT_LIVE seq=1 esp_ms=100 window_ms=100 subscribed=1 feed_ok=1 feed_fail=0 feed_age_ms=0 feed_max_gap_ms=0 ic_pin_ok=1 uart_drop=0 uart_queue=0'),
        transcript('main', 14.80, 'WDT_LIVE seq=2 esp_ms=14400 window_ms=1000 subscribed=1 feed_ok=20 feed_fail=0 feed_age_ms=0 feed_max_gap_ms=10 ic_pin_ok=1 uart_drop=0 uart_queue=0'),
        transcript('bench', 15.25, 'RELAY_BENCH marker='+m.MARKER+
                   ' type=response command=status esp_us=15250000 relay=high bypass=0 remaining_ms=0 en=1 edges=11 seq=11 dropped=0 txdrop=0 timer_ready=1 id=8'),
    ]
    for series in ('TICK', 'EDGE', 'PULSE'):
        rows.extend([
            transcript('main', 0.51, f'WDT_{series} seq=1 total=10 n=10'),
            transcript('main', 14.81, f'WDT_{series} seq=2 total=1400 n=100'),
        ])
    return rows


class TranscriptValidationTests(unittest.TestCase):
    def test_bypass_reset_requires_fresh_active_lease(self):
        tx = {'role':'bench','kind':'tx','host_mono_s':0.0,'text':'bypass:1500'}
        m.validate_live_bypass_ack([tx]+lease_trace()[:1], 6, 0.2)
        for rows, previous, now in [([tx]+lease_trace(),6,0.2), ([tx]+lease_trace()[:1],7,0.2), ([tx]+lease_trace()[:1],6,0.5)]:
            with self.assertRaises(RuntimeError): m.validate_live_bypass_ack(rows,previous,now)
        delayed = lease_trace()[:1]
        delayed[0]['host_mono_s'] = 2.0
        with self.assertRaisesRegex(RuntimeError,'timing margin'):
            m.validate_live_bypass_ack([tx]+delayed,6,2.1)

    def test_bypass_reset_must_be_inside_lease(self):
        rows = lease_trace()
        rows.extend([
            transcript('bench',0.3,'RELAY_BENCH marker='+m.MARKER+' type=edge esp_us=1300000 en=0 seq=1'),
            transcript('bench',0.4,'RELAY_BENCH marker='+m.MARKER+' type=edge esp_us=1400000 en=1 seq=2')])
        # Firmware records are normally received in timestamp order.
        rows.sort(key=lambda r:r['host_mono_s'])
        m.validate_reset_inside_lease(rows)
        rows[2]['text'] = rows[2]['text'].replace('esp_us=1400000','esp_us=2700000')
        with self.assertRaises(RuntimeError): m.validate_reset_inside_lease(rows)
    def test_successful_lease_and_early_release(self):
        self.assertEqual(m.validate_lease_window(lease_trace(), 1500, 'deadline', 6), 7)
        early = lease_trace(1500000, 'command', duration_ms=1000)
        self.assertEqual(m.validate_lease_window(early, 1000, 'command', 6), 7)

    def test_late_expiry_and_timer_failure_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'outside'):
            m.validate_lease_window(lease_trace(2700000), 1500, 'deadline', 6)
        with self.assertRaisesRegex(RuntimeError, 'timer unavailable'):
            m.validate_lease_window(lease_trace(timer_ready='0'), 1500, 'deadline', 6)

    def test_bench_restart_and_id_reset_rejected(self):
        restarted = lease_trace()
        restarted.insert(1, transcript('bench', 0.5, 'RELAY_BENCH marker='+m.MARKER+
                                      ' type=boot relay=high bypass=0 esp_us=10'))
        with self.assertRaisesRegex(RuntimeError, 'restarted'):
            m.validate_lease_window(restarted, 1500, 'deadline', 6)
        with self.assertRaisesRegex(RuntimeError, 'id reset'):
            m.validate_lease_window(lease_trace(), 1500, 'deadline', 7)

    def test_successful_reset_trace(self):
        result = m.validate_reset_cycle(reset_trace(), 'MAIN-TRACE')
        self.assertEqual((result['low_seq'], result['rise_seq']), (10, 11))

    def test_dead_isr_despite_healthy_task_feed_rejected(self):
        for series in ('TICK', 'EDGE', 'PULSE'):
            rows = reset_trace()
            for row in rows:
                if row['text'].startswith('WDT_' + series):
                    row['text'] = row['text'].replace('total=1400 n=100', 'total=10 n=0')
            with self.assertRaisesRegex(RuntimeError, 'Nonprogressing'):
                m.validate_reset_cycle(rows, 'MAIN-TRACE')

    def test_missing_readback_series_rejected(self):
        rows = [r for r in reset_trace() if not r['text'].startswith('WDT_EDGE')]
        with self.assertRaisesRegex(RuntimeError, 'Missing final'):
            m.validate_reset_cycle(rows, 'MAIN-TRACE')

    def test_stale_tick_rejected(self):
        rows = reset_trace()
        rows[4]['text'] = rows[4]['text'].replace('seq=2 esp_ms=14400', 'seq=2 esp_ms=50')
        with self.assertRaisesRegex(RuntimeError, 'regressed'):
            m.validate_reset_cycle(rows, 'MAIN-TRACE')

    def test_reboot_after_health_rejected(self):
        rows = reset_trace()
        rows.insert(5, transcript('main', 10.0,
            'WDT_SERIAL_BOOT build=MAIN-TRACE esp_us=5 reset_reason=1 timer_init=1 serial_requested=1'))
        with self.assertRaisesRegex(RuntimeError, 'single post-rise'):
            m.validate_reset_cycle(rows, 'MAIN-TRACE')

    def test_extra_en_transition_rejected(self):
        rows = reset_trace()
        rows.insert(2, transcript('bench', 0.25, 'RELAY_BENCH marker='+m.MARKER+
                                  ' type=edge esp_us=250000 en=0 seq=12'))
        with self.assertRaisesRegex(RuntimeError, 'exactly one'):
            m.validate_reset_cycle(rows, 'MAIN-TRACE')


if __name__ == '__main__': unittest.main()
