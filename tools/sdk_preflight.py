"""Read-only SDK manifest preflight; never runs PlatformIO or installs packages."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    'framework-arduinoespressif32': '3.20017.241212+sha.dcc1105b',
    'tool-esptoolpy': '2.41100.260830',
    'toolchain-xtensa-esp32': '8.4.0+2021r2-patch5',
    'tool-scons': '4.40801.0',
}


def main():
    platform = json.loads((ROOT/'.sdk/platforms/espressif32/platform.json').read_text())
    if platform['version'] != '7.0.1': raise ValueError('Platform mismatch')
    for name, version in EXPECTED.items():
        path = ROOT/'.sdk/packages'/name
        package = json.loads((path/'package.json').read_text())
        metadata = json.loads((path/'.piopm').read_text())
        if package['name'] != name or package['version'] != version:
            raise ValueError('SDK version mismatch: '+name)
        if metadata['name'] != name or metadata['version'] != version:
            raise ValueError('SDK metadata mismatch: '+name)
    for relative in ['toolchain-xtensa-esp32/bin/xtensa-esp32-elf-g++.exe',
                     'tool-scons/scons.py', 'tool-esptoolpy/esptool/__init__.py',
                     'framework-arduinoespressif32/cores/esp32/Arduino.h']:
        if not (ROOT/'.sdk/packages'/relative).is_file(): raise ValueError('Incomplete SDK: '+relative)
    print(json.dumps({'status': 'PASS', 'platform': '7.0.1', 'packages': EXPECTED, 'com': 'NOT_OPENED'}))


if __name__ == '__main__': main()
