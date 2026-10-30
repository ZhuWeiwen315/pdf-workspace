@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m venv .build-env
) else (
    python -m venv .build-env
)
if errorlevel 1 goto failed
".build-env\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto failed
".build-env\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --onedir --name PDFWorkspace --collect-all tkinterdnd2 --collect-all pypdfium2 --collect-all pypdfium2_raw --collect-all docx --collect-all reportlab app.py
if errorlevel 1 goto failed
echo.
".build-env\Scripts\python.exe" collect_licenses.py "dist\PDFWorkspace\THIRD_PARTY_LICENSES"
if errorlevel 1 goto failed
echo Build finished: dist\PDFWorkspace\PDFWorkspace.exe
echo Keep the ENTIRE dist\PDFWorkspace folder together.
pause
exit /b 0
:failed
echo Build failed. Please keep the full error output.
pause
exit /b 1
