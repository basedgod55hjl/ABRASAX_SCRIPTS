@echo off
title OSIRISBLXCK v5 — 3 MONITOR LAUNCH
color 0D
chcp 65001 >nul

echo ╔══════════════════════════════════════════════════════════╗
echo ║     OSIRISBLXCK v5 — 3 MONITOR FULL LAUNCH            ║
echo ║     4f5349524953424c58434b                               ║
echo ║     φ = 1.618  |  K = 0.618  |  φ×K = 1.0             ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
echo Launching across all 3 monitors...
echo   Monitor 1 (Primary): Chat
echo   Monitor 2: VRAM Monitor
echo   Monitor 3: Alive Bridge
echo.

cd /d "C:\Users\BASEDGOD\Desktop\ABRASAX AGI\scripts"
powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File "_launch_full_display.ps1"

pause
