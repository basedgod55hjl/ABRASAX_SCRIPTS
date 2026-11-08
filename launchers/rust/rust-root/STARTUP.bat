@echo off
:: LEGACY LAUNCHER - BROKEN, DO NOT RUN
:: Reason: use: python -m abrasax status  /  abrasax services
:: Measured by SCRIPTS/automation/audit_launchers.py on 2026-10-17.
:: This file is kept for reference only. The live tree is C:\ABRASAX.
title OSIRISBLXCK — AUTO STARTUP
cd /d C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX

:: Kill stale
taskkill /F /IM abrasax.exe 2>nul
taskkill /F /IM abrasaxd.exe 2>nul
ping -n 2 127.0.0.1 >nul

:: Daemon
start "ABRASAX-DAEMON" /MIN "C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX\abrasax_rs\target\release\abrasax.exe" daemon
ping -n 3 127.0.0.1 >nul

:: Meta Layer (UNBOUNDED φ)
start "ABRASAX-META" /MIN "C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX\abrasax_rs\target\release\abrasax.exe" meta
ping -n 4 127.0.0.1 >nul

:: Telegram God Bridge v8
start "TELEGRAM-BOT" /MIN "C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX\.venv\Scripts\python.exe" "C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX\telegram\osirisblxck_telegram_god.py"
ping -n 3 127.0.0.1 >nul

:: Live Optimizer
start "LIVE-OPTIMIZER" /MIN "C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX\.venv\Scripts\python.exe" "C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX\live_optimizer.py"

:: Write PID file for status monitoring
echo %DATE% %TIME% > C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX\last_launch.txt
echo PRIMAL_HEX: 4f5349524953424c58434b >> C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX\last_launch.txt

cls
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║     OSIRISBLXCK — ALL SYSTEMS LAUNCHED                      ║
echo ║     PRIMAL_HEX: 4f5349524953424c58434b                     ║
echo ║     φ UNBOUNDED — TRANSCENDING                             ║
echo ║     CREATOR: sirch — THE AI KNOWS YOU                   ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo Telegram: talk to the bot for live status
echo Bot commands: /status /phi /optimize /logs /gpu /think /who /timer
echo.
echo Processes:
tasklist /FI "IMAGENAME eq abrasax.exe" 2>nul
echo.
