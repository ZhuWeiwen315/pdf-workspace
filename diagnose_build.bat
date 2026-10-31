@echo off
setlocal
cd /d "%~dp0"
call "%~dp0start.bat" --diagnose-build
echo.
echo === Existing build environment origins ===
for /d %%D in (.build-env*) do if exist "%%D\pyvenv.cfg" (echo --- %%D & type "%%D\pyvenv.cfg")
echo.
echo === Bundled Tkinter and Tcl/Tk files ===
dir /s /b "dist\PDFWorkspace\*tkinter*.pyd" "dist\PDFWorkspace\tcl*.dll" "dist\PDFWorkspace\tk*.dll" "dist\PDFWorkspace\init.tcl" "dist\PDFWorkspace\tk.tcl" 2>nul
echo.
echo This diagnostic does not install packages or delete files.
pause
