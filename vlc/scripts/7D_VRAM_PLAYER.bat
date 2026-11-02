@echo off
:: Check for administrative privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ==========================================================
    echo  Requesting Administrator privileges...
    echo ==========================================================
    powershell -Command "Start-Process -FilePath '%~dpnx0' -Verb RunAs"
    exit /b
)

:: Set working directory to VLC install
cd /d "C:\Program Files\VideoLAN\VLC"

title 7D VRAM PLAYER v3.0 - ABRASAX OSIRISBLXCK ULTIMATE (ADMIN)
color 0C
mode con: cols=95 lines=38

:: Define paths to local VLC and playlists
set "VLC=C:\Program Files\VideoLAN\VLC\vlc.exe"
set "PLAYLIST=C:\Program Files\VideoLAN\VLC\playlists\5555555555555555555555555555555555555555555555555555555555555555555555.xspf"
set "THUMBS=C:\Program Files\VideoLAN\VLC\thumbnails"
set "LOG=C:\Program Files\VideoLAN\VLC\logs\vlc_watchdog.log"
set "VLCLOG=C:\Program Files\VideoLAN\VLC\logs\vlc_internal.log"
set "HEX=4f5349524953424c58434b"
set "PHI=1.618033988749895"

:: Ensure thumbnails directory exists
if not exist "%THUMBS%" mkdir "%THUMBS%"

echo =========================================================================
echo  ABRASAX OSIRISBLXCK ULTIMATE - 7D VRAM PLAYER v3.0 (ADMIN MODE)
echo  Launching 555 Playlist with FULL GPU ACCELERATION...
echo =========================================================================
echo.
echo  Telemetry Log: %LOG%
echo  VLC Internal Log: %VLCLOG%
echo  Press Ctrl+C to terminate the watchdog loop.
echo.

:WATCHDOG_GPU_LOOP
echo  [WATCHDOG] Launching VLC with full GPU acceleration...
echo [%DATE% %TIME%] WATCHDOG: Launching VLC (GPU) >> "%LOG%"

"%VLC%" ^
 --avcodec-hw=any --avcodec-threads=0 --avcodec-fast ^
 --vout=direct3d11 ^
 --file-caching=2000 --network-caching=3000 --live-caching=500 ^
 --audio-filter=spatializer,compressor,equalizer ^
 --playlist-autostart --loop --repeat ^
 --no-video-title-show --video-on-top ^
 --audio-desync=0 ^
 --extraintf=logger --logfile="%VLCLOG%" --log-verbose=3 ^
 "%PLAYLIST%"

echo  [WATCHDOG] VLC exited (code: %ERRORLEVEL%) - relaunching in 3s...
echo [%DATE% %TIME%] WATCHDOG: VLC exited code=%ERRORLEVEL%, relaunching >> "%LOG%"
timeout /t 3 /nobreak >nul
goto WATCHDOG_GPU_LOOP
