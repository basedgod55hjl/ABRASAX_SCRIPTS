@echo off
:: ABRASAX ALL ENGINES — Opens a visible elevated window
net session >nul 2>&1
if %errorLevel% neq 0 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)
title ABRASAX ALL ENGINES — Full System Launch
color 0D
cd /d "C:\Users\BASEDGOD\Desktop\ABRASAX AGI\abrasax_rs"
echo ============================================================
echo   ABRASAX v4.1.0 — ALL ENGINES LAUNCH
echo   MetaLayer + Autonomy + Holographic + Brimstone
echo   + MasterParallel + Stress Test
echo   PRIMAL_HEX: 4f5349524953424c58434b
echo ============================================================
echo.
".\target\release\abrasax.exe" all
echo.
pause
