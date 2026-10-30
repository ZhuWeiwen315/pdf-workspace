"""Copy installed dependency license notices into a Windows build output.

Run only from the build environment. This does not assign a license to this app.
"""
from importlib import metadata
from pathlib import Path
import shutil
import sys


def collect(destination):
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    index = []
    for dist in sorted(metadata.distributions(), key=lambda d: d.metadata['Name'].lower()):
        name = dist.metadata['Name']
        count = 0
        for relative in dist.files or []:
            value = str(relative).replace('\\', '/')
            base = Path(value).name.lower()
            if '/licenses/' not in value.lower() and not base.startswith(('license', 'copying', 'notice')):
                continue
            source = dist.locate_file(relative)
            if not source.is_file() or source.suffix.lower() in ('.py', '.pyc', '.so', '.dll', '.exe'):
                continue
            if '..' in Path(value).parts:
                continue
            target = root / name / value
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            count += 1
        index.append(f'{name}=={dist.version}: {count} notice files')
    # TkDnD carries its notice in the distributed Tcl source, outside dist-info.
    import tkinterdnd2
    tkdnd = Path(tkinterdnd2.__file__).parent / 'tkdnd'
    notices = []
    for source in sorted(tkdnd.rglob('tkdnd.tcl')):
        text = source.read_text(encoding='utf-8', errors='replace')
        header = text.split('package require', 1)[0]
        if 'copyright' in header.lower() and header not in notices:
            notices.append(header)
    if notices:
        (root / 'TkDnD-notices.txt').write_text('\n\n'.join(notices), encoding='utf-8')
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.is_file():
        shutil.copyfile(python_license, root / 'Python-LICENSE.txt')
    (root / 'INDEX.txt').write_text('\n'.join(index) + '\n', encoding='utf-8')
    # Fail a binary build if its PDFium notices were not retained.
    pdfium_notices = list((root / 'pypdfium2').rglob('*pdfium*'))
    if not any(p.is_file() for p in pdfium_notices):
        raise RuntimeError('PDFium dependency notices missing. Do not distribute this build until reviewed.')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python collect_licenses.py OUTPUT_DIRECTORY')
    collect(sys.argv[1])
