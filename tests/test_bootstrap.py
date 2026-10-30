import ast
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import bootstrap as boot


def info(version=(3,13,2),path='python.exe',bits=64,tk=True,platform='win-amd64'):
    return dict(version=list(version),path=path,base=path,bits=bits,tk=tk,platform=platform)

class BootstrapTests(unittest.TestCase):
    def test_python39_rejected(self):self.assertFalse(boot.is_compatible(info((3,9,13))))
    def test_supported_versions(self):
        for minor in [10,11,12,13,14]:self.assertTrue(boot.is_compatible(info((3,minor,0))))
    def test_arch_and_tk(self):
        self.assertFalse(boot.is_compatible(info(bits=32)))
        self.assertFalse(boot.is_compatible(info(tk=False)))
        self.assertFalse(boot.is_compatible(info(platform='win-arm64')))
    def test_preference(self):
        versions=[info((3,n,0)) for n in [10,14,12,13]]
        self.assertEqual(sorted(versions,key=boot.rank)[0]['version'],[3,13,0])
    def test_launcher_paths_with_spaces(self):
        output=' -V:3.13 * C:\\Program Files\\Python313\\python.exe\n -V:3.9 C:\\Python39\\python.exe\n'
        self.assertEqual(boot.parse_launcher_paths(output),[r'C:\Program Files\Python313\python.exe',r'C:\Python39\python.exe'])
    def test_launcher_quoted(self):
        self.assertEqual(boot.parse_launcher_paths(' -3.12 "C:\\Python 312\\python.exe"'),[r'C:\Python 312\python.exe'])
    def test_old_env_not_touched(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);old=root/'.venv';old.mkdir();sentinel=old/'keep.txt';sentinel.write_text('user data')
            python,dest=boot.choose_environment(root,[info((3,9,0),str(old/'python.exe'))],[info(path='new.exe')])
            self.assertEqual(python,Path('new.exe'));self.assertEqual(dest,root/'.venv-py313')
            self.assertEqual(sentinel.read_text(),'user data');self.assertFalse(dest.exists())
    def test_corrupt_target_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'.venv-py313').mkdir()
            _,dest=boot.choose_environment(root,[],[info()])
            self.assertEqual(dest,root/'.venv-py313-2')
    def test_compatible_env_reused(self):
        root=Path('sample');python,dest=boot.choose_environment(root,[info(path='existing.exe')],[info(path='base.exe')])
        self.assertEqual(python,Path('existing.exe'));self.assertIsNone(dest)
    def test_no_compatible(self):self.assertEqual(boot.choose_environment(Path('sample'),[],[info((3,9,0))]),(None,None))
    def test_pip_versions(self):
        self.assertTrue(boot.pip_needs_upgrade('20.2.3'));self.assertTrue(boot.pip_needs_upgrade(None))
        self.assertFalse(boot.pip_needs_upgrade('23.3'));self.assertFalse(boot.pip_needs_upgrade('26.0.1'))
    def test_requirements(self):
        pins=boot.parse_requirements(Path(boot.__file__).parent/'requirements.txt')
        self.assertEqual(pins['pypdf'],'6.10.0');self.assertEqual(pins['pdfplumber'],'0.11.9')
    def test_python38_syntax(self):ast.parse(Path(boot.__file__).read_text(),feature_version=(3,8))
    def test_build_separate_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            _,dest=boot.choose_environment(Path(temp),[],[info()],build=True)
            self.assertEqual(dest.name,'.build-env-py313')
    def test_diagnose_never_installs(self):
        with patch.object(boot,'is_windows',return_value=True),patch.object(boot,'environment_paths',return_value=[]),patch.object(boot,'candidates',return_value=['base']),patch.object(boot,'probe',return_value=info()),patch.object(boot,'checked') as execute,redirect_stdout(StringIO()):
            self.assertEqual(boot.main(['--diagnose']),0);execute.assert_not_called()
    def test_missing_python_stops_before_install(self):
        with patch.object(boot,'is_windows',return_value=True),patch.object(boot,'environment_paths',return_value=[]),patch.object(boot,'candidates',return_value=['old']),patch.object(boot,'probe',return_value=info((3,9,13))),patch.object(boot,'checked') as execute,redirect_stdout(StringIO()):
            self.assertEqual(boot.main([]),2);execute.assert_not_called()

if __name__=='__main__':unittest.main()
