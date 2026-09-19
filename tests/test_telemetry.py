"""Telemetry parsing and offline CLI; no serial dependency or device access."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from read_telemetry import parse_telemetry_line

EVENT = dict(schema=1, type='gpio_change', unix_time=None, time_valid=False,
             event_id=1, uptime_ms=50, gpio=33, old='HIGH', new='LOW',
             relay_on=True, reset_active=False)


class TelemetryTests(unittest.TestCase):
    def test_human_prefix_and_legacy_opt_in(self):
        self.assertIsNone(parse_telemetry_line('🔴 GPIO13'))
        text = json.dumps(EVENT)
        self.assertIsNone(parse_telemetry_line(text))
        self.assertEqual(parse_telemetry_line('JSON ' + text + '\r\n'), EVENT)
        self.assertEqual(parse_telemetry_line('[11:00:29.066] WDT/EN GPIO33 HIGH -> LOW | JSON ' + text), EVENT)
        self.assertEqual(parse_telemetry_line(text, allow_unprefixed=True), EVENT)

    def test_rejects_corrupt_and_inconsistent_records(self):
        for field, value in [('schema', True), ('schema', 2), ('unix_time', 123),
                             ('uptime_ms', -1), ('relay_on', 1), ('gpio', 12),
                             ('new', 'HIGH'), ('type', 'unknown')]:
            with self.subTest(field=field, value=value):
                row = deepcopy(EVENT)
                row[field] = value
                with self.assertRaises(ValueError):
                    parse_telemetry_line('JSON ' + json.dumps(row))
        for payload in ('{', '[]', '{"schema":1,"schema":1}', '{"value":NaN}'):
            with self.assertRaises(ValueError): parse_telemetry_line('JSON ' + payload)

    def test_cli_filters_and_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, output = root / 'serial.txt', root / 'events.jsonl'
            source.write_text('human\nJSON ' + json.dumps(EVENT) + '\nJSON {bad}\n', encoding='utf-8')
            command = [sys.executable, '-B', str(ROOT / 'tools/read_telemetry.py'),
                       '--input', str(source), '--output', str(output)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(output.read_text(encoding='utf-8')), EVENT)
            before = output.read_bytes()
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(output.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
