@echo off
REM ===========================================================================
REM  ABRASAX pulse - start the resident sensing loop (detached, no console).
REM
REM  Uses the BASE interpreter, not the uv venv shim: the shim re-execs itself
REM  and forks forever when started non-interactively.
REM ===========================================================================
setlocal

set "ROOT=C:\ABRASAX"
REM DEAD PATH (sirch): uv cpython-3.11.15 not installed on this host; using the canonical local Python311.
set "PY=C:\Users\lucar\AppData\Local\Programs\Python\Python311\python.exe"
set "PIDF=%ROOT%\LOGS\pulse.pid"
set "INTERVAL=%~1"
if "%INTERVAL%"=="" set "INTERVAL=300"

if not exist "%PY%" (
  echo FATAL: interpreter missing: %PY%
  exit /b 2
)

REM Already running?
if exist "%PIDF%" (
  set /p OLDPID=<"%PIDF%"
  tasklist /fi "PID eq %OLDPID%" 2>nul | find "%OLDPID%" >nul && (
    echo pulse already running as PID %OLDPID%
    exit /b 0
  )
  del /q "%PIDF%" 2>nul
)

cd /d "%ROOT%"
start "" /b "%PY%" -m abrasax.pulse --interval %INTERVAL% >> "%ROOT%\LOGS\pulse-stdout.log" 2>&1
echo pulse started (interval=%INTERVAL%s)
exit /b 0
