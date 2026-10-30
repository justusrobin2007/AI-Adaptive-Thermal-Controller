@echo off
setlocal
cd /d "%~dp0"
title Stop AI Adaptive Thermal Controller

echo =====================================================================
echo  Stopping AI Adaptive Thermal Controller & Web Dashboard...
echo =====================================================================

:: Kill any lingering dashboard window, python worker or hardware monitor
taskkill /fi "WINDOWTITLE eq AI Thermal Controller - Web Dashboard*" /t /f >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*streamlit*dashboard.py*' -or $_.CommandLine -like '*main.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
taskkill /im LibreHardwareMonitor.exe /f >nul 2>&1

:: Restore default Windows Balanced power scheme & 100% CPU boost state
powercfg /setactive 381b4222-f694-41f0-9685-ff5bb260df2e >nul 2>&1
powercfg /setacvalueindex SCHEME_CURRENT SUB_PROCESSOR PROCTHROTTLEMAX 100 >nul 2>&1
powercfg /setdcvalueindex SCHEME_CURRENT SUB_PROCESSOR PROCTHROTTLEMAX 100 >nul 2>&1
powercfg /setactive SCHEME_CURRENT >nul 2>&1

echo [OK] Dashboard and background services stopped.
echo [OK] Default Windows Balanced power scheme and 100%% CPU state restored.
echo =====================================================================
echo.
ping -n 3 127.0.0.1 >nul
