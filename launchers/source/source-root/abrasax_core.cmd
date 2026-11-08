@echo off
rem ABRASAX AI OS — Boot entry (scheduled task target) — headless (no window)
rem PRIMAL_HEX: 4f5349524953424c58434b
cd /d "%~dp0"
wscript //B "%~dp0run_hidden.vbs" "cmd /c ""%~dp0CRON_MASTER.bat"""
exit /b 0
