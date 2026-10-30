@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 bootstrap.py %*
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo No Python found. Install official Python 3.13 or 3.12 x64 with Tcl/Tk and Python Launcher.
        echo https://www.python.org/downloads/windows/
        pause
        exit /b 2
    )
    python bootstrap.py %*
)
if errorlevel 1 (
    echo.
    if "%~1"=="--diagnose" exit /b 1
    echo Startup stopped. Keep the messages above; no old environment was deleted.
    pause
    exit /b 1
)
exit /b 0
