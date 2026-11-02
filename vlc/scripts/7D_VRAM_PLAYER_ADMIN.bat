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

:: Return working directory to user Desktop
cd /d "%USERPROFILE%\Desktop"

title 7D VRAM PLAYER v3.0 - ABRASAX OSIRISBLXCK ULTIMATE (ADMIN)
color 0C
mode con: cols=95 lines=38

:: Securely define paths to Desktop portable VLC and _DATA folder playlists
set "VLC=%USERPROFILE%\Desktop\VLC\vlc-3.0.23\vlc.exe"
set "PLUGINS=%USERPROFILE%\Desktop\VLC\vlc-3.0.23\plugins"
set "PLAYLIST=%USERPROFILE%\Desktop\_DATA\5555555555555555555555555555555555555555555555555555555555555555555555.xspf"
set "MASTER=%USERPROFILE%\Desktop\_DATA\ABRASAX_VLC_MASTER.xspf"
set "DEDUPED=%USERPROFILE%\Desktop\_DATA\ALL_VIDEOS_BY_DURATION_DEDUPED.xspf"
set "THUMBS=%USERPROFILE%\Desktop\thumbnails"
set "LOG=%USERPROFILE%\Desktop\vlc_watchdog.log"
set "VLCLOG=%USERPROFILE%\Desktop\vlc_internal.log"
set "HEX=4f5349524953424c58434b"
set "PHI=1.618033988749895"

:: Ensure thumbnails directory exists
if not exist "%THUMBS%" mkdir "%THUMBS%"

:MENU
cls
echo.
echo  +=========================================================================+
echo  ^|  7D VRAM PLAYER v3.0 - ABRASAX OSIRISBLXCK ULTIMATE (ADMIN)            ^|
echo  ^|  PRIMAL_HEX: %HEX%                              ^|
echo  ^|  phi = %PHI%                                   ^|
echo  ^|  CPU: Ryzen 7 4800H 16T  GPU: GTX 1660 Ti 6GB                         ^|
echo  +=========================================================================+
echo.
echo  [1] PLAY 555  - GPU Accelerated (GTX 1660 Ti + D3D11 + full audio DSP)
echo  [2] PLAY 555  - CPU Stable (avcodec-hw=none stable fallback)
echo  [3] PLAY ALL  - GPU Accelerated Master Playlist (DEDUPED)
echo  [4] PLAY ALL  - CPU Stable Master Playlist (DEDUPED)
echo  [5] PLAY XOR  - Experimental Heterogeneous OpenCL Pipeline
echo  [6] NVENC     - Encode video with GTX 1660 Ti NVENC (H.264/HEVC)
echo  [7] SCAN LOG  - View VLC internal and watchdog logs
echo  [8] WATCHDOG  - Auto-restart loop (GPU Accelerated)
echo  [9] WATCHDOG  - Auto-restart loop (CPU Stable)
echo  [10] EXIT
echo.
set /p C="  Select [1-10]: "

if "%C%"=="1" goto PLAY_555_GPU
if "%C%"=="2" goto PLAY_555_CPU
if "%C%"=="3" goto PLAY_ALL_GPU
if "%C%"=="4" goto PLAY_ALL_CPU
if "%C%"=="5" goto PLAY_XOR
if "%C%"=="6" goto NVENC_ENCODE
if "%C%"=="7" goto SHOW_LOG
if "%C%"=="8" goto WATCHDOG_GPU
if "%C%"=="9" goto WATCHDOG_CPU
if "%C%"=="10" goto EXIT
goto MENU

:: ============================================================================
:: [1] PLAY 555 - GPU ACCELERATED
:: ============================================================================
:PLAY_555_GPU
cls
echo  [+] GPU ACCELERATED - launching 555 playlist...
echo  [+] GTX 1660 Ti (D3D11 + DXVA2 + D3D11VA) + full audio DSP
echo  [+] Press F in VLC for fullscreen
echo.
start "" "%VLC%" --plugin-path="%PLUGINS%" ^
 --avcodec-hw=any --avcodec-threads=16 --avcodec-fast ^
 --ffmpeg-hw --direct3d11-hw-decoding --dxva2=on --d3d11va=on --gpu-accel=auto ^
 --vout=direct3d11 ^
 --file-caching=2000 --network-caching=3000 --live-caching=500 ^
 --video-filter=adjust,sharpen,deinterlace,postproc ^
 --sharpen-intensity=0.35 --adjust-contrast=1.05 --deinterlace=1 --deinterlace-mode=yadif ^
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
 --no-video-title-show --video-on-top ^
 --audio-desync=0 ^
 "%PLAYLIST%"
