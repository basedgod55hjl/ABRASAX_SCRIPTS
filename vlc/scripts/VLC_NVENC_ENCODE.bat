@echo off
title VLC NVENC ENCODER - OSIRISBLXCK
echo ========================================
echo VLC NVIDIA NVENC HARDWARE ENCODER
echo ABRASAX God OS - GTX 1660 Ti
echo ========================================
echo.
set /p input="Enter input file path: "
set /p output="Enter output file path: "
echo.
echo Encoding with NVENC hardware encoder...
echo.
"C:\Program Files\VideoLAN\VLC\vlc.exe" "%input%" ^
    --sout="#transcode{vcodec=h264,venc=nvenc,width=1920,height=1080,vb=20000,acodec=mp3,ab=256}:standard{mux=mp4,dst='%output%',access=file}" ^
    --intf dummy ^
    --play-and-exit ^
    --no-sout-display ^
    --sout-keep
echo.
echo Encoding complete!
pause
