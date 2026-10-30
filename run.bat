@echo off
setlocal EnableDelayedExpansion

:: =============================================================================
:: AI Adaptive Thermal Controller - Master Launcher
:: =============================================================================
cd /d "%~dp0"
title AI Adaptive Thermal Controller

:: -----------------------------------------------------------------------------
:: 1. Privilege Check (Safe check - No popping loops)
:: -----------------------------------------------------------------------------
net session >nul 2>&1
if %errorLevel% equ 0 (
    set "PRIVILEGE_MSG=[ADMIN MODE] Full hardware powercfg and WMI control active."
) else (
    set "PRIVILEGE_MSG=[STANDARD USER] Running in safe simulation/dry-run mode. (For real hardware control, right-click run.bat and select 'Run as administrator')"
)

cls
echo =====================================================================
echo           AI ADAPTIVE THERMAL CONTROLLER - AUTO LAUNCHER             
echo =====================================================================
echo  %PRIVILEGE_MSG%
echo =====================================================================
echo.

:: -----------------------------------------------------------------------------
:: 2. Detect Python Installation
:: -----------------------------------------------------------------------------
set "PYTHON_CMD="
where python >nul 2>&1
if %errorLevel% equ 0 (
    set "PYTHON_CMD=python"
) else (
    where py >nul 2>&1
    if %errorLevel% equ 0 (
        set "PYTHON_CMD=py"
    )
)

if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python was not found in your system PATH!
    echo.
    echo Please install Python 3.10 or higher from https://www.python.org/
    echo Make sure to check the box: "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo [OK] Python detected:
%PYTHON_CMD% --version
echo.

:: -----------------------------------------------------------------------------
:: 3. Verify Dependencies
:: -----------------------------------------------------------------------------
echo [INFO] Verifying project dependencies...
%PYTHON_CMD% -c "import streamlit, psutil, pandas, sklearn, plotly" >nul 2>&1
if %errorLevel% neq 0 (
    echo [WARN] Missing required Python packages. Installing from requirements.txt...
    %PYTHON_CMD% -m pip install -r requirements.txt
    if %errorLevel% neq 0 (
        echo [ERROR] Failed to install dependencies. Please run 'pip install -r requirements.txt' manually.
        pause
        exit /b 1
    )
    echo [OK] All dependencies successfully installed.
) else (
    echo [OK] All required dependencies are installed.
)
echo.

:: -----------------------------------------------------------------------------
:: 4. Optional Special Modes (via flags)
:: -----------------------------------------------------------------------------
if /i "%~1"=="--test" (
    echo [INFO] Running test suite...
    %PYTHON_CMD% test_core.py
    %PYTHON_CMD% test_ai.py
    pause
    exit /b 0
)

if /i "%~1"=="--experiment" (
    echo [INFO] Running scientific benchmark experiment...
    %PYTHON_CMD% run_experiment.py
    pause
    exit /b 0
)

if /i "%~1"=="--dashboard-only" (
    echo [INFO] Launching Streamlit Web Dashboard only...
    %PYTHON_CMD% -m streamlit run dashboard.py
    pause
    exit /b 0
)

if /i "%~1"=="--controller-only" (
    echo [INFO] Launching Thermal Controller Engine only...
    %PYTHON_CMD% main.py
    pause
    exit /b 0
)

:: -----------------------------------------------------------------------------
:: 5. Launch Hardware Sensor Monitor (LibreHardwareMonitor) in Background
:: -----------------------------------------------------------------------------
echo =====================================================================
echo  [1/2] Checking Hardware Sensor Monitor (LibreHardwareMonitor)...
echo =====================================================================

tasklist /fi "imagename eq LibreHardwareMonitor.exe" 2>nul | findstr /i "LibreHardwareMonitor.exe" >nul
if !errorLevel! equ 0 (
    echo [OK] LibreHardwareMonitor is already running in background.
) else (
    set "LHM_EXE="
    if "!LHM_EXE!"=="" if exist "%~dp0tools\LibreHardwareMonitor\LibreHardwareMonitor.exe" set "LHM_EXE=%~dp0tools\LibreHardwareMonitor\LibreHardwareMonitor.exe"

    if not "!LHM_EXE!"=="" (
        echo [INFO] Launching LibreHardwareMonitor for CPU diode monitoring...
        start "" "!LHM_EXE!"
        ping -n 3 127.0.0.1 >nul
        echo [OK] LibreHardwareMonitor started.
    ) else (
        echo [WARN] LibreHardwareMonitor.exe not found.
    )
)
echo.

:: -----------------------------------------------------------------------------
:: 6. Launch Interactive Web Dashboard (Streamlit) Minimized in Background
:: -----------------------------------------------------------------------------
echo =====================================================================
echo  [2/2] Launching Interactive Web Dashboard (Streamlit)...
echo        Dashboard URL: http://localhost:8501
echo =====================================================================

:: Terminate any lingering orphaned dashboard instances to free port 8501
taskkill /fi "WINDOWTITLE eq AI Thermal Controller - Web Dashboard*" /t /f >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*streamlit*dashboard.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

start "AI Thermal Controller - Web Dashboard" /min %PYTHON_CMD% -m streamlit run dashboard.py

:: Short wait to allow the dashboard server to bind port and trigger browser open
ping -n 3 127.0.0.1 >nul

:: -----------------------------------------------------------------------------
:: 7. Launch Thermal Controller Engine in Current Console Window
:: -----------------------------------------------------------------------------
echo.
echo =====================================================================
echo  AI THERMAL CONTROLLER RUNTIME ACTIVE
echo        - Real-time CPU/GPU/RAM telemetry monitoring
echo        - ML Temperature Forecasting (10-second horizon)
echo        - Dynamic OS Power Scheme and CPU Boost Optimization
echo.
echo  Available Commands in this Console:
echo    'g on [name]' : Simulate game launch (e.g. 'g on cs2.exe')
echo    'g off'       : Stop game simulation
echo    't [degrees]' : Override CPU Temp (e.g. 't 92' or 't auto')
echo    'sc [key]'    : Load scenario (HEAVY_THERMAL_LOAD, RAPID_SPIKE, etc.)
echo    'q' or 'exit' : Shutdown controller and dashboard cleanly
echo =====================================================================
echo.

%PYTHON_CMD% main.py

:: -----------------------------------------------------------------------------
:: 8. Clean Shutdown and Cleanup
:: -----------------------------------------------------------------------------
echo.
echo =====================================================================
echo  [CLEANUP] Stopping Web Dashboard and restoring environment...
echo =====================================================================

:: Terminate the Streamlit Web Dashboard window and background processes
taskkill /fi "WINDOWTITLE eq AI Thermal Controller - Web Dashboard*" /t /f >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*streamlit*dashboard.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

echo [OK] All services stopped cleanly.
echo [OK] Original Windows power plan and CPU limits restored.
echo =====================================================================
echo.
pause
