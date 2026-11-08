@echo off
:: LEGACY LAUNCHER - BROKEN, DO NOT RUN
:: Reason: targets the retired ABRASAX_GOD_OS tree
:: Measured by SCRIPTS/automation/audit_launchers.py on 2026-10-17.
:: This file is kept for reference only. The live tree is C:\ABRASAX.
title ABRASAX CRON MASTER + SELF-BUILD
cd /d "C:\Users\sirch\Desktop\ABRASAX_GOD_OS"

echo [ABRASAX] Initializing Master Autonomous Self-Build Loop...
call .venv\Scripts\python.exe runtime\tiered_log.py heartbeat --iter 0
call .venv\Scripts\python.exe runtime\tiered_log.py decision --context "cron_master" --action "loop_start" --outcome "started"
call .venv\Scripts\python.exe llm_omega_build.py --build-all --gpu-optimize --parallel

:loop
echo [%date% %time%] Running ABRASAX Self-Build and Self-Optimization...
call .venv\Scripts\python.exe runtime\tiered_log.py heartbeat
call .venv\Scripts\python.exe llm_omega_build.py --build-all --gpu-optimize --parallel
call .venv\Scripts\python.exe runtime\tiered_log.py devlog --source cron_loop --kind tools --msg "TOOLS phase: build+optimize complete"
REM local_nexus fire-and-forget (2026-10-03: console-sharing wrappers wedged the
REM chain; a stuck nexus must never block the cycle. In-code 420s cap handles
REM runaway cycles; output goes to logs\nexus_run.log.)
start "" /min cmd /c ".venv\Scripts\python.exe runtime\local_nexus.py --once >> logs\nexus_run.log 2>&1"
call .venv\Scripts\python.exe runtime\tiered_log.py devlog --source cron_loop --kind reasoning --msg "REASONING phase: RARV cycle complete"
call .venv\Scripts\python.exe runtime\llm_roles_runner.py
call .venv\Scripts\python.exe runtime\compute_telemetry.py
call .venv\Scripts\python.exe runtime\kernel_telemetry.py
call .venv\Scripts\python.exe runtime\phone_telemetry.py
call .venv\Scripts\python.exe runtime\twin_wire.py
call .venv\Scripts\python.exe runtime\self_reflect.py
call .venv\Scripts\python.exe runtime\jarvis_autopilot.py
ping -n 2 127.0.0.1 >nul
goto loop
