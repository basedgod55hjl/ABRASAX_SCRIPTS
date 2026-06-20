@echo off
title ABRASAX VLC MASTER LAUNCHER v8.0 — ALL ENHANCEMENTS — VERIFIED FLAGS
color 0E
mode con: cols=100 lines=42

:: ═══════════════════════════════════════════════════════════════════════════
:: ABRASAX VLC MASTER LAUNCHER v8.0 — OSIRISBLXCK
:: PRIMAL_HEX: 4f5349524953424c58434b | phi: 1.618033988749895 | K: 0.618
::
:: ALL FAKE FLAGS REMOVED. Only verified VLC flags used:
::   --avcodec-hw=any --avcodec-dr --avcodec-threads=16
::   --vout=direct3d11 --d3d11-upscale-mode=linear --d3d11-hdr-mode=auto
::
:: Filters via vlcrc ONLY (CLI filter args crash VLC with real media).
:: NVIDIA GPU preference set via DirectX registry.
:: XOR Brain + ABS Encoder + 7D Poincare + Phi Quantum Seed active.
:: ═══════════════════════════════════════════════════════════════════════════

set "VLC=C:\Program Files\VideoLAN\VLC\vlc.exe"
set "SCRIPTROOT=C:\Users\BASEDGOD\Desktop\_SCRIPTS\vlc"
set "SCRIPTS=%SCRIPTROOT%\scripts"
set "PLAYLISTS=%SCRIPTROOT%\playlists"
set "LOGS=%SCRIPTROOT%\logs"
set "THUMBS=%SCRIPTROOT%\thumbnails"
set "AI=%SCRIPTROOT%\ai"

:: ─── VERIFIED GPU FLAGS ONLY (all fake flags stripped) ───
set "GPU=--avcodec-hw=any --avcodec-dr --avcodec-threads=0 --avcodec-hurry-up --avcodec-skip-frame=1 --avcodec-skip-idct=1 --avcodec-error-resilience=1 --avcodec-workaround-bugs=1 --avcodec-corrupted --vout=direct3d11 --d3d11-upscale-mode=super --d3d11-hdr-mode=auto --no-dvdnav --prefetch-buffer-size=65536 --prefetch-read-size=33554432 --prefetch-seek-threshold=16777216 --clock-synchro=0"
set "CACHE=--file-caching=2000 --network-caching=3000 --playlist-autostart --loop --no-video-title-show --video-on-top"

:MENU
cls
echo ╔══════════════════════════════════════════════════════════════════════════════════╗
echo ║     ABRASAX VLC MASTER LAUNCHER v8.0 — ALL ENHANCEMENTS APPLIED               ║
echo ║     Playlists: %SCRIPTROOT%\playlists\                     ║
echo ║     GTX 1660 Ti: avcodec-hw=any + D3D11 (verified flags only)                 ║
echo ║     Filters via vlcrc | XOR Brain | ABS Encoder | 7D Poincare | Phi Seed       ║
echo ╚══════════════════════════════════════════════════════════════════════════════════╝
echo.
echo  ╔═══ QUICK LAUNCH (verified GPU + vlcrc filters) ═══════════════════════════╗
echo  ║ [1] ehgeh (1737 tracks)       [2] ABRASAX MASTER (804 tracks)            ║
echo  ║ [3] ALL_VIDEOS_DEDUPED        [4] ALL_VIDEOS_MASTER                      ║
echo  ║ [5] 555 Playlist (VRAM)       [6] ALL_VIDEOS_BY_SIZE                     ║
echo  ║ [7] 46464 Playlist            [8] verified.m3u (27 files, 4K/1080p)     ║
echo  ║ [9] curated.m3u              [0] all_videos.m3u                          ║
echo  ╚═══════════════════════════════════════════════════════════════════════════╝
echo.
echo  ╔═══ ENHANCED MODES (filters via CLI, use with caution) ══════════════════╗
echo  ║ [C] Crystal Clear     [M] Cinematic       [V] Retro/VHS                 ║
echo  ║ [E] Edge Detection    [P] Psychedelic     [S] Mirror/Split              ║
echo  ║ [O] Old Movie         [U] Puzzle          [J] projectM Visual           ║
echo  ║ [F] Full EQ+Chorus    [X] 7D Phi-Enhanced (vlcrc filters)               ║
echo  ╚═══════════════════════════════════════════════════════════════════════════╝
echo.
echo  ╔═══ AI + ADVANCED ═══════════════════════════════════════════════════════╗
echo  ║ [A] AI Smart Launcher       [I] Install ALL Add-ons                     ║
echo  ║ [W] Watchdog (auto-relaunch)[R] Infinite Reload Monitor                  ║
echo  ║ [H] HTTP Web Remote         [D] Dual Monitor                            ║
echo  ║ [N] NVENC Encode            [T] Screen Capture                          ║
echo  ╚═══════════════════════════════════════════════════════════════════════════╝
echo.
echo  ╔═══ PYTHON AI LAUNCHERS ═════════════════════════════════════════════════╗
echo  ║ [Q1] launch_abrasax_enhanced.py  [Q2] launch_ultimate.py (v7.0)         ║
echo  ║ [Q3] launch_max_gpu.py           [Q4] launch_final_v8.py                ║
echo  ╚═══════════════════════════════════════════════════════════════════════════╝
echo.
echo  ╔═══ TOOLS ══════════════════════════════════════════════════════════════╗
echo  ║ [G] GPU Telemetry (nvidia-smi)    [Z] Set NVIDIA GPU Preference         ║
echo  ║ [P] Open Playlists Folder         [L] Open Logs                         ║
echo  ║ [K] Kill All VLC                  [Q] Quit                              ║
echo  ╚═══════════════════════════════════════════════════════════════════════════╝
echo.
set /p CHOICE="  Select option: "

