@echo off
title VLC ULTIMATE HW ACCEL - OSIRISBLXCK
echo ========================================
echo VLC ULTIMATE HARDWARE ACCELERATION ENGINE
echo ABRASAX God OS - NVIDIA GTX 1660 Ti
echo ========================================
echo.
echo [GPU] Direct3D11 + DXVA2 + D3D11VA
echo [CPU] AMD Ryzen 7 4800H (16 threads)
echo.
start "" "C:\Program Files\VideoLAN\VLC\vlc.exe" ^
    --avcodec-hw=any ^
    --vout=direct3d11 ^
    --d3d11va ^
    --dxva2 ^
    --codec=all ^
    --no-ffmpeg-dr ^
    --live-caching=300 ^
    --file-caching=1000 ^
    --real-time ^
    --rt-priority ^
    --skip-frames=0 ^
    --decoding-threads=0
