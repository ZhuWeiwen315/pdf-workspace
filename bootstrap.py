"""Windows launcher, intentionally compatible with Python 3.8+ for diagnostics.

Selects a supported 64-bit interpreter before installing anything. Existing
virtual environments are never removed or overwritten. No passwords are logged.
"""
from __future__ import print_function
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

MIN_VERSION = (3, 10)
PREFERRED = [(3, 13), (3, 12), (3, 11), (3, 10)]
ROOT = Path(__file__).resolve().parent
PROBE = r'''
import json,sys,struct,sysconfig
from pathlib import Path
info={'version':list(sys.version_info[:3]),'bits':struct.calcsize('P')*8,'platform':sysconfig.get_platform(),'executable':sys.executable,'base':getattr(sys,'_base_executable',sys.executable),'tk':False}
info['base_prefix']=sys.base_prefix
info['conda']=(Path(sys.prefix,'conda-meta').is_dir() or Path(sys.base_prefix,'conda-meta').is_dir() or 'conda' in sys.version.lower() or 'anaconda' in sys.version.lower())
try:
 import tkinter,venv,_tkinter
 info['tkinter_binary']=_tkinter.__file__
 info['tcl_library']=tkinter.Tcl().eval('info library')
 info['tk']=True
except Exception as e: info['tk_error']=str(e)
try:
 import pip
 info['pip']=pip.__version__
except Exception: info['pip']=None
print(json.dumps(info))
'''
IMPORTS = ('pypdf','tkinterdnd2','cryptography','pdfplumber','pdfminer','docx','pypdfium2','reportlab','PIL')


def probe(executable):
    try:
        result = subprocess.run([str(executable), '-I', '-c', PROBE], capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=15)
        if result.returncode != 0:
            return None
        info = json.loads(result.stdout.strip().splitlines()[-1])
        info['path'] = str(executable)
        return info
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return None


def is_compatible(info):
    version = tuple(info.get('version', [])[:2])
    return (len(version) == 2 and version[0] == 3 and version >= MIN_VERSION
            and info.get('bits') == 64 and info.get('tk') is True
            and info.get('platform') == 'win-amd64')


def rank(info):
    version = tuple(info['version'][:2])
    return (PREFERRED.index(version) if version in PREFERRED else len(PREFERRED),
            -version[0], -version[1])


def parse_launcher_paths(output):
    paths = []
    for line in output.splitlines():
        match = re.search(r'((?:[A-Za-z]:[\\/]|\\\\).+?python(?:w)?\.exe)\s*"?\s*$', line, re.I)
        if match:
            path = match.group(1).strip('"')
            if path.lower().endswith('pythonw.exe'):
                path = path[:-11] + 'python.exe'
            paths.append(path)
    return paths


def registry_paths():
    if os.name != 'nt':
        return []
    import winreg
    result = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, r'SOFTWARE\Python', 0, winreg.KEY_READ | view) as top:
                    companies = [winreg.EnumKey(top,i) for i in range(winreg.QueryInfoKey(top)[0])]
                for company in companies:
                    company_key = 'SOFTWARE\\Python\\' + company
                    with winreg.OpenKey(hive,company_key,0,winreg.KEY_READ | view) as key:
                        tags = [winreg.EnumKey(key,i) for i in range(winreg.QueryInfoKey(key)[0])]
                    for tag in tags:
                        try:
                            with winreg.OpenKey(hive,company_key+'\\'+tag+'\\InstallPath',0,winreg.KEY_READ | view) as key:
                                try: path = winreg.QueryValueEx(key,'ExecutablePath')[0]
                                except OSError: path = str(Path(winreg.QueryValueEx(key,None)[0])/'python.exe')
                                result.append(path)
                        except OSError:
                            continue
            except OSError:
                continue
    return result


def candidates():
    paths = [sys.executable]
    launcher = shutil.which('py')
    if launcher:
        try:
            result = subprocess.run([launcher,'-0p'],capture_output=True,text=True,
                                    encoding='utf-8',errors='replace',timeout=15)
            paths.extend(parse_launcher_paths(result.stdout + '\n' + result.stderr))
        except (OSError,subprocess.TimeoutExpired):
            pass
    paths.extend(registry_paths())
    found = shutil.which('python')
    if found and 'windowsapps' not in found.lower():
        paths.append(found)
    unique = []
    seen = set()
    for path in paths:
        key = os.path.normcase(os.path.abspath(path))
        if key not in seen and Path(path).is_file():
            seen.add(key); unique.append(path)
    return unique


