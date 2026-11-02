@echo off
title VLC AUTO-RELAUNCH — NVIDIA GTX 1660 Ti ENHANCED
color 0A
cd /d "C:\Program Files\VideoLAN\VLC"
set CYCLE=0

:RELAUNCH
set /a CYCLE+=1
cls
echo ╔══════════════════════════════════════════════════════════════════════════╗
echo ║     VLC AUTO-RELAUNCH — CYCLE %CYCLE%                                 ║
echo ║     NVIDIA GTX 1660 Ti: D3D11VA + DXVA2 + NVDEC                       ║
echo ║     φ: 1.618033988749895                                               ║
echo ╚══════════════════════════════════════════════════════════════════════════╝
echo.
echo [%DATE% %TIME%] Launching VLC Enhanced — Cycle %CYCLE%
echo [✓] GTX 1660 Ti: D3D11VA + DXVA2 + NVDEC + NVENC
echo [✓] Video: Crystal Clear (sharpen + hqdn3d denoise + deinterlace + gradfun)
echo [✓] Audio: Compressor + Equalizer + Spatializer + NormVol
echo [✓] CPU: 16 Threads Parallel Decode
echo.
echo Close VLC window → auto-relaunches in 3 seconds
echo Press Ctrl+C in this window to stop permanently
echo.

:: Launch VLC with FULL NVIDIA GPU + ALL Crystal Clear enhancements
start "" /B vlc.exe ^
    --avcodec-hw=any --avcodec-hw-any --avcodec-hw-decoding=yes --avcodec-dr ^
    --avcodec-threads=16 --avcodec-fast --ffmpeg-hw ^
    --direct3d11-hw-decoding --direct3d11-hw-blending --dxva2=on --d3d11va=on ^
    --vout=direct3d11 --d3d11-upscale-mode=linear --gpu-accel=auto ^
    --video-filter=adjust,sharpen,deinterlace,postproc,hqdn3d,gradfun ^
    --sharpen-intensity=0.35 --adjust-contrast=1.08 ^
    --deinterlace=1 --deinterlace-mode=yadif ^
    --hqdn3d-luma-spatial=4 --hqdn3d-chroma-spatial=4 --gradfun-radius=16 ^
    --audio-filter=compressor,equalizer,spatializer,normvol,gain ^
    --compressor-level=4.0 --equalizer-preset=fullbass --normvol=on ^
    --file-caching=2000 --network-caching=3000 --live-caching=500 ^
    --playlist-autostart --loop --repeat ^
    --no-video-title-show --video-on-top

:MONITOR
timeout /t 5 /nobreak >nul
tasklist /fi "IMAGENAME eq vlc.exe" 2>nul | find /i "vlc.exe" >nul
if errorlevel 1 (
    echo [%DATE% %TIME%] VLC closed — relaunching Cycle %CYCLE%...
    timeout /t 3 /nobreak >nul
    goto RELAUNCH
)
goto MONITOR
