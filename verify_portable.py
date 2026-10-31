"""Windows CI relocation test: copy ONLY the EXE; no Python on child PATH."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def isolated_environment():
    env={key:value for key,value in os.environ.items()
         if not key.upper().startswith(('PYTHON','CONDA','_CE_'))
         and key.upper() not in ('TCL_LIBRARY','TK_LIBRARY','VIRTUAL_ENV')}
    windows=env.get('SystemRoot',env.get('SYSTEMROOT',r'C:\Windows'))
    env['PATH']=str(Path(windows)/'System32')+os.pathsep+windows
    return env


def verify(exe, reports):
    exe=Path(exe).resolve();reports=Path(reports).resolve()
    reports.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(exe.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='portable_relocation_') as temporary:
        root=Path(temporary);cwd=root/'unrelated_cwd';cwd.mkdir()
        for index,name in enumerate(('Desktop Copy','中文路径 与空格')):
            target=root/name;target.mkdir();moved=target/'PDFWorkspace.exe'
            shutil.copyfile(exe,moved)
            assert list(target.iterdir()) == [moved], 'Test must copy only EXE'
            assert hashlib.sha256(moved.read_bytes()).hexdigest() == digest
            report=reports/('relocated-%d.json'%index)
            process=subprocess.run([str(moved),'--self-test',str(report)],cwd=cwd,
                                   env=isolated_environment(),timeout=180)
            if process.returncode or not report.is_file():
                raise RuntimeError('Frozen self-test failed or no report: '+str(report))
            result=json.loads(report.read_text(encoding='utf-8'))
            if result.get('ok') is not True:raise RuntimeError(result)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('exe');parser.add_argument('reports')
    args=parser.parse_args();verify(args.exe,args.reports)
