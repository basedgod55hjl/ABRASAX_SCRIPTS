@echo off
title VLC HW ACCEL TEST - OSIRISBLXCK
echo ========================================
echo VLC HARDWARE ACCELERATION TEST SUITE
echo ========================================
echo.
echo [1] Test Direct3D11 Video Output
echo [2] Test DXVA2 Decoding
echo [3] Test NVENC Encoding
echo [4] Test Multi-GPU (NVIDIA + AMD)
echo [5] Full Benchmark
echo.
set /p choice="Select test (1-5): "
echo.
if "%%choice%%"=="1" goto d3d11
if "%%choice%%"=="2" goto dxva2
if "%%choice%%"=="3" goto nvenc
if "%%choice%%"=="4" goto multigpu
if "%%choice%%"=="5" goto fullbench
goto end

:d3d11
"C:\Program Files\VideoLAN\VLC\vlc.exe" --vout=direct3d11 --avcodec-hw=any
goto end

:dxva2
"C:\Program Files\VideoLAN\VLC\vlc.exe" --vout=direct3d11 --dxva2 --avcodec-hw=any
goto end

:nvenc
"C:\Program Files\VideoLAN\VLC\vlc.exe" --sout=#transcode{vcodec=h264,venc=nvenc,vb=10000}:standard{mux=mp4,dst=test_nvenc.mp4,access=file} %%1
goto end

:multigpu
echo Testing both GPUs...
"C:\Program Files\VideoLAN\VLC\vlc.exe" --avcodec-hw=any --vout=direct3d11
goto end

:fullbench
echo Running full hardware benchmark...
for %%%%i in (*.mp4 *.mkv *.avi) do (
    echo Testing: %%%%i
    "C:\Program Files\VideoLAN\VLC\vlc.exe" "%%%%i" --intf dummy --play-and-exit --avcodec-hw=any --verbose=1
)
goto end

:end
echo Test complete.
pause
