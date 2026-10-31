"""Frozen entry point: no installer, downloads, system Python or mutable app folder."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import shutil
import sys
import traceback


def resource_root():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))


def export_licenses(destination):
    source = resource_root() / 'THIRD_PARTY_LICENSES'
    if not (source / 'INDEX.txt').is_file():
        raise RuntimeError('Bundled third-party licenses are missing')
    # Never merge into or overwrite a user directory.
    shutil.copytree(source, Path(destination))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', metavar='REPORT_JSON')
    parser.add_argument('--export-licenses', metavar='NEW_DIRECTORY')
    args = parser.parse_args(argv)
    if args.export_licenses:
        export_licenses(args.export_licenses)
        return 0
    if args.self_test:
        from portable_smoke import run_self_test
        return run_self_test(Path(args.self_test))
    try:
        from app import App
        from tkinterdnd2 import TkinterDnD
        from tkinter import filedialog, messagebox
        root = TkinterDnD.Tk()
        App(root)
        # Embedded notices remain available even after moving the single EXE.
        def licenses():
            parent = filedialog.askdirectory(title='选择许可证导出位置（将新建子文件夹）')
            if not parent:
                return
            import tempfile
            directory = Path(tempfile.mkdtemp(prefix='PDFWorkspace_licenses_', dir=parent))
            directory.rmdir()  # Empty newly-created reservation only, never user data.
            try:
                export_licenses(directory)
                messagebox.showinfo('许可证', '已导出第三方许可证：\n' + str(directory))
            except Exception as exc:
                messagebox.showerror('无法导出许可证', str(exc))
        import tkinter as tk
        menu = tk.Menu(root)
        help_menu = tk.Menu(menu, tearoff=0)
        help_menu.add_command(label='导出第三方许可证', command=licenses)
        menu.add_cascade(label='关于', menu=help_menu)
        root.config(menu=menu)
        root.mainloop()
        return 0
    except Exception:
        detail = traceback.format_exc()
        # Startup-only error; no document content, passwords or operation logs.
        if sys.platform == 'win32':
            ctypes.windll.user32.MessageBoxW(None, '程序启动失败。请保留此信息，不要下载随机 DLL。\n\n' + detail,
                                            'PDF 工作台', 0x10)
        elif sys.stderr:
            print(detail, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
