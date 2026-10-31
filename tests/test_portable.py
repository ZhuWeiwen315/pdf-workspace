import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import portable_entry
import portable_smoke
import verify_portable


class PortableTests(unittest.TestCase):
    def test_fourteen_pdf_smoke_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            checks=portable_smoke.exercise_pdf_features(Path(folder))
            self.assertEqual(len(checks),15)
            self.assertIn('source_unchanged',checks)
    def test_embedded_notices_export(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'THIRD_PARTY_LICENSES';source.mkdir()
            (source/'INDEX.txt').write_text('fixture')
            with patch.object(portable_entry,'resource_root',return_value=root):
                portable_entry.export_licenses(root/'out')
                self.assertEqual((root/'out'/'INDEX.txt').read_text(),'fixture')
    def test_export_never_overwrites_existing_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'THIRD_PARTY_LICENSES';source.mkdir()
            (source/'INDEX.txt').write_text('fixture');output=root/'out';output.mkdir()
            marker=output/'keep';marker.write_text('original')
            with patch.object(portable_entry,'resource_root',return_value=root):
                with self.assertRaises(FileExistsError):portable_entry.export_licenses(output)
            self.assertEqual(marker.read_text(),'original')
    def test_missing_notices_error(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(portable_entry,'resource_root',return_value=Path(folder)):
            with self.assertRaises(RuntimeError):portable_entry.export_licenses(Path(folder)/'out')
    def test_environment_does_not_depend_on_python_or_conda(self):
        with patch.dict(os.environ,{'SystemRoot':r'C:\Windows','PYTHONHOME':'bad','PYTHONPATH':'bad','CONDA_PREFIX':'bad','TCL_LIBRARY':'bad','TK_LIBRARY':'bad','VIRTUAL_ENV':'bad','PATH':'bad'},clear=True):
            env=verify_portable.isolated_environment()
            for key in ('PYTHONHOME','PYTHONPATH','CONDA_PREFIX','TCL_LIBRARY','TK_LIBRARY','VIRTUAL_ENV'):
                self.assertNotIn(key,env)
            self.assertNotIn('bad',env['PATH'])
    def test_self_test_failures_report_nonzero_without_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            report=Path(folder)/'result.json'
            with patch('tkinterdnd2.TkinterDnD.Tk',side_effect=RuntimeError('synthetic tk failure')):
                self.assertEqual(portable_smoke.run_self_test(report),1)
                data=json.loads(report.read_text());self.assertFalse(data['ok'])
                self.assertIn('synthetic tk failure',data['error'])
                with self.assertRaises(FileExistsError):portable_smoke.run_self_test(report)
    def test_build_lock_has_hash_for_every_pin(self):
        lock=Path(__file__).resolve().parent.parent/'requirements-windows-build.lock'
        for line in lock.read_text().splitlines():
            if not line.startswith('#'):
                self.assertRegex(line,r'^\S+==\S+ --hash=sha256:[0-9a-f]{64}$')

if __name__=='__main__':unittest.main()
