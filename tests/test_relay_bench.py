"""Host regression for the dedicated GPIO13 relay / GPIO33 EN bench."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RelayJsonTests(unittest.TestCase):
    def test_active_entrypoint_and_legacy_profile_defaults(self):
        test_relay_profile_isolated_from_legacy_entrypoint()
        test_relay_maintenance_profile_is_explicit_and_default_off()

    def test_real_output_keeps_capture_time_and_parses(self):
        source = r'''
#define RELAY_BENCH_LATCHED_OFF 1
#define RELAY_TEST_LATCHED 1
#include "relay_bench_harness.cpp"
int main() {
  RelayBenchSetup();
  RelayBenchExecuteCommand("off");
  assert(fakeRelayLevel == 0);
  RelayBenchExecuteCommand("on");
  RelayBenchReportRelease();
  fakeNowUs = 123456789;
  fakeEnLevel = 0;
  RelayBenchEnISR();
  const auto writes = fakeRelayWrites;
  fakeNowUs = 999999999;
  RelayBenchDrainEdges();
  RelayBenchPrintStatus("response", "status");
  assert(fakeRelayWrites == writes);
  AppSerial.printf("WDT max-range fixture | ");
  RelayBenchPinJson("release", 13, 1, INT64_MAX, UINT32_MAX, "timer_failure");
  std::fputs(AppSerial.output.c_str(), stdout);
}
'''
        with tempfile.TemporaryDirectory(prefix='relay-json-') as temp:
            folder = Path(temp)
            path = folder / 'test.cpp'
            path.write_text(source, encoding='utf-8')
            binary = folder / 'test.exe'
            subprocess.run([shutil.which('g++'), '-std=c++11', '-Wall', '-Wextra', '-Werror',
                            '-I', str(ROOT / 'tests'), str(path), '-o', str(binary)],
                           check=True, timeout=40)
            result = subprocess.run([str(binary)], check=True, capture_output=True,
                                    text=True, timeout=15)
        sys.path.insert(0, str(ROOT / 'tools'))
        from read_telemetry import parse_telemetry_line
        lines = [line for line in result.stdout.splitlines() if ' | JSON ' in line]
        rows = [parse_telemetry_line(line) for line in lines]
        self.assertEqual([r['event'] for r in rows],
                         ['boot', 'command', 'release', 'edge', 'status', 'status', 'release'])
        self.assertTrue(all(len(('JSON ' + line.split(' | JSON ', 1)[1] + '\n').encode()) < 384
                            for line in lines))
        self.assertEqual((rows[3]['gpio'], rows[3]['level'], rows[3]['uptime_us']), (33, 0, 123456789))
        self.assertEqual(rows[5]['uptime_us'], 999999999)
        self.assertTrue(all(row['wdt_triggered'] is None and row['unix_time'] is None for row in rows))
        import json
        for key, value in [('gpio', 25), ('level', True), ('time_valid', True),
                           ('unix_time', 100), ('wdt_triggered', True), ('signal', 'relay_control')]:
            invalid = dict(rows[3], **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                parse_telemetry_line('WDT test | JSON ' + json.dumps(invalid))


def test_relay_bench_host_scenarios(tmp_path):
    compiler = shutil.which("g++")
    assert compiler, "g++ required"
    binary = tmp_path / "relay_bench.exe"
    result = subprocess.run(
        [compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror",
         str(ROOT / "tests" / "relay_bench_harness.cpp"), "-o", str(binary)],
        text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    run = subprocess.run([str(binary)], text=True, capture_output=True, timeout=10)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "relay bench host scenarios PASS" in run.stdout


def test_relay_maintenance_host_scenarios(tmp_path):
    compiler = shutil.which("g++")
    assert compiler, "g++ required"
    binary = tmp_path / "relay_bench_maintenance.exe"
    result = subprocess.run(
        [compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror",
         str(ROOT / "tests" / "relay_bench_maintenance_harness.cpp"), "-o", str(binary)],
        text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    run = subprocess.run([str(binary)], text=True, capture_output=True, timeout=10)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "relay bench maintenance scenarios PASS" in run.stdout


def test_relay_profile_isolated_from_legacy_entrypoint():
    ini = (ROOT / 'platformio.ini').read_text(encoding='utf-8')
    assert 'build_src_filter = -<*> +<main.cpp>' in ini
    assert '-DPROBE_GENERATOR=0' in ini and '-DAUTO_ICWDT_ENABLED=0' in ini
    source = (ROOT / 'src/RelayResetBench.h').read_text(encoding='utf-8')
    assert 'RELAY_BENCH_RELAY_PIN = 13' in source
    assert 'RELAY_BENCH_EN_PIN = 33' in source
    main = (ROOT/'src/main.cpp').read_text(encoding='utf-8')
    assert '#include "RelayResetBench.h"' not in main
    assert 'constexpr uint8_t RESET_PIN = 25;' in main


def test_relay_maintenance_profile_is_explicit_and_default_off():
    source = (ROOT / 'src/RelayResetBench.h').read_text(encoding='utf-8')
    assert '#define RELAY_BENCH_MAINTENANCE_90S 0' in source
    assert 'RELAY13-EN33-MAINT90-01' in source
    assert 'strcmp(command, "flash-bypass:90000")' in source
    assert 'RELAY_BENCH_MAINTENANCE_90S=1' not in (ROOT/'platformio.ini').read_text()


