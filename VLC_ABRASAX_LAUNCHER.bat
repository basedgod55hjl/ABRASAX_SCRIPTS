@echo off
title ABRASAX VLC MASTER LAUNCHER — GLOBAL PATHS FIXED — 7D ENHANCED
color 0E
mode con: cols=100 lines=40

:: ═══════════════════════════════════════════════════════════════════════════
:: VLC GLOBAL LAUNCHER — All paths hardcoded, works from ANY directory
:: PRIMAL_HEX: 4f5349524953424c58434b | φ: 1.618033988749895
:: ═══════════════════════════════════════════════════════════════════════════

set "VLC=C:\Program Files\VideoLAN\VLC\vlc.exe"
set "VLCDIR=C:\Program Files\VideoLAN\VLC"
set "SCRIPTS=%VLCDIR%\scripts"
set "PLAYLISTS=%VLCDIR%\playlists"
set "LOGS=%VLCDIR%\logs"
set "THUMBS=%VLCDIR%\thumbnails"
set "GPU=--avcodec-hw=any --avcodec-hw-any --avcodec-hw-decoding=yes --avcodec-dr --avcodec-threads=16 --avcodec-fast --ffmpeg-hw --direct3d11-hw-decoding --direct3d11-hw-blending --dxva2=on --d3d11va=on --d3d11-upscale-mode=linear --d3d11-hdr-mode=auto --gpu-accel=auto --vout=direct3d11"
set "VFILTERS=--video-filter=adjust,sharpen,deinterlace,postproc,hqdn3d,gradfun"
set "VPARAMS=--sharpen-intensity=0.35 --sharpen-sigma=0.5 --adjust-contrast=1.08 --adjust-brightness=1.02 --adjust-saturation=1.05 --adjust-gamma=1.0 --deinterlace=1 --deinterlace-mode=yadif --hqdn3d-luma-spatial=4 --hqdn3d-chroma-spatial=4 --gradfun-radius=16 --gradfun-strength=1.2"
set "AFILTERS=--audio-filter=compressor,equalizer,spatializer,stereo_widen,normvol,gain"
set "APARAMS=--compressor-level=4.0 --compressor-threshold=-18 --compressor-ratio=4 --compressor-attack=10 --compressor-release=150 --compressor-makeup-gain=6 --equalizer-preset=fullbass --equalizer-preamp=18.0 --spatializer-roomsize=0.85 --spatializer-width=1.0 --spatializer-wet=0.4 --spatializer-dry=0.6 --spatializer-damp=0.2 --stereo-widen=180 --normvol=on --gain=1.0"
set "CACHE=--file-caching=2000 --network-caching=3000 --live-caching=500 --playlist-autostart --loop --repeat --no-video-title-show --video-on-top --audio-desync=0 --audio-time-stretch --audio-replay-gain-mode=track"

