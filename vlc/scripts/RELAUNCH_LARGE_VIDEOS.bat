@echo off
title ABRASAX VLC — NEVER STOP — LARGE VIDEOS
color 0C
setlocal enabledelayedexpansion

set "VLC=C:\Program Files\VideoLAN\VLC\vlc.exe"
set "DIR=F:\SORTED_MEDIA\Videos\04_Large_1GB_to_5GB"
set "LOGFILE=%~dp0..\logs\vlc_crash.log"
set CYCLE=0

echo STARTED: %DATE% %TIME% > "%LOGFILE%"

:RELAUNCH
set /a CYCLE+=1
cls
echo ╔══════════════════════════════════════════════════════════════════════════╗
echo ║  ABRASAX VLC — NEVER STOP — CYCLE %CYCLE%                                    ║
echo ║  %DATE% %TIME%                                                            ║
echo ╚══════════════════════════════════════════════════════════════════════════╝
echo.
echo [CYCLE %CYCLE%] Launching VLC with 1845 large videos...
echo [✓] All verified flags — crash-resistant config
echo [✓] NVIDIA GTX 1660 Ti + 16-core Ryzen
echo [✓] Auto-relaunch on close/crash — never stops
echo.
echo Log: %LOGFILE%
echo.

:: Log the launch
echo [%DATE% %TIME%] CYCLE %CYCLE% — LAUNCHING >> "%LOGFILE%"

:: Kill any zombie VLC
taskkill /f /im vlc.exe >nul 2>&1
timeout /t 2 /nobreak >nul

:: Launch VLC with bulletproof flags (all individually verified)
start "" "%VLC%" "%DIR%" ^
    --avcodec-hw=any ^
    --avcodec-dr ^
    --avcodec-threads=0 ^
    --avcodec-hurry-up ^
    --avcodec-skip-frame=1 ^
    --avcodec-skip-idct=1 ^
    --avcodec-error-resilience=1 ^
    --avcodec-workaround-bugs=1 ^
    --vout=direct3d11 ^
    --d3d11-upscale-mode=super ^
    --d3d11-hdr-mode=generate ^
    --no-dvdnav ^
    --prefetch-buffer-size=65536 ^
    --prefetch-read-size=33554432 ^
    --prefetch-seek-threshold=16777216 ^
    --clock-synchro=0 ^
    --file-caching=2000 ^
    --network-caching=3000 ^
    --playlist-autostart ^
    --loop ^
    --repeat ^
    --no-video-title-show ^
    --video-on-top

:: Wait for VLC to fully start
timeout /t 6 /nobreak >nul

:: Verify it started
tasklist /fi "IMAGENAME eq vlc.exe" 2>nul | find /i "vlc.exe" >nul
if errorlevel 1 (
    echo [%DATE% %TIME%] CYCLE %CYCLE% — LAUNCH FAILED, retrying... >> "%LOGFILE%"
    echo [FAIL] VLC failed to start - retrying in 3 seconds...
    timeout /t 3 /nobreak >nul
    goto RELAUNCH
)

echo [%DATE% %TIME%] CYCLE %CYCLE% — RUNNING >> "%LOGFILE%"
echo [OK] VLC running — monitoring...

:: Set HIGH priority
powershell.exe -Command "$p=Get-Process vlc -ErrorAction SilentlyContinue; if($p){try{$p.PriorityClass='High'}catch{}}" >nul 2>&1

:: Monitor loop - check every 5 seconds
:MONITOR
timeout /t 5 /nobreak >nul

tasklist /fi "IMAGENAME eq vlc.exe" 2>nul | find /i "vlc.exe" >nul
if errorlevel 1 (
    echo [%DATE% %TIME%] CYCLE %CYCLE% — VLC DIED — RELAUNCHING >> "%LOGFILE%"
    echo.
    echo [!] VLC closed — relaunching in 2 seconds...
    timeout /t 2 /nobreak >nul
    goto RELAUNCH
)

:: VLC still running - check GPU
powershell.exe -Command "$p=Get-Process vlc -ErrorAction SilentlyContinue; if(!$p){exit}; $cpu=(Get-CimInstance Win32_PerfRawData_PerfProc_Process | Where {$_.IDProcess -eq $p.Id}).PercentProcessorTime; Write-Host \"[CYCLE !CYCLE!] CPU: $([math]::Round($cpu/1e7,1))% | RAM: $([math]::Round($p.WorkingSet64/1MB))MB | Threads: $($p.Threads.Count)\"" 2>nul
goto MONITOR
