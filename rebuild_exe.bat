@echo off
call "%~dp0start.bat" --fresh-build
if errorlevel 1 exit /b 1
pause