:MENU
cls
echo ╔══════════════════════════════════════════════════════════════════════════════════╗
echo ║     ABRASAX VLC MASTER LAUNCHER — GLOBAL PATHS — 7D ENHANCED                  ║
echo ║     All paths hardcoded to: C:\Program Files\VideoLAN\VLC\                    ║
echo ║     GTX 1660 Ti: D3D11VA + DXVA2 + NVDEC + NVENC                             ║
echo ║     PRIMAL_HEX: 4f5349524953424c58434b  |  φ: 1.618033988749895               ║
echo ╚══════════════════════════════════════════════════════════════════════════════════╝
echo.
echo  ╔═══ QUICK LAUNCH ═══════════════════════════════════════════════════════════╗
echo  ║ [1] 46464 Playlist + ALL GPU/Filters     [2] ABRASAX MASTER Playlist      ║
echo  ║ [3] ALL_VIDEOS_BY_DURATION_DEDUPED       [4] ALL_VIDEOS_MASTER            ║
echo  ║ [5] 555 Playlist (VRAM Optimized)        [6] ALL_VIDEOS_BY_SIZE           ║
echo  ╚═══════════════════════════════════════════════════════════════════════════╝
echo.
echo  ╔═══ ENHANCED MODES ═══════════════════════════════════════════════════════╗
echo  ║ [7] Crystal Clear HQ       [8] Cinematic            [9] Retro/VHS       ║
echo  ║ [10] Edge Detection        [11] Psychedelic         [12] Mirror/Split   ║
echo  ║ [13] Old Movie             [14] Puzzle              [15] projectM Visual ║
echo  ║ [16] Full EQ+Chorus+Spatializer                                       ║
echo  ╚═══════════════════════════════════════════════════════════════════════════╝
echo.
echo  ╔═══ ADVANCED ════════════════════════════════════════════════════════════╗
echo  ║ [17] Screen Capture     [18] NVENC Encode    [19] HTTP Web Remote      ║
echo  ║ [20] HW Accel MAX       [21] Dual Monitor    [22] Infinite Reload      ║
echo  ║ [23] 7D VRAM Optimized  [24] AI Enhance Loop                         ║
echo  ╚═══════════════════════════════════════════════════════════════════════════╝
echo.
echo  ╔═══ TOOLS ══════════════════════════════════════════════════════════════╗
echo  ║ [G] GPU Telemetry (nvidia-smi)    [P] Open Playlists Folder            ║
echo  ║ [D] Open Docs Folder              [L] Open Logs                        ║
echo  ║ [K] Kill All VLC                  [Q] Quit                             ║
echo  ╚═══════════════════════════════════════════════════════════════════════════╝
echo.
set /p CHOICE="  Select option: "

:: ─── QUICK LAUNCH ───
if /i "%CHOICE%"=="1" start "" "%VLC%" %GPU% %VFILTERS% %VPARAMS% %AFILTERS% %APARAMS% %CACHE% "%PLAYLISTS%\46464.xspf" & goto MENU
if /i "%CHOICE%"=="2" start "" "%VLC%" %GPU% %VFILTERS% %VPARAMS% %AFILTERS% %APARAMS% %CACHE% "%PLAYLISTS%\ABRASAX_VLC_MASTER.xspf" & goto MENU
if /i "%CHOICE%"=="3" start "" "%VLC%" %GPU% %VFILTERS% %VPARAMS% %AFILTERS% %APARAMS% %CACHE% "%PLAYLISTS%\ALL_VIDEOS_BY_DURATION_DEDUPED.xspf" & goto MENU
if /i "%CHOICE%"=="4" start "" "%VLC%" %GPU% %VFILTERS% %VPARAMS% %AFILTERS% %APARAMS% %CACHE% "%PLAYLISTS%\ALL_VIDEOS_MASTER.xspf" & goto MENU
if /i "%CHOICE%"=="5" call "%SCRIPTS%\7D_VRAM_PLAYER.bat" & goto MENU
if /i "%CHOICE%"=="6" start "" "%VLC%" %GPU% %VFILTERS% %VPARAMS% %AFILTERS% %APARAMS% %CACHE% "%PLAYLISTS%\ALL_VIDEOS_BY_SIZE.xspf" & goto MENU

