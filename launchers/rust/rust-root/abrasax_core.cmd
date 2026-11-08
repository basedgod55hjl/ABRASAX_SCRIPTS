@echo off
:: LEGACY LAUNCHER - BROKEN, DO NOT RUN
:: Reason: looks for C:\Python31x\python.exe; use PYTHON\.venv_gui\Scripts\python.exe
:: Measured by SCRIPTS/automation/audit_launchers.py on 2026-10-17.
:: This file is kept for reference only. The live tree is C:\ABRASAX.
setlocal enabledelayedexpansion

:: ============================================================================
:: ABRASAX AI OS — Core System Launcher
:: High-priority, self-healing launcher for the ABRASAX engine and watchdog.
::
:: This script is the primary entry point for the ABRASAX_AI_CORE Windows service
:: and the boot-level scheduled task. It launches both the Python gateway and the
:: PowerShell watchdog, retrying on failure with exponential backoff.
::
:: HEX: 4f5349524953424c58434b  —  OSIRISBLXCK
:: phi x K = 1.0  |  K = phi^-1 = 0.618
:: ============================================================================

:: --- Configuration ----------------------------------------------------------
set "ABRASAX_ROOT=%~dp0"
set "ABRASAX_ROOT=%ABRASAX_ROOT:~0,-1%"
set "SERVICE_SCRIPT=%ABRASAX_ROOT%\abrasax_service.ps1"
set "GATEWAY_SCRIPT=%ABRASAX_ROOT%\deploy\docker\gateway\gateway.py"
set "ENGINE_SCRIPT=%ABRASAX_ROOT%\_abrasax_local_chat.py"
set "RUST_BRIDGE_SCRIPT=%ABRASAX_ROOT%\ops\start_rust_engine.ps1"
set "LOG_DIR=%ABRASAX_ROOT%\logs"
set "LAUNCHER_LOG=%LOG_DIR%\abrasax_core_launcher.log"
set "MAX_RETRIES=999"
set "BASE_DELAY=2"

:: PowerShell paths to search
set "PWSH_PATHS=C:\Program Files\WindowsApps\Microsoft.PowerShell_7.6.1.0_x64__8wekyb3d8bbwe\pwsh.exe;C:\Program Files\PowerShell\7\pwsh.exe;C:\Program Files\PowerShell\7-preview\pwsh.exe;pwsh.exe"

:: Ensure log directory exists
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

:: Set window title
title ABRASAX-CORE-SYSTEM  [PRIMAL_HEX:4f5349524953424c58434b]

:: Change to ABRASAX root
cd /d "%ABRASAX_ROOT%"

:: ============================================================================
:: Display banner
:: ============================================================================
echo ============================================================
echo  ABRASAX Core System v4.1.0
echo  PRIMAL_HEX: 4f5349524953424c58434b
echo  PHI: 1.618033988749895
echo ============================================================
echo.

:: ============================================================================
:: Find PowerShell (try multiple locations)
:: ============================================================================
set "PWSH="
for %%p in (%PWSH_PATHS%) do (
    where %%p >nul 2>&1
    if not errorlevel 1 (
        set "PWSH=%%p"
        goto :found_pwsh
    )
)
:found_pwsh
if not defined PWSH (
    call :log "CRITICAL: PowerShell not found in any known location"
    exit /b 1
)
call :log "Using PowerShell: %PWSH%"

:: ============================================================================
:: Set high process priority
:: ============================================================================
:: Available: IDLE, BELOW_NORMAL, NORMAL, ABOVE_NORMAL, HIGH, REALTIME
wmic process where "processid='%PID%'" call setpriority "high" >nul 2>&1

:: Also try via PowerShell (more reliable on some systems)
"%PWSH%" -NoProfile -Command "
    try {
        \$p = Get-Process -Id $PID -ErrorAction Stop;
        \$p.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::High;
        Write-Host ('[INIT] Priority set to: ' + \$p.PriorityClass)
    } catch {
        Write-Host ('[INIT] Could not set priority: ' + \$_.Exception.Message)
    }
" >nul 2>&1

call :log "Process priority set to HIGH"

:: ============================================================================
:: Find Python
:: ============================================================================
set "PYTHON="
where python.exe >nul 2>&1
if not errorlevel 1 (
    set "PYTHON=python.exe"
    goto :found_python
)
:: Check common paths
for %%p in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "%ABRASAX_ROOT%\.venv\Scripts\python.exe"
) do (
    if exist "%%~p" (
        set "PYTHON=%%~p"
        goto :found_python
    )
)
:found_python
if not defined PYTHON (
    call :log "WARNING: Python not found. Gateway will not be launched."
) else (
    call :log "Using Python: %PYTHON%"
)

