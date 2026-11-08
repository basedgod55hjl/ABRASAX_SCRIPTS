@echo off
REM ABRASAX_GOD_OS 7D FUSION COCKPIT - one-click launcher (debug version)
REM Keeps the console open and logs any error so we can see what happens.
cd /d "%~dp0"
if not exist logs mkdir logs
..\..\.venv\Scripts\python.exe -u ..\..\tools\fusion7d_gui.py 2>> logs\gui_error.log
echo.
echo GUI exited with code %errorlevel%  (errors logged to logs\gui_error.log)
pause
