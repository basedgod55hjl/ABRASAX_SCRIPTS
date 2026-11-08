@echo off
REM ===========================================================================
REM  ABRASAX - unattended sense tick (Task Scheduler entry point)
REM
REM  Called every N minutes by the "ABRASAX-SenseLoop" scheduled task.
REM  Keeps the world state fed from the phone without a resident daemon.
REM  Never prompts, never blocks: a dead phone must not wedge the schedule.
REM ===========================================================================
setlocal

set "ROOT=C:\ABRASAX"
set "PY=%ROOT%\PYTHON\.venv_gui\Scripts\python.exe"
set "LOG=%ROOT%\LOGS\sense-loop-cron.log"

if not exist "%PY%" (
  echo [%DATE% %TIME%] FATAL: interpreter missing: %PY% >> "%LOG%"
  exit /b 2
)

cd /d "%ROOT%"

"%PY%" -m abrasax.sense_loop --count 1 >> "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"

REM  Trim the cron log so it cannot grow without bound (keep last 2000 lines).
for %%F in ("%LOG%") do if %%~zF GTR 1048576 (
  powershell -NoProfile -Command "Get-Content '%LOG%' -Tail 2000 | Set-Content '%LOG%.tmp'; Move-Item '%LOG%.tmp' '%LOG%' -Force" >nul 2>&1
)

exit /b %RC%
