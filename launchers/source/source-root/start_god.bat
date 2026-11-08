@echo off
:: ABRASAX_JEV: decisions via abrasax_jev.py / _WORK/jev_client.py
title ABRASAX GOD OS
color 0B
cd /d "%~dp0"

echo [OSIRISBLXCK] Starting ABRASAX GOD OS...
echo [OSIRISBLXCK] PRIMAL_HEX: 4F5349524953424C58434B ^| phi: 1.618033988749895

echo [OSIRISBLXCK] Bringing up full service mesh (idempotent)...
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\bringup_services.ps1"

echo [OSIRISBLXCK] Brimstone Catalyst (headless)...
rem Brimstone handled by the ABRASAX-Brimstone-Loop scheduled task (tuned K, 120s cadence) - duplicate launch disabled 2026-10-11
echo [OSIRISBLXCK] LLM svc node-lm-server (headless, :8777)...
start "" /min cmd /c "cd tools\node_lm_server && node server.mjs >> ..\..\logs\node_lm_8777.log 2>&1"

echo [OSIRISBLXCK] Telegram bridge (headless)...
start "" .venv\Scripts\pythonw.exe src\telegram\bridge.py

echo [OSIRISBLXCK] All systems launched.
pause