goto MENU

:: ============================================================================
:: [2] PLAY 555 - CPU STABLE
:: ============================================================================
:PLAY_555_CPU
cls
echo  [+] CPU STABLE - launching 555 playlist...
echo  [+] CPU decode (16T) + D3D11 display + full audio DSP
echo  [+] Press F in VLC for fullscreen
echo.
start "" "%VLC%" --plugin-path="%PLUGINS%" ^
 --avcodec-hw=none --avcodec-threads=16 --avcodec-fast ^
 --vout=gl --opengl-provider=desktop ^
 --file-caching=2000 --network-caching=3000 --live-caching=500 ^
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
 --no-video-title-show --video-on-top ^
 --audio-desync=0 ^
 "%PLAYLIST%"
goto MENU

:: ============================================================================
:: [3] PLAY ALL - GPU ACCELERATED
:: ============================================================================
:PLAY_ALL_GPU
cls
echo  [+] GPU ACCELERATED - Master playlist...
echo  [+] GTX 1660 Ti (D3D11 + DXVA2 + D3D11VA) + full audio DSP
echo.
start "" "%VLC%" --plugin-path="%PLUGINS%" ^
 --avcodec-hw=any --avcodec-threads=16 --avcodec-fast ^
 --ffmpeg-hw --direct3d11-hw-decoding --dxva2=on --d3d11va=on --gpu-accel=auto ^
 --vout=direct3d11 ^
 --file-caching=2000 --network-caching=3000 ^
 --audio-filter=spatializer,compressor,equalizer,stereo_widen ^
 --spatializer-roomsize=0.85 --spatializer-width=1.0 ^
 --spatializer-wet=0.4 --spatializer-dry=0.6 --spatializer-damp=0.2 ^
 --compressor-rms-peak=0 --compressor-attack=10 --compressor-release=150 ^
 --compressor-threshold=-18 --compressor-ratio=4 ^
 --compressor-knee=5 --compressor-makeup-gain=6 ^
 --equalizer-preset=fullbass --equalizer-preamp=18.0 ^
 --audio-time-stretch --audio-replay-gain-mode=track ^
 --playlist-autostart --loop --repeat ^
 --no-video-title-show --video-on-top ^
 "%DEDUPED%"
goto MENU

:: ============================================================================
:: [4] PLAY ALL - CPU STABLE
:: ============================================================================
:PLAY_ALL_CPU
cls
echo  [+] CPU STABLE - Master playlist...
echo  [+] CPU decode (16T) + D3D11 + full audio DSP
echo.
start "" "%VLC%" --plugin-path="%PLUGINS%" ^
 --avcodec-hw=none --avcodec-threads=16 --avcodec-fast ^
 --vout=gl --opengl-provider=desktop ^
 --file-caching=2000 --network-caching=3000 ^
 --audio-filter=spatializer,compressor,equalizer,stereo_widen ^
 --spatializer-roomsize=0.85 --spatializer-width=1.0 ^
 --spatializer-wet=0.4 --spatializer-dry=0.6 --spatializer-damp=0.2 ^
 --compressor-rms-peak=0 --compressor-attack=10 --compressor-release=150 ^
 --compressor-threshold=-18 --compressor-ratio=4 ^
 --compressor-knee=5 --compressor-makeup-gain=6 ^
 --equalizer-preset=fullbass --equalizer-preamp=18.0 ^
 --audio-time-stretch --audio-replay-gain-mode=track ^
 --playlist-autostart --loop --repeat ^
 --no-video-title-show --video-on-top ^
 "%DEDUPED%"
goto MENU

