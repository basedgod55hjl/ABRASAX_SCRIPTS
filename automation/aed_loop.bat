@echo off
cd /d C:\ABRASAX
set PYTHONIOENCODING=utf-8
python -u SCRIPTS\automation\aed_loop.py --interval 300 >> LOGS\aed_loop.out 2>&1
