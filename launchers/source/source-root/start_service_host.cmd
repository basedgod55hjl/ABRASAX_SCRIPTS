@echo off
rem ABRASAX service host — hidden relaunch wrapper (headless)
cd /d "%~dp0"
set ABRASAX_ROOT=%~dp0
".venv\Scripts\python.exe" scripts\abrasax_service_host.py >> "logs\start_all\service_host.log" 2>&1
