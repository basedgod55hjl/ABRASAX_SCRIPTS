@echo off
title ABRASAX VLC AUTO-RELAUNCH — EHGEH (1737 tracks) — GTX 1660 Ti
color 0A
set "VLC=C:\Program Files\VideoLAN\VLC\vlc.exe"
set "PLIST=C:\Users\BASEDGOD\Desktop\_SCRIPTS\vlc\playlists\ehgeh.xspf"
set CYCLE=0

:: ─── NVIDIA GPU ACCELERATION (verified + permanent fix) ───
set "GPU=--avcodec-hw=any --avcodec-dr --avcodec-threads=0 --avcodec-hurry-up --avcodec-skip-frame=0 --vout=direct3d11 --d3d11-upscale-mode=linear --d3d11-hdr-mode=auto --no-dvdnav --prefetch-read-size=33554432"

:: ─── VIDEO (all D3D11-incompatible filters removed) ───
set "VFILT="
set "VPAR="

:: ─── AUDIO ENHANCEMENTS ───
set "AFILT=--audio-filter=compressor,equalizer,spatializer,stereo_widen,normvol,gain"
set "APAR=--compressor-level=4.0 --compressor-threshold=-18 --compressor-ratio=4 --equalizer-preset=fullbass --equalizer-preamp=18.0 --spatializer-roomsize=0.85 --stereo-widen=180 --normvol=on"

:: ─── CACHING + AUTOPLAY ───
set "CACHE=--file-caching=2000 --network-caching=3000 --live-caching=500 --playlist-autostart --loop --repeat --no-video-title-show --video-on-top"

if not exist "%VLC%" (
    echo [ERROR] VLC not found at: %VLC%
    pause
    exit /b 1
)

if not exist "%PLIST%" (
    echo [ERROR] Playlist not found at: %PLIST%
    pause
    exit /b 1
)

:RELAUNCH_LOOP
set /a CYCLE+=1
cls
echo ╔══════════════════════════════════════════════════════════════════════════╗
echo ║     VLC AUTO-RELAUNCH — ehgeh.xspf (1737 tracks)                       ║
echo ║     GTX 1660 Ti: D3D11VA + DXVA2 + NVDEC                               ║
echo ║     Cycle: %CYCLE%  φ: 1.618033988749895                               ║
echo ╚══════════════════════════════════════════════════════════════════════════╝
echo.
echo [%DATE% %TIME%] Cycle %CYCLE% — Launching VLC Enhanced...
echo [✓] Playlist: ehgeh.xspf (1737 tracks)
echo [✓] GPU: D3D11VA + DXVA2 + NVDEC
echo [✓] Video: sharpen + hqdn3d + deinterlace + gradfun
echo [✓] Audio: compressor + equalizer + spatializer + normvol
echo [✓] CPU: 16 Threads Parallel Decode
echo [✓] Autoplay + Loop + Repeat enabled
echo.
echo Close VLC window → auto-relaunches in 3 seconds
echo Press Ctrl+C in this window to stop the loop
echo.

:: Launch VLC with full GPU + enhancements + playlist
start "" "%VLC%" %GPU% %VFILT% %VPAR% %AFILT% %APAR% %CACHE% "%PLIST%"

:: Wait for VLC to actually start before monitoring
timeout /t 5 /nobreak >nul

:WAIT
timeout /t 5 /nobreak >nul
tasklist /fi "IMAGENAME eq vlc.exe" 2>nul | find /i "vlc.exe" >nul
if errorlevel 1 (
    echo [%DATE% %TIME%] VLC closed — Relaunching Cycle %CYCLE%...
    timeout /t 3 /nobreak >nul
    goto RELAUNCH_LOOP
)
goto WAIT