:: ============================================================================
:: [5] PLAY XOR - Experimental GPU acceleration (OpenCL)
:: ============================================================================
:PLAY_XOR
cls
echo  +=========================================================================+
echo  ^|  XOR/ABS GPU PIPELINE v1.0 - HETEROGENEOUS COMPUTING               ^|
echo  ^|  NVIDIA GTX 1660 Ti + AMD Radeon iGPU + Ryzen 16T                  ^|
echo  ^|  Primal Hex: %HEX% ^| phi = %PHI%                              ^|
echo  +=========================================================================+
echo.
echo  [1] PLAY Real-time XOR/ABS (NVIDIA GPU + OpenCL)
echo  [2] PLAY Real-time XOR/ABS (AMD iGPU + OpenCL)
echo  [3] ENCODE Video with XOR/ABS (NVIDIA NVENC Hardware Encoder)
echo  [4] ENCODE Video with XOR/ABS (AMD AMF Hardware Encoder)
echo  [5] Return to Main Menu
echo.
set /p XOR_C="  Select [1-5]: "
if "%XOR_C%"=="5" goto MENU

echo.
set /p INFILE="  Enter input video path (or drag & drop): "
set INFILE=###%INFILE%###
set INFILE=%INFILE:###=%
set INFILE=%INFILE:"=%

if "%XOR_C%"=="1" (
    echo Launching NVIDIA GPU OpenCL real-time playback...
    "C:\Users\BASEDGOD\Desktop\ABRASAX\.venv\Scripts\python.exe" "C:\Users\BASEDGOD\Desktop\ABRASAX\xor_abs_pipeline.py" "%INFILE%" none nvidia 1
    pause
    goto PLAY_XOR
)
if "%XOR_C%"=="2" (
    echo Launching AMD iGPU OpenCL real-time playback...
    "C:\Users\BASEDGOD\Desktop\ABRASAX\.venv\Scripts\python.exe" "C:\Users\BASEDGOD\Desktop\ABRASAX\xor_abs_pipeline.py" "%INFILE%" none amd 1
    pause
    goto PLAY_XOR
)

:: For encoding, we need an output file path
set /p OUTFILE="  Enter output video path (.mp4): "
set OUTFILE=###%OUTFILE%###
set OUTFILE=%OUTFILE:###=%
set OUTFILE=%OUTFILE:"=%

if "%XOR_C%"=="3" (
    echo Launching NVIDIA GPU NVENC hardware encoder...
    "C:\Users\BASEDGOD\Desktop\ABRASAX\.venv\Scripts\python.exe" "C:\Users\BASEDGOD\Desktop\ABRASAX\xor_abs_pipeline.py" "%INFILE%" "%OUTFILE%" nvidia 1
    pause
    goto PLAY_XOR
)
if "%XOR_C%"=="4" (
    echo Launching AMD iGPU AMF hardware encoder...
    "C:\Users\BASEDGOD\Desktop\ABRASAX\.venv\Scripts\python.exe" "C:\Users\BASEDGOD\Desktop\ABRASAX\xor_abs_pipeline.py" "%INFILE%" "%OUTFILE%" amd 1
    pause
    goto PLAY_XOR
)
goto PLAY_XOR

:: ============================================================================
:: [6] NVENC ENCODE — GTX 1660 Ti hardware encode H.264 or HEVC
:: ============================================================================
:NVENC_ENCODE
cls
echo  +=========================================================================+
echo  ^|  NVENC HARDWARE ENCODER - GTX 1660 Ti (Turing)                        ^|
echo  ^|  Supports: H.264 + H.265/HEVC at up to 4K                             ^|
echo  +=========================================================================+
echo.
set /p INFILE="  Input file path: "
set /p OUTFILE="  Output file path (.mp4): "
echo.
echo  [1] H.264 (compatible, fast)
echo  [2] H.265/HEVC (smaller, better quality)
set /p CODEC="  Select codec [1-2]: "

if "%CODEC%"=="2" (
    set VCODEC=hevc
    set VENC=nvenc_hevc
) else (
    set VCODEC=h264
    set VENC=nvenc
)

echo.
echo  [+] Encoding with GTX 1660 Ti NVENC...
echo  [+] Codec: %VCODEC% via %VENC%
echo.
"%VLC%" --plugin-path="%PLUGINS%" "%INFILE%" ^
 --sout="#transcode{vcodec=%VCODEC%,venc=%VENC%,width=1920,height=1080,vb=12000,acodec=mp3,ab=320,channels=2,samplerate=48000}:standard{mux=mp4,dst='%OUTFILE%',access=file}" ^
 --intf dummy ^
 --play-and-exit ^
 --no-sout-display ^
 --sout-keep
echo.
echo  [+] Encoding complete! Output: %OUTFILE%
pause
goto MENU

