"""Negative export/check contracts, without hardware or network."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('tester_project', Path(__file__).resolve().parents[1] / 'tools/project.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'ESP32/c_IC_WDT_Tester'
        self.root.mkdir(parents=True)
        self.dependency = self.root / 'src/RelayResetBench.h'
        self.dependency.parent.mkdir(parents=True)
        self.dependency.write_bytes(b'fixture only')
        for relative in m.PROJECT_FILES:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('fixture', encoding='utf-8')
        self.lock = {'schema_version': 2, 'dependencies': [{
            'path': 'src/RelayResetBench.h',
            'sha256': m.digest(self.dependency.read_bytes())}]}
        self.write_lock()

    def write_lock(self):
        (self.root / 'dependency-lock.json').write_text(json.dumps(self.lock), encoding='utf-8')

    def test_drift_rejected(self):
        self.dependency.write_bytes(b'different revision')
        with self.assertRaisesRegex(ValueError, 'changed'):
            m.checked_dependencies(self.root)

    def test_missing_rejected(self):
        self.dependency.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing'):
            m.checked_dependencies(self.root)

    def test_traversal_rejected(self):
        self.lock['dependencies'][0]['path'] = '../secret'
        self.write_lock()
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            m.checked_dependencies(self.root)

    def test_duplicate_rejected(self):
        self.lock['dependencies'].append(self.lock['dependencies'][0])
        self.write_lock()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            m.checked_dependencies(self.root)

    def test_export_allowlist_hashes_and_no_overwrite(self):
        (self.root / 'unexpected.secret.env').write_text('fixture secret', encoding='utf-8')
        output = self.base / 'transfer.zip'
        m.export_snapshot(output, self.root)
        with zipfile.ZipFile(output) as archive:
            manifest = json.loads(archive.read('TRANSFER_MANIFEST.json'))
            self.assertEqual(manifest['hardware'], 'NOT_RUN')
            self.assertNotIn('unexpected.secret.env', archive.namelist())
            self.assertNotIn('src/secrets.h', archive.namelist())
            self.assertIn('src/secrets.example.h', archive.namelist())
            for name, expected in manifest['files'].items():
                self.assertEqual(m.digest(archive.read(name)), expected)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            m.export_snapshot(output, self.root)

    def test_public_export_excludes_credentials_and_local_history(self):
        (self.root/'src/secrets.h').write_text('const char* WIFI_PASSWORD = "private-test-value-918";')
        (self.root/'README.md').write_text('[Local](.work/private.json) [Guide](docs/GITHUB.md)')
        output = self.base/'public.zip'
        m.export_snapshot(output, self.root, public=True)
        with zipfile.ZipFile(output) as archive:
            self.assertNotIn('src/secrets.h', archive.namelist())
            self.assertEqual(archive.read('device-profile.json'), archive.read('device-profile.example.json'))
            self.assertNotIn(b'.work/private.json', archive.read('README.md'))
            self.assertIn(b'[Guide](docs/GITHUB.md)', archive.read('README.md'))
            self.assertIn(b'Private run history is excluded', archive.read('docs/ACCEPTANCE.md'))
            manifest = json.loads(archive.read('TRANSFER_MANIFEST.json'))
            self.assertTrue(manifest['public_snapshot'])
            for name, expected in manifest['files'].items():
                self.assertEqual(m.digest(archive.read(name)), expected)
                self.assertNotIn(b'private-test-value-918', archive.read(name))
        (self.root/'README.md').write_text('accidental private-test-value-918')
        with self.assertRaisesRegex(ValueError, 'Wi-Fi value'):
            m.export_snapshot(self.base/'leak.zip', self.root, public=True)
        self.assertFalse((self.base/'leak.zip').exists())


if __name__ == '__main__':
    unittest.main()
