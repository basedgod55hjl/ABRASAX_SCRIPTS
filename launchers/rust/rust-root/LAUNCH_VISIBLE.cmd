@echo off
:: LEGACY LAUNCHER - BROKEN, DO NOT RUN
:: Reason: targets 'Desktop\ABRASAX AGI' which does not exist
:: Measured by SCRIPTS/automation/audit_launchers.py on 2026-10-17.
:: This file is kept for reference only. The live tree is C:\ABRASAX.
REM ABRASAX VISIBLE WINDOWS LAUNCHER
REM This opens visible monitoring windows
cd /d "C:\Users\sirch\Desktop\ABRASAX AGI"
echo Opening ABRASAX monitor windows...

REM Window 1 - Gateway Monitor
start "ABRASAX Gateway :9000" cmd /k "echo === GATEWAY HEALTH MONITOR === && echo. && :loop && curl -s http://localhost:9000/health && echo. && ping -n 4 127.0.0.1 >nul && cls && goto loop"

REM Window 2 - GPU Monitor
start "ABRASAX GPU" cmd /k "echo === GPU MONITOR === && echo. && :loop && nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader && ping -n 4 127.0.0.1 >nul && cls && goto loop"

REM Window 3 - Process Monitor
start "ABRASAX Processes" cmd /k "echo === ABRASAX PROCESSES === && echo. && :loop && tasklist /fi "IMAGENAME eq python.exe" /nh 2>nul && tasklist /fi "IMAGENAME eq abrasax.exe" /nh 2>nul && ping -n 6 127.0.0.1 >nul && cls && goto loop"

echo All windows launched!