def environment_paths(root, build=False):
    prefix = '.build-env' if build else '.venv'
    roots = [root/prefix] + sorted(root.glob(prefix+'-py*'))
    return [folder/'Scripts'/'python.exe' for folder in roots if (folder/'Scripts'/'python.exe').is_file()]


def choose_environment(root, existing_infos, interpreter_infos, build=False):
    """Return (python_path, create_path_or_None); never delete existing paths."""
    good = [info for info in existing_infos if is_compatible(info) and (not build or not info.get('conda'))]
    if good:
        selected = min(good,key=rank)
        return Path(selected['path']), None
    good = [info for info in interpreter_infos if is_compatible(info) and (not build or not info.get('conda'))]
    if not good:
        return None, None
    selected = min(good,key=rank)
    version = selected['version']
    base = root / (('.build-env-py' if build else '.venv-py') + '%d%d' % (version[0],version[1]))
    destination = base
    counter = 2
    while destination.exists():
        destination = root / (base.name + '-%d' % counter)
        counter += 1
    return Path(selected.get('base') or selected['path']), destination


def parse_requirements(path):
    pins = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)(?:\[[A-Za-z0-9_,.-]+\])?==([^\s;]+)',line)
        if not match:
            raise ValueError('requirements.txt 必须使用明确的 package==version 格式。')
        pins[match.group(1)] = match.group(2)
    return pins


def dependencies_ready(python, pins):
    code = '''import importlib,json,sys\nfrom importlib import metadata\nerrors=[]\npins=json.loads(sys.argv[1])\nfor name,wanted in pins.items():\n try:\n  actual=metadata.version(name)\n  if actual!=wanted: errors.append(name+': '+actual+' != '+wanted)\n except metadata.PackageNotFoundError: errors.append(name+': not installed')\nfor name in json.loads(sys.argv[2]):\n try: importlib.import_module(name)\n except Exception as e: errors.append(name+': '+str(e))\nprint(json.dumps(errors,ensure_ascii=True))\nsys.exit(bool(errors))'''
    result = subprocess.run([str(python),'-I','-c',code,json.dumps(pins),json.dumps(IMPORTS)],
                            capture_output=True,text=True,encoding='utf-8',errors='replace')
    if result.returncode != 0:
        print('依赖尚未就绪：' + result.stdout.strip())
        return False
    check = subprocess.run([str(python),'-m','pip','check'],capture_output=True,text=True,encoding='utf-8',errors='replace')
    if check.returncode:
        print('依赖一致性检查：' + check.stdout.strip() + check.stderr.strip())
    return check.returncode == 0


def pip_needs_upgrade(version):
    numbers = re.match(r'^(\d+)\.(\d+)',str(version or ''))
    return not numbers or tuple(map(int,numbers.groups())) < (23,3)


def checked(command, label):
    print('\n' + label, flush=True)
    result = subprocess.run([str(item) for item in command],cwd=str(ROOT))
    if result.returncode:
        raise RuntimeError(label + '失败（退出码 %d）。' % result.returncode)


def show_info(label, info):
    version = '.'.join(map(str,info['version']))
    verdict = '可用' if is_compatible(info) else '不兼容（需 Python 3.10+、Windows x64、Tcl/Tk）'
    print('%s: Python %s / %s 位 / %s / %s' % (label,version,info['bits'],verdict,info['path']))
    print('  pip: ' + str(info.get('pip') or '未安装'))
    print('  base_prefix: ' + str(info.get('base_prefix','未知')))
    print('  Conda: ' + str(bool(info.get('conda'))))
    print('  _tkinter: ' + str(info.get('tkinter_binary','不可用')))
    print('  Tcl library: ' + str(info.get('tcl_library','不可用')))
    if not info.get('tk'):
        print('  Tcl/Tk error: ' + str(info.get('tk_error','未知')))
        print('  缺少 Tcl/Tk：请在官方 Python 安装器中选择 Modify，启用 Tcl/Tk。pip 无法补装此组件。')


