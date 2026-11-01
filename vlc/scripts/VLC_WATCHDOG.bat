@echo off
title VLC — ABRASAX GPU WATCHDOG
color 0A
cd /d "C:\Users\BASEDGOD\Desktop\VLC_ABRASAX"

:LOOP
:: Check if VLC is running
tasklist /FI "IMAGENAME eq vlc.exe" 2>NUL | find /I "vlc.exe" >NUL
if %ERRORLEVEL% EQU 0 (
    :: VLC running — check GPU
    timeout /t 30 /nobreak >nul
    goto LOOP
)

:: VLC dead — relaunch
echo [%DATE% %TIME%] VLC DIED — RELAUNCHING
taskkill /f /im vlc.exe >nul 2>&1
timeout /t 2 /nobreak >nul

start "" "C:\Program Files\VideoLAN\VLC\vlc.exe" ^
    "C:\Users\BASEDGOD\Desktop\VLC_ABRASAX\playlists\verified.m3u" ^
    --avcodec-hw=any --avcodec-dr --avcodec-threads=16 ^
    --vout=direct3d11 --d3d11-upscale-mode=linear ^
    --no-video-title-show

timeout /t 5 /nobreak >nul

:: Verify it started
tasklist /FI "IMAGENAME eq vlc.exe" 2>NUL | find /I "vlc.exe" >NUL
if %ERRORLEVEL% EQU 0 (
    echo [%DATE% %TIME%] VLC RELAUNCHED OK
) else (
    echo [%DATE% %TIME%] LAUNCH FAILED — will retry
)

timeout /t 30 /nobreak >nul
goto LOOP