:: ============================================================================
:: [7] SCAN LOGS
:: ============================================================================
:SHOW_LOG
cls
echo  +=========================================================================+
echo  ^|  VLC SYSTEM LOGS VIEW                                                  ^|
echo  +=========================================================================+
echo.
echo  [1] View Watchdog Log: %LOG%
echo  [2] View VLC Internal Log: %VLCLOG%
echo  [3] Return to Menu
echo.
set /p LOG_C="  Select [1-3]: "
if "%LOG_C%"=="3" goto MENU
cls
if "%LOG_C%"=="1" (
    if exist "%LOG%" ( type "%LOG%" ) else ( echo No watchdog log found. )
)
if "%LOG_C%"=="2" (
    if exist "%VLCLOG%" ( type "%VLCLOG%" ) else ( echo No VLC internal log found. )
)
echo.
pause
goto SHOW_LOG

:: ============================================================================
:: [8] WATCHDOG — GPU ACCELERATED
:: ============================================================================
:WATCHDOG_GPU
cls
echo  +=========================================================================+
echo  ^|  WATCHDOG MODE - GPU ACCELERATED                                       ^|
echo  ^|  Monitors VLC - auto-relaunches on crash                                ^|
echo  ^|  Logs to: %LOG%                                                         ^|
echo  ^|  Press Ctrl+C to stop watchdog                                         ^|
echo  +=========================================================================+
echo.
echo  [+] Starting GPU Watchdog loop...
echo.

:WATCHDOG_GPU_LOOP
echo  [WATCHDOG] Launching VLC with GPU Accel...
echo [%DATE% %TIME%] WATCHDOG: Launching VLC (GPU) >> "%LOG%"

"%VLC%" --plugin-path="%PLUGINS%" ^
 --avcodec-hw=any --avcodec-threads=16 --avcodec-fast ^
 --ffmpeg-hw --direct3d11-hw-decoding --dxva2=on --d3d11va=on --gpu-accel=auto ^
 --vout=direct3d11 ^
 --file-caching=2000 --network-caching=3000 --live-caching=500 ^
 --video-filter=adjust,sharpen,deinterlace,postproc ^
 --sharpen-intensity=0.35 --adjust-contrast=1.05 --deinterlace=1 --deinterlace-mode=yadif ^
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
 --no-video-title-show --video-on-top ^
 --audio-desync=0 ^
 --extraintf=logger --logfile="%VLCLOG%" --log-verbose=3 ^
 "%PLAYLIST%"

echo  [WATCHDOG] VLC exited (code: %ERRORLEVEL%) — relaunching in 3s...
echo [%DATE% %TIME%] WATCHDOG: VLC exited code=%ERRORLEVEL%, relaunching >> "%LOG%"
timeout /t 3 /nobreak >nul
goto WATCHDOG_GPU_LOOP

:: ============================================================================
:: [9] WATCHDOG — CPU STABLE
:: ============================================================================
:WATCHDOG_CPU
cls
echo  +=========================================================================+
echo  ^|  WATCHDOG MODE - CPU STABLE                                            ^|
echo  ^|  Monitors VLC - auto-relaunches on crash                                ^|
echo  ^|  Logs to: %LOG%                                                         ^|
echo  ^|  Press Ctrl+C to stop watchdog                                         ^|
echo  +=========================================================================+
echo.
echo  [+] Starting CPU Watchdog loop...
echo.

:WATCHDOG_CPU_LOOP
echo  [WATCHDOG] Launching VLC with CPU Stable...
echo [%DATE% %TIME%] WATCHDOG: Launching VLC (CPU) >> "%LOG%"

"%VLC%" --plugin-path="%PLUGINS%" ^
 --avcodec-hw=none --avcodec-threads=16 --avcodec-fast ^
 --vout=gl --opengl-provider=desktop ^
 --file-caching=2000 --network-caching=3000 --live-caching=500 ^
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
 --no-video-title-show --video-on-top ^
 --audio-desync=0 ^
 --extraintf=logger --logfile="%VLCLOG%" --log-verbose=3 ^
 "%PLAYLIST%"

echo  [WATCHDOG] VLC exited (code: %ERRORLEVEL%) — relaunching in 3s...
echo [%DATE% %TIME%] WATCHDOG: VLC exited code=%ERRORLEVEL%, relaunching >> "%LOG%"
timeout /t 3 /nobreak >nul
goto WATCHDOG_CPU_LOOP

:EXIT
exit
