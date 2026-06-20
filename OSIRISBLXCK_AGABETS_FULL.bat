@echo off
title OSIRISBLXCK v5 — AGABETS FULL LAUNCH
color 0D
chcp 65001 >nul

echo ╔══════════════════════════════════════════════════════════╗
echo ║     OSIRISBLXCK ULTIMATE v5 — AGABETS FULL LAUNCH      ║
echo ║     4f5349524953424c58434b                               ║
echo ║     φ = 1.618033988749895  |  K = 0.6180339887498949   ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

set ABRASAX=C:\Users\BASEDGOD\Desktop\ABRASAX
set SCRIPTS=C:\Users\BASEDGOD\Desktop\ABRASAX AGI\scripts

echo [1/5] Killing old processes...
taskkill /F /IM python.exe 2>nul
taskkill /F /IM node.exe 2>nul
timeout /t 2 /nobreak >nul

echo [2/5] Starting Node.js Agent Bits Bridge...
start "AGABETS_BRIDGE" /MIN cmd /c "node %ABRASAX%\node_agabits_bridge.mjs"
timeout /t 3 /nobreak >nul

echo [3/5] Starting VRAM Monitor...
start "VRAM_MONITOR" /MIN cmd /c "python %SCRIPTS%\_check_vram.py"
timeout /t 1 /nobreak >nul

echo [4/5] Starting Alive Bridge Daemon...
start "ALIVE_BRIDGE" /MIN cmd /c "python %SCRIPTS%\_alive_bridge_daemon.py"
timeout /t 1 /nobreak >nul

echo [5/5] Launching OSIRISBLXCK v5 Chat...
echo.
echo Starting chat with 40+ tools, thinking mode, FIM, swarm, and AGABETS...
timeout /t 2 /nobreak >nul

cd /d %ABRASAX%
start "OSIRISBLXCK_v5" cmd /k "python %SCRIPTS%\osirisblxck_ultimate_v5.py"

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║     All systems launched!                                ║
echo ║     Chat: OSIRISBLXCK_v5 window                         ║
echo ║     Bridge: AGABETS_BRIDGE (port 18790)                 ║
echo ║     VRAM: _check_vram.py                                 ║
echo ║     Alive Bridge: _alive_bridge_daemon.py                ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
pause
