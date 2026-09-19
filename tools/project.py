"""Offline checks, host tests and a frozen portable export; never opens Serial."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT_FILES = (
    'LICENSE', 'docs/FUTURE.md', 'docs/LICENSING.md', 'docs/SERVICES.md', 'docs/PAYMENT.md',
    'docs/commercial/CONTRACT_RU.md', 'docs/commercial/LOYALTY_88_RU.md',
    'docs/commercial/ORDER_RU.md', 'docs/commercial/LEGAL_NOTES.md',
    'README.md', 'AGENTS.md', '.gitignore', '.gitattributes', 'platformio.ini',
    'dependency-lock.json', 'flash-settings.json', 'src/main.cpp', 'tools/project.py',
    'tools/check_build.py', 'tests/test_project.py', 'tests/test_main.py',
    'docs/OPERATOR.md', 'docs/PORTABILITY.md', 'docs/ACCEPTANCE.md', 'docs/INSTRUCTIONS_INDEX.md',
    'docs/RECHECK_20260918.md',
    'tools/current_protocol.py', 'tests/test_current_protocol.py',
    'tools/restart_usb_port.ps1', 'tests/test_usb_restart.py', 'docs/USB_COM_RECOVERY.md',
    'tools/restart_usb_interactive.ps1',
    'tools/read_usb_restart_events.py',
    'USB_RESTART_PLAN.md',
    'NVS_RECOVERY_PLAN.md',
    'tools/read_telemetry.py', 'tests/test_telemetry.py',
    'docs/AI_QUICKSTART.md', 'docs/COMMANDS.md', 'docs/TELEMETRY.md', 'docs/LEGACY_LATCH02.md',
    'src/AGENTS.md', 'tools/AGENTS.md', 'tests/AGENTS.md', 'docs/AGENTS.md',
    'docs/PROJECT_LAYOUT.md',
    'src/secrets.example.h', 'device-profile.example.json',
    'docs/GETTING_STARTED.md', 'docs/HOW_IT_WORKS.md', 'docs/WIRING.md',
    'docs/GITHUB.md', 'docs/TROUBLESHOOTING.md', 'CONTRIBUTING.md',
    'docs/IC_WDT_HARDWARE.md', 'docs/datasheets/README.md', 'docs/datasheets/manifest.json',
    'docs/VALIDATION_20260919.md',
    'docs/datasheets/IN1232-integral-archive.pdf', 'docs/datasheets/DS1232LP-040594.pdf',
    'docs/datasheets/INTEGRAL-catalog-2005.pdf',
    'docs/HANDOFF.md', 
    'skills/esp32-ic-wdt-tester/SKILL.md',
    'skills/esp32-ic-wdt-tester/agents/openai.yaml',
    'src/RelayResetBench.h', 'src/relay_main.cpp', 'src/Auto_Serial.h',
    'tools/relay_bench_session.py', 'tools/vendor/com_session_logger.py',
    'tests/test_relay_session.py', 'tests/relay_bench_harness.cpp',
    'tests/relay_bench_maintenance_harness.cpp', 'tests/relay_latched_harness.cpp',
    'tools/sdk_preflight.py', 'tools/flash_tester.py', 'tests/test_relay_bench.py', 'tests/test_flash_tester.py', 'tests/test_esptool_retry.py', 'device-profile.json', 'tools/tester_control.py', 'tests/test_tester_control.py', 'docs/CODE_STYLE.md',
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def regular_file(base, relative):
    """Reject traversal and symlink/junction escape before reading a source."""
    parts = Path(relative).parts
    if Path(relative).is_absolute() or '..' in parts or not parts:
        raise ValueError('Unsafe relative path: ' + relative)
    candidate = base.joinpath(*parts)
    current = base
    for part in parts:
        current = current / part
        if current.is_symlink() or getattr(current, 'is_junction', lambda: False)():
            raise ValueError('Linked source rejected: ' + relative)
    if not candidate.is_file() or not candidate.resolve().is_relative_to(base.resolve()):
        raise ValueError('Missing or outside source: ' + relative)
    return candidate


def checked_dependencies(root=ROOT):
    lock = json.loads((root / 'dependency-lock.json').read_text(encoding='utf-8'))
    if lock['schema_version'] != 2:
        raise ValueError('Unsupported lock schema')
    repo = root
    entries = {}
    for row in lock['dependencies']:
        relative = row['path']
        if relative in entries:
            raise ValueError('Duplicate dependency: ' + relative)
        data = regular_file(repo, relative).read_bytes()
        if digest(data) != row['sha256']:
            raise ValueError('Dependency changed; request owner review: ' + relative)
        entries[relative] = data
    return entries


def run_tests(root=ROOT):
    before = checked_dependencies(root)
    probe = root
    subprocess.run([sys.executable, '-B', str(probe / 'tests/test_relay_session.py')],
                   check=True, timeout=60)
    compiler = shutil.which('g++')
    if not compiler:
        raise RuntimeError('g++ missing; no dependencies were installed')
    with tempfile.TemporaryDirectory(prefix='ic-wdt-tester-') as directory:
        for name in ('relay_bench_harness', 'relay_bench_maintenance_harness', 'relay_latched_harness'):
            binary = Path(directory) / (name + '.exe')
            subprocess.run([compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror',
                            str(root / ('tests/' + name + '.cpp')), '-o', str(binary)],
                           check=True, timeout=40)
            subprocess.run([str(binary)], check=True, timeout=15)
    subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover',
                    '-s', str(root / 'tests'), '-p', 'test_*.py', '-v'],
                   check=True, timeout=60)
    if checked_dependencies(root) != before:
        raise ValueError('Dependencies changed during test')


def export_snapshot(output, root=ROOT, public=False):
    output = output.resolve()
    if output.exists():
        raise ValueError('Output already exists; choose a new dated filename')
    entries = checked_dependencies(root)
    for relative in PROJECT_FILES:
        path = regular_file(root, relative)
        entries[relative] = path.read_bytes()
    # Read all bytes before writing, verify source stability a second time.
    for relative, data in entries.items():
        if regular_file(root, relative).read_bytes() != data:
            raise ValueError('Source changed while exporting: ' + relative)
    if public:
        import posixpath
        import re
        from urllib.parse import unquote
        # A published example must not authorize writes to the author's tester.
        entries['device-profile.json'] = entries['device-profile.example.json']
        # Local histories/evidence refer to private paths and old board state.
        for name in ('docs/ACCEPTANCE.md', 'docs/HANDOFF.md', 'docs/PROJECT_LAYOUT.md',
                     'docs/RECHECK_20260918.md', 'USB_RESTART_PLAN.md', 'NVS_RECOVERY_PLAN.md'):
            guide = 'GETTING_STARTED.md' if name.startswith('docs/') else 'docs/GETTING_STARTED.md'
            entries[name] = ('# Local workspace record\n\n'
                'Private run history is excluded from this public snapshot.\n'
                'Source tests/build do not confirm any installed firmware or physical signals.\n'
                'Use the [setup guide](' + guide + ') and record your own board identity,\n'
                'wiring, image hash, operations and verified results before live work.\n').encode()
        entries['docs/LEGACY_LATCH02.md'] = (
            '# Legacy LATCH-02 compatibility\n\n'
            'RelayResetBench.h and relay_main.cpp are retained for a separate legacy firmware.\n'
            'The default PlatformIO environment builds main.cpp only.\n\n'
            'Legacy commands: identity, status, off, on, bypass:<1-5000ms>, release.\n'
            'Aliases: function wdt status/on/off/timed <ms>. OFF is latched until ON or reboot.\n'
            'GPIO13 controls the relay; GPIO33 observes EN. JSON type wdt_pin is described\n'
            'in [TELEMETRY](TELEMETRY.md). Identity/lease workflows are not main.cpp commands.\n'
            'Use tester_control.py only with positively identified legacy firmware;\n'
            'use CurrentProtocol for main.cpp. Do not infer wiring or board identity from COM.\n'
            'Private historical owner IDs and hardware logs are excluded from this snapshot.\n').encode()
        # Public docs must not link to excluded Del/runtime or parent-workspace files.
        for name, data in list(entries.items()):
            if not name.endswith('.md'): continue
            def portable_link(match):
                label, target = match.groups()
                clean = target.strip('<>').split('#', 1)[0]
                if not clean or re.match(r'^[a-zA-Z][\w+.-]*:', clean): return match.group(0)
                relative = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(clean)))
                return match.group(0) if relative in entries else label + ' (local workspace reference)'
            entries[name] = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', portable_link, data.decode('utf-8-sig')).encode('utf-8')
        local = root/'src/secrets.h'
        if local.exists():
            tokens = re.findall(rb'WIFI_(?:SSID|PASSWORD)\s*=\s*"((?:\\.|[^"\\])*)"', local.read_bytes())
            for token in tokens:
                if token and any(token in data for data in entries.values()):
                    raise ValueError('Local Wi-Fi value found in public export; export stopped')
        if any(name.endswith('/secrets.h') or name.startswith(('Del/', '.work/', '.sdk/', '.pio/')) for name in entries):
            raise ValueError('Private/runtime file in public export')
    manifest = {
        'kind': 'frozen-transfer-snapshot-not-active-source',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'hardware': 'NOT_RUN', 'source_migration': 'COMPLETE',
        'public_snapshot': public,
        'files': {name: digest(data) for name, data in sorted(entries.items())},
    }
    # Exclusive creation never overwrites an earlier export or active source.
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for relative, data in sorted(entries.items()):
            archive.writestr(relative, data)
        archive.writestr('TRANSFER_MANIFEST.json', json.dumps(manifest, indent=2))
    return {'path': str(output), 'sha256': digest(output.read_bytes()),
            'files': len(entries), 'hardware': 'NOT_RUN'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'test', 'export'))
    parser.add_argument('--output', type=Path, help='New ZIP path; export only')
    parser.add_argument('--public', action='store_true', help='Export GitHub snapshot with example board profile and no local run history')
    args = parser.parse_args()
    if (args.action == 'export') != (args.output is not None):
        parser.error('Only export requires --output')
    if args.public and args.action != 'export':
        parser.error('--public requires export')
    try:
        if args.action == 'export':
            result = export_snapshot(args.output, public=args.public)
        else:
            entries = checked_dependencies()
            if args.action == 'test':
                run_tests()
            result = {'status': 'PASS', 'action': args.action,
                      'dependencies': len(entries), 'hardware': 'NOT_RUN'}
        print(json.dumps(result))
        return 0
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'FAIL', 'error': str(error)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
