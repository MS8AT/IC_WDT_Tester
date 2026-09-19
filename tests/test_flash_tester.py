import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import flash_tester as m


class FlashGuards(unittest.TestCase):
    def test_flash_voltage_strap_and_overrides(self):
        self.assertEqual(m.validate_flash_voltage(0x03, 0x431, 0x3a00000), '3.3V')
        with self.assertRaises(RuntimeError):
            m.validate_flash_voltage(0x23, 0x431, 0x3a00000)  # observed tester state
        self.assertEqual(m.validate_flash_voltage(0x23, 0x1c000, 0), '3.3V')
        for efuse in (0x10000, 0x14000, 0x18000):
            with self.assertRaises(RuntimeError): m.validate_flash_voltage(0, efuse, 0)
        with self.assertRaises(RuntimeError): m.validate_flash_voltage(0, 0, 1 << 22)

    def test_factory_identity_exact(self):
        expected = dict(chip_model='ESP32-D0WDQ6', chip_revision='v1.0', base_mac='02:00:00:00:00:01')
        m.validate_rom('ESP32-D0WDQ6 (revision v1.0)', expected['base_mac'], expected)
        for description, mac in [('ESP32-S3', expected['base_mac']), ('ESP32-D0WDQ6 (revision v1.0)', '02:00:00:00:00:02')]:
            with self.assertRaises(RuntimeError): m.validate_rom(description, mac, expected)

    def test_backup_and_partition_match(self):
        data = bytearray(4194304)
        data[0x1000:0x1004] = b'boot'; data[0x8000:0x8004] = b'part'
        images = {'bootloader.bin': b'boot', 'partitions.bin': b'part', 'firmware.bin': b'app'}
        m.validate_backup(data, images)
        with self.assertRaises(RuntimeError): m.validate_backup(data[:-1], images)
        data[0x8000] ^= 1
        with self.assertRaises(RuntimeError): m.validate_backup(data, images)

    def test_no_backup_reads_only_boot_and_table(self):
        images = {'bootloader.bin': b'boot', 'partitions.bin': b'part', 'firmware.bin': b'app'}
        class Device:
            reads = []
            def read_flash(self, offset, length):
                self.reads.append((offset, length))
                return {0x1000: b'boot', 0x8000: b'part'}[offset]
        device = Device()
        installed = m.read_layout(device.read_flash, images)
        m.validate_layout(installed, images)
        self.assertEqual(device.reads, [(0x1000, 4), (0x8000, 4)])
        for name in ('bootloader.bin', 'partitions.bin'):
            with self.assertRaises(RuntimeError): m.validate_layout({**installed, name: b'bad'}, images)
        with self.assertRaises(RuntimeError):
            m.validate_layout(installed, {**images, 'firmware.bin': b'x'*(0x140000+1)})

    def test_default_full_backup_disabled(self):
        self.assertFalse(m.backup_setting(m.ROOT/'flash-settings.json'))


if __name__ == '__main__': unittest.main()