:: ============================================================================
:: Start Rust AI Engine bridge server in background
:: ============================================================================
if exist "%RUST_BRIDGE_SCRIPT%" (
    echo [CORE] Starting Rust engine bridge...
    start "abrasax-rust-bridge" /B /MIN "%PWSH%" -NoProfile -ExecutionPolicy Bypass -Command "& '%RUST_BRIDGE_SCRIPT%' -SkipBuild *> '%LOG_DIR%\rust_bridge_launch.log'"
    call :log "Rust engine bridge launched"
) else (
    call :log "Rust bridge script not found (non-critical): %RUST_BRIDGE_SCRIPT%"
)

:: ============================================================================
:: MAIN LOOP — Watchdog + Gateway with retry and backoff
:: ============================================================================
call :log "============================================"
call :log "ABRASAX AI OS — Core Launcher Starting"
call :log "PRIMAL_HEX: 4f5349524953424c58434b"
call :log "============================================"
call :log "Root: %ABRASAX_ROOT%"

set RETRY_COUNT=0
set DELAY=%BASE_DELAY%

echo [CORE] Starting main service loop...
echo.

:main_loop

:: --- Launch Python gateway if available ---
if defined PYTHON (
    if exist "%GATEWAY_SCRIPT%" (
        call :log "Launching gateway: %GATEWAY_SCRIPT%"
        start "abrasax-gateway" /B /MIN "%PYTHON%" "%GATEWAY_SCRIPT%" >"%LOG_DIR%\gateway.log" 2>&1
    ) else (
        call :log "Gateway script not found: %GATEWAY_SCRIPT%"
    )

    if exist "%ENGINE_SCRIPT%" (
        call :log "Launching engine: %ENGINE_SCRIPT%"
        start "abrasax-engine" /B /MIN "%PYTHON%" "%ENGINE_SCRIPT%" --daemon >"%LOG_DIR%\engine.log" 2>&1
    ) else (
        call :log "Engine script not found: %ENGINE_SCRIPT%"
    )
)

:: --- Launch the PowerShell watchdog (primary loop) ---
if exist "%SERVICE_SCRIPT%" (
    call :log "Launching watchdog: %SERVICE_SCRIPT%"
    "%PWSH%" -NoProfile -ExecutionPolicy Bypass -File "%SERVICE_SCRIPT%"
) else (
    call :log "CRITICAL: Watchdog script not found: %SERVICE_SCRIPT%"
    goto :recovery
)

:: --- If we get here, the watchdog exited unexpectedly ---
call :log "WARNING: Watchdog exited unexpectedly"

:recovery
set /a RETRY_COUNT+=1
call :log "Recovery attempt #%RETRY_COUNT%"

if %RETRY_COUNT% geq %MAX_RETRIES% (
    call :log "CRITICAL: Max retries (%MAX_RETRIES%) reached. Exiting."
    exit /b 1
)

:: Exponential backoff with jitter (cap at 60 seconds)
set /a DELAY = %BASE_DELAY% * 2
if %DELAY% gtr 60 set DELAY=60

:: Add random jitter (+/- 25%)
set /a JITTER = %DELAY% / 4
if %JITTER% lss 1 set JITTER=1
set /a JITTER_OFFSET = %random% %% (%JITTER% * 2 + 1) - %JITTER%
set /a ACTUAL_DELAY = %DELAY% + %JITTER_OFFSET%
if %ACTUAL_DELAY% lss 1 set ACTUAL_DELAY=1

call :log "Backing off for %ACTUAL_DELAY% seconds before restart..."
timeout /t %ACTUAL_DELAY% /nobreak >nul

goto :main_loop

:: ============================================================================
:: Logging function
:: ============================================================================
:log
set "TIMESTAMP=%DATE% %TIME%"
echo [%TIMESTAMP%] %* >> "%LAUNCHER_LOG%"
echo [%TIMESTAMP%] %*
exit /b 0

:: ============================================================================
:: Clean exit handler
:: ============================================================================
:cleanup
call :log "ABRASAX Core Launcher shutting down..."
:: Kill gateway and engine processes on exit
taskkill /FI "WINDOWTITLE eq abrasax-gateway*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq abrasax-engine*" /F >nul 2>&1
exit /b 0