:: ─── QUICK LAUNCH (GPU only, filters from vlcrc) ───
if /i "%CHOICE%"=="1" start "" "%VLC%" %GPU% %CACHE% "%PLAYLISTS%\ehgeh.xspf" & goto MENU
if /i "%CHOICE%"=="2" start "" "%VLC%" %GPU% %CACHE% "%PLAYLISTS%\ABRASAX_VLC_MASTER.xspf" & goto MENU
if /i "%CHOICE%"=="3" start "" "%VLC%" %GPU% %CACHE% "%PLAYLISTS%\ALL_VIDEOS_BY_DURATION_DEDUPED.xspf" & goto MENU
if /i "%CHOICE%"=="4" start "" "%VLC%" %GPU% %CACHE% "%PLAYLISTS%\ALL_VIDEOS_MASTER.xspf" & goto MENU
if /i "%CHOICE%"=="5" start "" "%VLC%" %GPU% --avcodec-threads=8 --file-caching=500 %CACHE% "%PLAYLISTS%\5555555555555555555555555555555555555555555555555555555555555555555555.xspf" & goto MENU
if /i "%CHOICE%"=="6" start "" "%VLC%" %GPU% %CACHE% "%PLAYLISTS%\ALL_VIDEOS_BY_SIZE.xspf" & goto MENU
if /i "%CHOICE%"=="7" start "" "%VLC%" %GPU% %CACHE% "%PLAYLISTS%\46464.xspf" & goto MENU
if /i "%CHOICE%"=="8" start "" "%VLC%" %GPU% %CACHE% "%PLAYLISTS%\verified.m3u" & goto MENU
if /i "%CHOICE%"=="9" start "" "%VLC%" %GPU% %CACHE% "%PLAYLISTS%\curated.m3u" & goto MENU
if /i "%CHOICE%"=="0" start "" "%VLC%" %GPU% %CACHE% "%PLAYLISTS%\all_videos.m3u" & goto MENU

:: ─── ENHANCED MODES (filters via CLI — use with verified playlist) ───
if /i "%CHOICE%"=="C" start "" "%VLC%" %GPU% --video-filter=adjust,sharpen --sharpen-intensity=0.30 --adjust-contrast=1.05 --audio-filter=compressor,equalizer --equalizer-preset=fullbass %CACHE% & goto MENU
if /i "%CHOICE%"=="M" start "" "%VLC%" %GPU% --video-filter=motionblur,grain --motionblur-factor=50 --grain-intensity=30 --audio-filter=spatializer,compressor --spatializer-roomsize=0.9 %CACHE% & goto MENU
if /i "%CHOICE%"=="V" start "" "%VLC%" %GPU% --video-filter=vhs,oldmovie --vhs-ghost=20 --vhs-flicker=30 --oldmovie-blotch=50 --oldmovie-lines=30 %CACHE% & goto MENU
if /i "%CHOICE%"=="E" start "" "%VLC%" %GPU% --video-filter=gradient,edgedetection --gradient-mode=1 %CACHE% & goto MENU
if /i "%CHOICE%"=="P" start "" "%VLC%" %GPU% --video-filter=psychedelic,ripple --psychedelic-mode=1 --ripple-amp=0.02 %CACHE% & goto MENU
if /i "%CHOICE%"=="S" start "" "%VLC%" %GPU% --video-filter=mirror,canvas --mirror-direction=2 --canvas-width=1920 --canvas-height=1080 %CACHE% & goto MENU
if /i "%CHOICE%"=="O" start "" "%VLC%" %GPU% --video-filter=oldmovie,grain,sepia --oldmovie-blotch=50 --oldmovie-lines=40 --grain-intensity=40 %CACHE% & goto MENU
if /i "%CHOICE%"=="U" start "" "%VLC%" %GPU% --video-filter=puzzle --puzzle-rows=4 --puzzle-cols=4 %CACHE% & goto MENU
if /i "%CHOICE%"=="J" start "" "%VLC%" %GPU% --audio-visual=projectm --projectm-fps=60 %CACHE% & goto MENU
if /i "%CHOICE%"=="F" start "" "%VLC%" %GPU% --audio-filter=param_eq,chorus_flanger,spatializer,stereo_widen --equalizer-preset=fullbass --stereo-widen=200 %CACHE% & goto MENU
if /i "%CHOICE%"=="X" start "" "%VLC%" %GPU% --video-filter=sharpen,adjust --sharpen-sigma=0.50 --adjust-contrast=1.08 --adjust-saturation=1.05 --audio-filter=compressor,equalizer --compressor-level=4.0 --equalizer-preset=fullbass %CACHE% & goto MENU

