@echo off
title ABRASAX VLC AI ENGINE — SMART LAUNCH
color 0B
cd /d "%~dp0.."

set "PYTHON=C:\Users\BASEDGOD\Desktop\ABRASAX\.venv\Scripts\python.exe"
set "ENGINE=%~dp0..\ai\vlc_ai_engine.py"

if not exist "%PYTHON%" set "PYTHON=python"
if not exist "%ENGINE%" (
    echo [ERROR] AI Engine not found: %ENGINE%
    pause
    exit /b 1
)

:MENU
cls
echo ╔══════════════════════════════════════════════════════════════════════════╗
echo ║        ABRASAX VLC AI ENHANCEMENT ENGINE — SMART LAUNCHER              ║
echo ║        PRIMAL_HEX: 4f5349524953424c58434b | phi: 1.618033988749895    ║
echo ╚══════════════════════════════════════════════════════════════════════════╝
echo.
echo  ╔═══ AI ANALYSIS ══════════════════════════════════════════════════════╗
echo  ║ [1] Analyze ehgeh playlist (1737 tracks)                             ║
echo  ║ [2] Analyze ABRASAX MASTER playlist                                 ║
echo  ║ [3] Analyze ALL_VIDEOS_MASTER playlist                              ║
echo  ╚════════════════════════════════════════════════════════════════════════╝
echo.
echo  ╔═══ AI OPTIMIZATION ══════════════════════════════════════════════════╗
echo  ║ [4] Optimize ehgeh (dedupe + categorize + sort)                      ║
echo  ║ [5] Optimize ABRASAX MASTER                                         ║
echo  ║ [6] Scan ALL drives + create SMART MIX playlist                     ║
echo  ╚════════════════════════════════════════════════════════════════════════╝
echo.
echo  ╔═══ AI PLAYBACK ══════════════════════════════════════════════════════╗
echo  ║ [7] Launch ehgeh with AI-optimized filters                           ║
echo  ║ [8] Launch ABRASAX MASTER with AI filters                            ║
echo  ║ [9] Launch AI SMART MIX (auto-scanned)                               ║
echo  ╚════════════════════════════════════════════════════════════════════════╝
echo.
echo  ╔═══ TOOLS ════════════════════════════════════════════════════════════╗
echo  ║ [R] View latest AI analysis report                                   ║
echo  ║ [L] View AI engine logs                                              ║
echo  ║ [Q] Quit                                                             ║
echo  ╚═══════════════════════════════════════════════════════════════════════╝
echo.
set /p CHOICE="  Select option: "

set "EHGEH=%~dp0..\playlists\ehgeh.xspf"
set "MASTER=%~dp0..\playlists\ABRASAX_VLC_MASTER.xspf"
set "ALLVID=%~dp0..\playlists\ALL_VIDEOS_MASTER.xspf"
set "SMART=%~dp0..\playlists\AI_SMART_MIX.xspf"

if "%CHOICE%"=="1" "%PYTHON%" "%ENGINE%" --playlist "%EHGEH%" --mode analyze & pause & goto MENU
if "%CHOICE%"=="2" "%PYTHON%" "%ENGINE%" --playlist "%MASTER%" --mode analyze & pause & goto MENU
if "%CHOICE%"=="3" "%PYTHON%" "%ENGINE%" --playlist "%ALLVID%" --mode analyze & pause & goto MENU
if "%CHOICE%"=="4" "%PYTHON%" "%ENGINE%" --playlist "%EHGEH%" --mode optimize & pause & goto MENU
if "%CHOICE%"=="5" "%PYTHON%" "%ENGINE%" --playlist "%MASTER%" --mode optimize & pause & goto MENU
if "%CHOICE%"=="6" "%PYTHON%" "%ENGINE%" --mode scan --output "%SMART%" & pause & goto MENU
if "%CHOICE%"=="7" "%PYTHON%" "%ENGINE%" --playlist "%EHGEH%" --mode launch & goto MENU
if "%CHOICE%"=="8" "%PYTHON%" "%ENGINE%" --playlist "%MASTER%" --mode launch & goto MENU
if "%CHOICE%"=="9" if exist "%SMART%" ( "%PYTHON%" "%ENGINE%" --playlist "%SMART%" --mode launch & goto MENU ) else ( echo [ERROR] Run option 6 first to create SMART MIX & pause & goto MENU )
if /i "%CHOICE%"=="R" dir /od "%~dp0..\ai\analysis_*.json" & pause & goto MENU
if /i "%CHOICE%"=="L" type "%~dp0..\logs\vlc_ai_engine.log" 2>nul | more & pause & goto MENU
if /i "%CHOICE%"=="Q" exit /b

goto MENU
