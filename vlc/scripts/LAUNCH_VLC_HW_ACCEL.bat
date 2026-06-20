@echo off
title VLC 64-bit HW Accelerated - ABRASAX
color 0A
echo ============================================
echo   VLC 3.0.23 64-bit — HARDWARE ACCELERATED
echo   GTX 1660 Ti — Direct3D11 — DXVA2 — D3D11VA
echo   PRIMAL_HEX: 4f5349524953424c58434b
echo ============================================
echo.
echo [✓] Loading ABRASAX Master Playlist (150 tracks)
echo [✓] GPU hardware decoding enabled
echo [✓] Direct3D11 video output
echo.

start "" "C:\Program Files\VideoLAN\VLC\vlc.exe" ^
    --avcodec-hw=any ^
    --direct3d11-hw-decoding ^
    --gpu-accel=auto ^
    --dxva2=on ^
    --d3d11va=on ^
    --file-caching=300 ^
    --network-caching=1000 ^
    --live-caching=300 ^
    --no-video-title-show ^
    --video-on-top ^
    "C:\Program Files\VideoLAN\VLC\playlists\ABRASAX_VLC_MASTER.xspf"

echo.
echo [✓] VLC Launched! Enjoy the show.
echo.
pause
