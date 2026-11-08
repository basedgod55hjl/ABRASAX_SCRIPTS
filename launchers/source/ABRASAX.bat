@echo off
REM ============================================================
REM  ABRASAX - SINGLE CANONICAL LAUNCHER
REM  One entry point for the whole mesh (gateway/dashboard/sysmon/
REM  bridges/service_host/cron/daemons/headroom/autopilot).
REM  Stop with ..\scripts\stop_system.ps1
REM ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\launch_system.ps1"
pause
