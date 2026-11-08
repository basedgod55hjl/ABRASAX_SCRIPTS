@echo off
REM ABRASAX single-stack launcher -- OSIRISBLXCK 2026-10-31
REM Brings up EXACTLY ONE host (which owns one orchestrator + one jev_server).
REM Safe to run twice: the singleton guard refuses the duplicate.
setlocal
cd /d C:\abrasax

set ABRASAX_ROOT=C:\abrasax
set PY=C:\Users\lucar\AppData\Local\hermes\installs\963bca82cc65020c\environments\5c935fe120f64309965c21d03cf4ab9b\venv\Scripts\python.exe
if not exist "%PY%" set PY=python

echo [align] pre-flight audit...
"%PY%" SCRIPTS\automation\abrasax_align.py
echo.

echo [align] launching guarded host...
start "ABRASAX-HOST" /min "%PY%" C:\abrasax\host.py
timeout /t 6 >nul

echo [align] post-launch audit...
"%PY%" SCRIPTS\automation\abrasax_align.py
endlocal
