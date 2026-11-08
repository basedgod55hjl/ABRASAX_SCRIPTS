@echo off
:: ABRASAX_JEV: decisions via abrasax_jev.py / _WORK/jev_client.py
REM ============================================
REM  CUA-DRIVER DAEMON LAUNCHER (Desktop)
REM  Starts or restarts the cua-driver automation
REM  daemon reliably. Use before any CUA tools.
REM ============================================
setlocal
REM DEAD PATH (sirch): cua-driver.exe is not installed under any local Python Scripts dir on this host.
set "CUA="
set "URL=C:\Users\lucar\AppData\Local\Temp"

REM --- Default mode. Pass arg: 1 = standard, 2 = unrestricted, else standard ---
set "MODE=standard"
if /i "%~1"=="unrestricted" set "MODE=unrestricted"

REM --- Stop any existing daemon ---
"%CUA%" stop >nul 2>&1
ping -n 2 127.0.0.1 >nul

REM --- Start daemon detached with proper log files ---
echo Starting cua-driver daemon (%MODE% mode)...
start "cua-driver" /min "%CUA%" serve --permission-mode %MODE%

REM --- Wait and verify ---
ping -n 4 127.0.0.1 >nul
"%CUA%" status

echo.
echo If status shows "is running", the daemon is up.
if not "%MODE%"=="standard" (
    echo NOTE: unrestricted mode disables approvals. Use only if you know the risk.
)
pause
endlocal