:: ─── ENHANCED MODES ───
if /i "%CHOICE%"=="7" start "" "%VLC%" %GPU% --video-filter=adjust,hqdn3d,sharpen,gradfun --hqdn3d-luma-spatial=6 --hqdn3d-chroma-spatial=6 --sharpen-intensity=0.30 --adjust-contrast=1.05 --audio-filter=compressor,equalizer --equalizer-preset=fullbass & goto MENU
if /i "%CHOICE%"=="8" start "" "%VLC%" %GPU% --video-filter=motionblur,grain,anaglyph --motionblur-factor=50 --grain-intensity=30 --anaglyph-mode=1 --audio-filter=spatializer,compressor --spatializer-roomsize=0.9 & goto MENU
if /i "%CHOICE%"=="9" start "" "%VLC%" %GPU% --video-filter=vhs,oldmovie,posterize --vhs-ghost=20 --vhs-flicker=30 --oldmovie-blotch=50 --oldmovie-lines=30 --posterize-level=4 & goto MENU
if /i "%CHOICE%"=="10" start "" "%VLC%" %GPU% --video-filter=gradient,edgedetection,invert --gradient-mode=1 --audio-filter=compressor & goto MENU
if /i "%CHOICE%"=="11" start "" "%VLC%" %GPU% --video-filter=psychedelic,ripple,wave --psychedelic-mode=1 --ripple-amp=0.02 --wave-mode=2 & goto MENU
if /i "%CHOICE%"=="12" start "" "%VLC%" %GPU% --video-filter=mirror,canvas --mirror-direction=2 --canvas-width=1920 --canvas-height=1080 & goto MENU
if /i "%CHOICE%"=="13" start "" "%VLC%" %GPU% --video-filter=oldmovie,grain,sepia --oldmovie-blotch=50 --oldmovie-lines=40 --grain-intensity=40 --audio-filter=compressor,equalizer --equalizer-preset=classical & goto MENU
if /i "%CHOICE%"=="14" start "" "%VLC%" %GPU% --video-filter=puzzle --puzzle-rows=4 --puzzle-cols=4 & goto MENU
if /i "%CHOICE%"=="15" start "" "%VLC%" %GPU% --vout=direct3d11 --audio-visual=projectm --projectm-fps=60 --audio-filter=equalizer --equalizer-preset=fullbass & goto MENU
if /i "%CHOICE%"=="16" start "" "%VLC%" %GPU% --audio-filter=param_eq,chorus_flanger,spatializer,stereo_widen --param-eq-band=0,3,5:1,1,2:2,-1,4:3,2,3:4,0,6:5,-2,7:6,1,5:7,3,2:8,0,4:9,-1,3 --chorus-flanger-delay=8 --chorus-flanger-speed=0.3 --spatializer-roomsize=0.85 --stereo-widen=200 --equalizer-preset=fullbass & goto MENU

:: ─── ADVANCED ───
if /i "%CHOICE%"=="17" start "" "%VLC%" screen:// --screen-fps=30 --screen-width=1920 --screen-height=1080 %GPU% --sout=#transcode{vcodec=h264,vb=10000}:standard{mux=mp4,dst=screen_capture.mp4,access=file} & goto MENU
if /i "%CHOICE%"=="18" start "" "%VLC%" --sout=#transcode{vcodec=h264,venc=nvenc,vb=20000}:standard{mux=mp4,dst=encoded.mp4,access=file} --play-and-exit & goto MENU
if /i "%CHOICE%"=="19" start "" "%VLC%" --intf=http --http-port=8080 --http-password=abrasax & goto MENU
if /i "%CHOICE%"=="20" call "%SCRIPTS%\VLC_HW_ACCEL_MAX.bat" & goto MENU
if /i "%CHOICE%"=="21" call "%SCRIPTS%\ABRASAX_VLC_DUAL_MONITOR.bat" & goto MENU
if /i "%CHOICE%"=="22" call "%SCRIPTS%\ABRASAX_VLC_INFINITE_MONITOR.bat" & goto MENU
if /i "%CHOICE%"=="23" call "%SCRIPTS%\7D_VRAM_PLAYER.bat" & goto MENU
if /i "%CHOICE%"=="24" call "%SCRIPTS%\ABRASAX_VLC_AI_ENHANCE.bat" & goto MENU

:: ─── TOOLS ───
if /i "%CHOICE%"=="G" start "" cmd /c "nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv -l 5" & goto MENU
if /i "%CHOICE%"=="P" start "" "%PLAYLISTS%" & goto MENU
if /i "%CHOICE%"=="D" start "" "%VLCDIR%" & goto MENU
if /i "%CHOICE%"=="L" start "" "%LOGS%" & goto MENU
if /i "%CHOICE%"=="K" taskkill /f /im vlc.exe >nul 2>&1 & echo [X] All VLC processes killed & timeout /t 2 & goto MENU
if /i "%CHOICE%"=="Q" exit /b

echo Invalid option. Try again.
timeout /t 2
goto MENU
