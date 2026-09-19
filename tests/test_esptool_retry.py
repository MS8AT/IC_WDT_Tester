"""Run the real cached esptool failure path, without Serial or hardware."""
from pathlib import Path
import io
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT/'.sdk/packages/tool-esptoolpy'
sys.path.insert(0, str(ROOT/'tools'))
import flash_tester


@unittest.skipUnless(TOOL.exists(), 'SDK contract test requires prepared local SDK')
class NativeRetryTest(unittest.TestCase):
    def test_native_serial_error_does_not_reconnect_or_retry(self):
        sys.path.insert(0, str(TOOL/'_contrib'))
        sys.path.insert(0, str(TOOL))
        from esptool.cmds import write_flash
        from serial import SerialException

        class Stub:
            WRITE_FLASH_ATTEMPTS = 2
            CHIP_NAME = 'ESP32'
            IS_STUB = True
            secure_download_mode = True
            FLASH_SECTOR_SIZE = 4096
            calls = 0
            def flash_begin(self, *args, **kwargs):
                self.calls += 1
                raise SerialException('injected disconnect')
            @property
            def _port(self):
                self.fail_reconnect = True
                raise AssertionError('Reconnect attempted')

        original = Stub()
        flash_tester.disable_write_retry(original)
        recreated = Stub()
        self.assertEqual(recreated.WRITE_FLASH_ATTEMPTS, 1)
        data = io.BytesIO(b'test')
        args = SimpleNamespace(compress=False, no_compress=True, no_stub=False,
            force=False, encrypt=False, encrypt_files=None, flash_size='keep',
            erase_all=False, addr_filename=[(0x10000, data)])
        with self.assertRaisesRegex(SerialException, 'injected disconnect'):
            write_flash(recreated, args)
        self.assertEqual(recreated.calls, 1)


if __name__ == '__main__': unittest.main()