def is_windows():
    return os.name == 'nt'


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    diagnose = '--diagnose' in argv
    build = any(flag in argv for flag in ('--build','--diagnose-build','--fresh-build'))
    fresh_build = '--fresh-build' in argv
    diagnose = diagnose or '--diagnose-build' in argv
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    print('PDF 工作台启动检查（不修改系统默认 Python，不删除旧环境）')
    print('最低 Python 3.10：pdfplumber 0.11.9 依赖 pdfminer.six 20251230，后者不支持 Python 3.9。')
    existing = [info for path in environment_paths(ROOT,build) for info in [probe(path)] if info]
    interpreters = [info for path in candidates() for info in [probe(path)] if info]
    for info in existing: show_info('已有程序环境',info)
    for info in interpreters: show_info('已安装解释器',info)
    if fresh_build:
        print('全新重建：不会复用已有构建环境，全部旧目录保留。')
    python, destination = choose_environment(ROOT,[] if fresh_build else existing,interpreters,build)
    if not is_windows():
        print('此启动器用于 Windows x64；其他平台请按 README 手动运行。')
        return 0 if diagnose else 2
    if build:
        print('构建策略：跳过 Conda 及其派生 venv，保留旧环境；请使用 python.org 的 CPython x64。')
    if python is None:
        print('\n没有找到兼容的 Python，已停止，不会尝试下载依赖。')
        print('请安装官方 Python 3.13 或 3.12 的 Windows 64-bit installer，保留 Tcl/Tk 与 Python Launcher。')
        print('下载：https://www.python.org/downloads/windows/')
        print('无需卸载 Python 3.9，无需删除 .venv；安装完成后再次双击 start.bat。')
        return 2
    print('\n选择：' + str(python))
    print('使用环境：' + str(destination if destination else python.parent.parent))
    if diagnose:
        print('诊断结束：没有创建环境或下载任何内容。')
        return 0
    try:
        if destination is not None:
            destination.mkdir(exist_ok=False)  # Reserve a new directory; never overwrite an existing one.
            checked([python,'-m','venv',destination],'创建新的兼容环境（旧 .venv 保留不动）')
            python = destination/'Scripts'/'python.exe'
        info = probe(python)
        if not info or not is_compatible(info):
            raise RuntimeError('新环境未通过版本/Tcl/Tk 检查；旧环境未删除，请保留此输出。')
        pins = parse_requirements(ROOT/'requirements.txt')
        if not dependencies_ready(python,pins):
            if not info.get('pip'):
                checked([python,'-m','ensurepip','--upgrade'],'初始化 pip')
            if pip_needs_upgrade(info.get('pip')):
                checked([python,'-m','pip','install','--upgrade','pip>=23.3'],'更新此环境内的旧 pip')
            checked([python,'-m','pip','install','-r',ROOT/'requirements.txt'],'安装缺少或版本不符的依赖（首次/升级时联网）')
            if not dependencies_ready(python,pins):
                raise RuntimeError('安装后检查仍未通过，请保留输出；不要反复删除环境。')
        if build:
            checked([python,'-I','-c','import tkinter; r=tkinter.Tk(); r.withdraw(); r.update(); r.destroy()'], '验证实际构建环境的 Tcl/Tk')
            checked([python,'-m','pip','install','--upgrade','pyinstaller'],'准备 Windows 打包工具')
            checked([python,'-m','PyInstaller','--version'],'实际 PyInstaller 版本')
            checked([python,'-m','PyInstaller','--noconfirm','--clean','--windowed','--onedir','--name','PDFWorkspace',
                     '--collect-all','tkinterdnd2','--collect-all','pypdfium2','--collect-all','pypdfium2_raw',
                     '--collect-all','docx','--collect-all','reportlab','app.py'],'构建 Windows 程序')
            checked([python,'collect_licenses.py','dist/PDFWorkspace/THIRD_PARTY_LICENSES'],'收集第三方许可证')
            print('构建完成：dist/PDFWorkspace/PDFWorkspace.exe。请保留整个目录。')
            return 0
        print('\n环境就绪，启动程序。以后依赖齐全时不再执行安装。',flush=True)
        return subprocess.run([str(python),str(ROOT/'app.py')],cwd=str(ROOT)).returncode
    except (OSError,RuntimeError,ValueError) as exc:
        print('\n' + str(exc))
        print('若此时仍提示无匹配版本，再检查网络或镜像同步情况；仅升级 pip 无法让 Python 3.9 满足 Python 3.10 要求。')
        print('本启动器不自动切换镜像，也不删除环境。可运行 diagnose.bat 生成只读诊断。')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
