@echo off
title ABRASAX NVIDIA → AMD HYBRID GPU PIPELINE
color 0B
cd /d "%~dp0.."

set "PYTHON=python"
if exist "C:\Users\BASEDGOD\Desktop\ABRASAX\.venv\Scripts\python.exe" set "PYTHON=C:\Users\BASEDGOD\Desktop\ABRASAX\.venv\Scripts\python.exe"
set "PIPELINE=%~dp0..\ai\nvidia_amd_pipeline.py"

:MENU
cls
echo ╔══════════════════════════════════════════════════════════════════════════╗
echo ║     ABRASAX NVIDIA - AMD HYBRID GPU PIPELINE                          ║
echo ║     GTX 1660 Ti (decode) --PCIe 3.0 x16--^> Radeon iGPU (display)       ║
echo ║     PRIMAL_HEX: 4f5349524953424c58434b | phi: 1.618                   ║
echo ╚══════════════════════════════════════════════════════════════════════════╝
echo.
echo  ╔═══ PIPELINE CONTROL ════════════════════════════════════════════════╗
echo  ║ [1] Launch NVIDIA→AMD Hybrid VLC (verified.m3u)                    ║
echo  ║ [2] Launch NVIDIA→AMD Hybrid VLC (ehgeh.xspf, 1737 tracks)        ║
echo  ║ [3] Launch NVIDIA→AMD Hybrid VLC (ABRASAX MASTER)                  ║
echo  ║ [4] Launch NVIDIA→AMD Hybrid VLC (curated.m3u)                     ║
echo  ╚═══════════════════════════════════════════════════════════════════════╝
echo.
echo  ╔═══ MONITORING ══════════════════════════════════════════════════════╗
echo  ║ [D] Pipeline Dashboard (snapshot)                                   ║
echo  ║ [M] Live Monitor (both GPUs, 5s refresh)                            ║
echo  ║ [I] GPU Info + Bandwidth Report                                     ║
echo  ╚═══════════════════════════════════════════════════════════════════════╝
echo.
echo  ╔═══ SYSTEM ══════════════════════════════════════════════════════════╗
echo  ║ [G] GPU Telemetry (nvidia-smi live)                                  ║
echo  ║ [K] Kill All VLC                                                    ║
echo  ║ [Q] Quit                                                             ║
echo  ╚═══════════════════════════════════════════════════════════════════════╝
echo.
set /p CHOICE="  Select option: "

set "PLAYLISTS=%~dp0..\playlists"

if "%CHOICE%"=="1" "%PYTHON%" "%PIPELINE%" --mode launch --playlist "%PLAYLISTS%\verified.m3u" & pause & goto MENU
if "%CHOICE%"=="2" "%PYTHON%" "%PIPELINE%" --mode launch --playlist "%PLAYLISTS%\ehgeh.xspf" & pause & goto MENU
if "%CHOICE%"=="3" "%PYTHON%" "%PIPELINE%" --mode launch --playlist "%PLAYLISTS%\ABRASAX_VLC_MASTER.xspf" & pause & goto MENU
if "%CHOICE%"=="4" "%PYTHON%" "%PIPELINE%" --mode launch --playlist "%PLAYLISTS%\curated.m3u" & pause & goto MENU
if /i "%CHOICE%"=="D" "%PYTHON%" "%PIPELINE%" --mode dashboard & pause & goto MENU
if /i "%CHOICE%"=="M" "%PYTHON%" "%PIPELINE%" --mode monitor --interval 5 & goto MENU
if /i "%CHOICE%"=="I" "%PYTHON%" "%PIPELINE%" --mode info & pause & goto MENU
if /i "%CHOICE%"=="G" start "" cmd /c "nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,pcie.rx.throughput,pcie.tx.throughput --format=csv -l 3" & goto MENU
if /i "%CHOICE%"=="K" taskkill /f /im vlc.exe >nul 2>&1 & echo [X] All VLC killed & timeout /t 2 & goto MENU
if /i "%CHOICE%"=="Q" exit /b

goto MENU
