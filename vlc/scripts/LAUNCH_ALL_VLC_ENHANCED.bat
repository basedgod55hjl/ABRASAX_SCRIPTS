@echo off
title ABRASAX VLC ACELERATED HETEROGENEOUS ENGINE
color 0D
mode con: cols=95 lines=32

:: --- CORE CONSTANTS ---
set "HEX=4f5349524953424c58434b"
set "PHI=1.618033988749895"
set "VLC=C:\Program Files\VideoLAN\VLC\vlc.exe"
set "PLAYROOT=C:\Users\BASEDGOD\Desktop\_SCRIPTS\vlc"
set "PLAYLIST=%PLAYROOT%\playlists\ALL_VIDEOS_BY_DURATION_DEDUPED.xspf"
set "THUMBS=%PLAYROOT%\thumbnails"
set "LOG=%PLAYROOT%\logs\vlc_debug.log"

:: Make sure thumbnails folder exists
if not exist "%THUMBS%" mkdir "%THUMBS%"

cls
echo.
echo  +=======================================================================================+
echo  ^|   ABRASAX VLC ULTIMATE ENHANCED LAUNCHER v5.0                                         ^|
echo  ^|   PRIMAL_HEX: %HEX%                                                  ^|
echo  ^|   phi = %PHI% ^| phi*K = 1.0                                                         ^|
echo  +=======================================================================================+
echo.
echo   [i] Active Playlist:  %PLAYLIST%
echo   [i] Hardware Targets: CPU (Ryzen 16T) + GPU (GTX 1660 Ti) + iGPU (Radeon)
echo.
echo   [1] LAUNCH ULTIMATE PLAY - CPU Decode + GL Out (Anti-Green Screen / Max Stability)
echo   [2] LAUNCH HW ACCEL PLAY - NVIDIA GPU Decode (Full NVDEC / High FPS)
echo   [3] LAUNCH GPU XOR/ABS   - Run Vectorized OpenCL GPU Pipeline (OpenCL Engine)
echo   [4] EXIT
echo.
set /p CHOICE="  Select option [1-4]: "

if "%CHOICE%"=="1" goto LAUNCH_STABLE
if "%CHOICE%"=="2" goto LAUNCH_HW
if "%CHOICE%"=="3" goto LAUNCH_XOR
if "%CHOICE%"=="4" goto EXIT
goto MENU

:LAUNCH_STABLE
cls
echo  +=======================================================================================+
echo  ^|   LAUNCHING: CPU Decode + GL Output Stable Baseline                                  ^|
echo  ^|   Press F inside VLC to toggle Fullscreen. Close window to return.                    ^|
echo  +=======================================================================================+
echo.
"%VLC%" ^
 --avcodec-hw=none --avcodec-threads=16 --avcodec-fast ^
 --vout=gl --opengl-provider=desktop ^
 --file-caching=2000 --network-caching=3000 --live-caching=500 ^
 --video-filter=sharpen,deinterlace,adjust ^
 --sharpen-sigma=0.5 ^
 --deinterlace=1 --deinterlace-mode=yadif ^
 --postproc-q=6 ^
 --contrast=1.15 --brightness=1.05 --saturation=1.1 --gamma=1.0 ^
 --audio-filter=spatializer,compressor,equalizer,stereo_widen ^
 --spatializer-roomsize=0.85 --spatializer-width=1.0 ^
 --spatializer-wet=0.4 --spatializer-dry=0.6 --spatializer-damp=0.2 ^
 --compressor-rms-peak=0 --compressor-attack=10 --compressor-release=150 ^
 --compressor-threshold=-18 --compressor-ratio=4 ^
 --compressor-knee=5 --compressor-makeup-gain=6 ^
 --equalizer-preset=fullbass --equalizer-preamp=18.0 ^
 --audio-time-stretch --audio-replay-gain-mode=track ^
 --scene-ratio=60 --scene-prefix=snap_ --scene-path="%THUMBS%" ^
 --playlist-autostart --loop --repeat ^
 --no-video-title-show --qt-fullscreen-screennumber=1 --video-on-top ^
 --audio-desync=0 ^
 "%PLAYLIST%"
goto EXIT

:LAUNCH_HW
cls
echo  +=======================================================================================+
echo  ^|   LAUNCHING: Hardware Accelerated NVIDIA NVDEC Playback                              ^|
echo  ^|   Direct3D11 Native GPU Telemetry Active.                                             ^|
echo  +=======================================================================================+
echo.
"%VLC%" ^
 --avcodec-hw=any --avcodec-dr --avcodec-fast --avcodec-threads=16 ^
 --vout=direct3d11 --d3d11-upscale-mode=linear --d3d11-hdr-mode=auto ^
 --direct3d11-hw-blending ^
 --file-caching=1500 --network-caching=3000 --live-caching=500 ^
 --audio-filter=spatializer,compressor,equalizer,stereo_widen ^
 --spatializer-roomsize=0.85 --spatializer-width=1.0 ^
 --spatializer-wet=0.4 --spatializer-dry=0.6 --spatializer-damp=0.2 ^
 --compressor-rms-peak=0 --compressor-attack=10 --compressor-release=150 ^
 --compressor-threshold=-18 --compressor-ratio=4 ^
 --compressor-knee=5 --compressor-makeup-gain=6 ^
 --equalizer-preset=fullbass --equalizer-preamp=18.0 ^
 --playlist-autostart --loop --repeat ^
 --no-video-title-show --qt-fullscreen-screennumber=1 --video-on-top ^
 "%PLAYLIST%"
goto EXIT

:LAUNCH_XOR
cls
echo  +=======================================================================================+
echo  ^|   LAUNCHING: GPU-Accelerated (OpenCL) XOR-ABS Primal-Hex Pipeline                     ^|
echo  ^|   Rendering real-time on NVIDIA GeForce GTX 1660 Ti OpenCL Core.                      ^|
echo  +=======================================================================================+
echo.
"C:\Users\BASEDGOD\Desktop\ABRASAX\.venv\Scripts\python.exe" "C:\Users\BASEDGOD\Desktop\ABRASAX\xor_abs_pipeline.py" "%PLAYLIST%" none nvidia 1
pause
goto EXIT

:EXIT
exit

