@echo off
title FocusLock Launcher

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

:: Free port 8765 if an old process was lingering
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8765 ^| findstr LISTENING 2^>nul') do (
    taskkill /f /pid %%a >nul 2>&1
)

:: Terminate any stale orphaned main.py instance before starting
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*main.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

:: Launch FocusLock in pure windowed mode
cd /d "%~dp0app"
start "" pythonw main.py
exit
