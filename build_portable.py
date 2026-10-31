"""Maintainer build only. User runs resulting EXE, never this script."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
from collect_licenses import collect

ROOT = Path(__file__).resolve().parent


def validate_builder():
    if sys.platform != 'win32' or struct.calcsize('P') != 8:
        raise RuntimeError('Build on Windows x64, not by cross-compilation.')
    if sys.version_info[:3] != (3,12,10):
        raise RuntimeError('Use pinned CPython 3.12.10 x64 for this build lock.')
    if (Path(sys.base_prefix)/'conda-meta').exists():
        raise RuntimeError('Use setup-python CPython, not a Conda-derived environment.')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    args=parser.parse_args(); destination=Path(args.output).resolve()
    validate_builder()
    if destination.exists():
        raise FileExistsError('Output must be a NEW directory: '+str(destination))
    destination.mkdir(parents=True,exist_ok=False)
    subprocess.run([sys.executable,'-m','pip','check'],check=True)
    with tempfile.TemporaryDirectory(prefix='pdfworkspace_build_') as temporary:
        stage=Path(temporary); notices=stage/'THIRD_PARTY_LICENSES'; collect(notices)
        shutil.copyfile(ROOT/'THIRD_PARTY_NOTICES.txt',notices/'PROJECT-DEPENDENCY-NOTICES.txt')
        if (ROOT/'LICENSE').is_file():shutil.copyfile(ROOT/'LICENSE',notices/'PROJECT-LICENSE.txt')
        # CPython's Tcl/Tk runtime notices are not Python package dist-info files.
        for license_file in (Path(sys.base_prefix)/'tcl').rglob('license*'):
            if license_file.is_file():
                relative=license_file.relative_to(Path(sys.base_prefix)/'tcl')
                target=notices/'Tcl-Tk'/relative;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(license_file,target)
        command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--windowed','--noupx',
                 '--name','PDFWorkspace','--distpath',str(stage/'dist'),'--workpath',str(stage/'work'),
                 '--specpath',str(stage),'--paths',str(ROOT),'--add-data',str(notices)+os.pathsep+'THIRD_PARTY_LICENSES']
        for package in ('tkinterdnd2','pypdfium2','pypdfium2_raw','docx','reportlab'):
            command.extend(['--collect-all',package])
        command.append(str(ROOT/'portable_entry.py'))
        with (destination/'build-log.txt').open('w',encoding='utf-8') as log:
            result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        warnings=stage/'work'/'PDFWorkspace'/'warn-PDFWorkspace.txt'
        if warnings.exists():shutil.copyfile(warnings,destination/'build-warnings.txt')
        result.check_returncode()
        exe=destination/'PDFWorkspace.exe';shutil.copyfile(stage/'dist'/'PDFWorkspace.exe',exe)
        frozen=subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True)
        (destination/'environment.txt').write_text(frozen,encoding='utf-8')
        manifest={'python':sys.version,'platform':platform.platform(),'commit':os.environ.get('GITHUB_SHA','local'),
                  'sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),
                  'lock_sha256':hashlib.sha256((ROOT/'requirements-windows-build.lock').read_bytes()).hexdigest(),
                  'code_signed':False}
        (destination/'build-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(destination)

if __name__=='__main__':main()
