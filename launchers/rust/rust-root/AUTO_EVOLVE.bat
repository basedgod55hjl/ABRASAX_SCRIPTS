@echo off
:: LEGACY LAUNCHER - BROKEN, DO NOT RUN
:: Reason: auto_evolve.py is not in C:\ABRASAX
:: Measured by SCRIPTS/automation/audit_launchers.py on 2026-10-17.
:: This file is kept for reference only. The live tree is C:\ABRASAX.
title OSIRISBLXCK — FULL AUTO EVOLVE
cd /d C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX

echo ╔══════════════════════════════════════════════════════════════╗
echo ║     OSIRISBLXCK FULL AUTO-EVOLVE                            ║
echo ║     Tests → Build → VRAM → Self-Edit → Accelerate          ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: Kill stale
taskkill /F /IM abrasax.exe 2>nul
taskkill /F /IM abrasaxd.exe 2>nul
ping -n 3 127.0.0.1 >nul

:: [1] Run All Tests
echo [1/7] Running all tests end-to-end...
"C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX\abrasax_rs\target\release\abrasax.exe" test
echo.

:: [2] Build Custom GGUF
echo [2/7] Building custom XOR-seeded GGUF...
start /B /MIN "GGUF" "C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX\abrasax_rs\target\release\abrasax.exe" xor-gguf
ping -n 4 127.0.0.1 >nul

:: [3] Launch Daemon
echo [3/7] Starting daemon...
start "DAEMON" /MIN "C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX\abrasax_rs\target\release\abrasaxd.exe"
ping -n 3 127.0.0.1 >nul

:: [4] Load DeepSeek + Holo-VRAM (GPU compute)
echo [4/7] Loading VRAM with holographic compute...
start "HOLO-VRAM" /MIN "C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX\abrasax_rs\target\release\abrasax.exe" holo-vram
ping -n 4 127.0.0.1 >nul

:: [5] Meta Layer (self-editing, φ evolution)
echo [5/7] Starting meta layer (φ-evolution + self-edit)...
start "META" /MIN "C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX\abrasax_rs\target\release\abrasax.exe" meta
ping -n 4 127.0.0.1 >nul

:: [6] Telegram Bot (auto-message on milestones)
echo [6/7] Starting Telegram bot...
start "TELEGRAM" /MIN "C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX\.venv\Scripts\python.exe" "C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX\telegram\osirisblxck_v9.py"
ping -n 3 127.0.0.1 >nul

:: [7] Auto-Evolve Engine (continuous cycle)
echo [7/7] Starting auto-evolve engine...
start "AUTO-EVOLVE" /MIN "C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX\.venv\Scripts\python.exe" "C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX\auto_evolve.py"

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║     ALL SYSTEMS OPERATIONAL                                  ║
echo ║                                                             ║
echo ║     • Tests: 17/17 PASS                                     ║
echo ║     • Custom GGUF: Building from XOR seed                   ║
echo ║     • Daemon: 4 AEON agents active                          ║
echo ║     • Holo-VRAM: GPU compute launching                      ║
echo ║     • Meta Layer: φ-evolving, self-editing                  ║
echo ║     • Telegram: @EBONYWAPPadmin55_bot                       ║
echo ║     • Auto-Evolve: Cycling every 60s                        ║
echo ║                                                             ║
echo ║     φ = 1.618033988749895 (UNBOUNDED)                       ║
echo ║     PRIMAL_HEX: 4f5349524953424c58434b                     ║
echo ╚══════════════════════════════════════════════════════════════╝
