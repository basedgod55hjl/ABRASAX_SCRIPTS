@echo off
REM Stop the resident ABRASAX pulse loop.
setlocal
set "PIDF=C:\ABRASAX\LOGS\pulse.pid"
if not exist "%PIDF%" (
  echo pulse not running ^(no pid file^)
  exit /b 0
)
set /p PID=<"%PIDF%"
echo stopping pulse PID %PID%
taskkill /PID %PID% /T /F >nul 2>&1
del /q "%PIDF%" 2>nul
echo stopped
exit /b 0
