@echo off
REM Neotron A55 Gateway launcher - reads config from .env
cd /d "%~dp0"
python -m neotron.run
pause
