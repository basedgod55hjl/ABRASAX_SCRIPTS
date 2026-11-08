@echo off
title Neotron A55 Gateway Watchdog
cd /d "%~dp0"
python -m neotron.watchdog
pause