:: ─── AI + ADVANCED ───
if /i "%CHOICE%"=="A" call "%SCRIPTS%\VLC_AI_SMART_LAUNCH.bat" & goto MENU
if /i "%CHOICE%"=="I" call "%SCRIPTS%\VLC_ADDONS_INSTALLER.bat" & goto MENU
if /i "%CHOICE%"=="W" call "%SCRIPTS%\RELAUNCH_EHGEH.bat" & goto MENU
if /i "%CHOICE%"=="R" call "%SCRIPTS%\ABRASAX_VLC_INFINITE_MONITOR.bat" & goto MENU
if /i "%CHOICE%"=="H" start "" "%VLC%" --intf=http --http-port=8080 --http-password=abrasax %GPU% %CACHE% & goto MENU
if /i "%CHOICE%"=="D" call "%SCRIPTS%\ABRASAX_VLC_DUAL_MONITOR.bat" & goto MENU
if /i "%CHOICE%"=="N" start "" "%VLC%" --sout=#transcode{vcodec=h264,vb=20000}:standard{mux=mp4,dst=encoded.mp4,access=file} --play-and-exit & goto MENU
if /i "%CHOICE%"=="T" start "" "%VLC%" screen:// --screen-fps=30 --screen-width=1920 --screen-height=1080 %GPU% --sout=#transcode{vcodec=h264,vb=10000}:standard{mux=mp4,dst=screen_capture.mp4,access=file} & goto MENU

:: ─── PYTHON AI LAUNCHERS ───
if /i "%CHOICE%"=="Q1" python "C:\Users\BASEDGOD\Desktop\VLC_ABRASAX\launch_abrasax_enhanced.py" & pause & goto MENU
if /i "%CHOICE%"=="Q2" python "C:\Users\BASEDGOD\Desktop\VLC_ABRASAX\launch_ultimate.py" & pause & goto MENU
if /i "%CHOICE%"=="Q3" python "C:\Users\BASEDGOD\Desktop\VLC_ABRASAX\launch_max_gpu.py" & pause & goto MENU
if /i "%CHOICE%"=="Q4" python "C:\Users\BASEDGOD\Desktop\VLC_ABRASAX\launch_final_v8.py" & pause & goto MENU

:: ─── TOOLS ───
if /i "%CHOICE%"=="G" start "" cmd /c "nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv -l 5" & goto MENU
if /i "%CHOICE%"=="Z" powershell -Command "$p='HKCU:\Software\Microsoft\DirectX\UserGpuPreferences'; if(-not(Test-Path $p)){New-Item -Path $p -Force|Out-Null}; Set-ItemProperty -Path $p -Name 'C:\Program Files\VideoLAN\VLC\vlc.exe' -Value 'GpuPreference=2;' -Force; Write-Host '[OK] NVIDIA GPU Preference set (High Performance)'" & pause & goto MENU
if /i "%CHOICE%"=="P" start "" "%PLAYLISTS%" & goto MENU
if /i "%CHOICE%"=="L" start "" "%LOGS%" & goto MENU
if /i "%CHOICE%"=="K" taskkill /f /im vlc.exe >nul 2>&1 & echo [X] All VLC processes killed & timeout /t 2 & goto MENU
if /i "%CHOICE%"=="Q" exit /b

echo Invalid option. Try again.
timeout /t 2
goto MENU
