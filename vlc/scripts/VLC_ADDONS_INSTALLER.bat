@echo off
title ABRASAX VLC — ADD-ONS INSTALLER
color 0D
cd /d "C:\Program Files\VideoLAN\VLC"

echo ╔══════════════════════════════════════════════════════════════════════════╗
echo ║        ABRASAX VLC ADD-ONS INSTALLER v1.0                             ║
echo ║        PRIMAL_HEX: 4f5349524953424c58434b | phi: 1.618                ║
echo ╚══════════════════════════════════════════════════════════════════════════╝
echo.

:: ============================================================================
:: 1. ENABLE HTTP REMOTE CONTROL INTERFACE
:: ============================================================================
echo [1/5] Enabling HTTP Web Remote Control...
echo.

:: Create VLC config directory if needed
if not exist "%APPDATA%\vlc" mkdir "%APPDATA%\vlc"

:: Write HTTP interface config to vlcrc
set "VLCRC=%APPDATA%\vlc\vlcrc"

:: Check if HTTP interface is already configured
findstr /c:"extraintf=http" "%VLCRC%" >nul 2>&1
if errorlevel 1 (
    echo # ABRASAX AI: Enable HTTP remote control >> "%VLCRC%"
    echo extraintf=http >> "%VLCRC%"
    echo http-port=8080 >> "%VLCRC%"
    echo http-password=abrasax >> "%VLCRC%"
    echo http-src="%CD%\lua\http" >> "%VLCRC%"
    echo [✓] HTTP interface enabled on port 8080 (password: abrasax)
) else (
    echo [✓] HTTP interface already configured
)

:: ============================================================================
:: 2. ENABLE TELNET INTERFACE (for AI script control)
:: ============================================================================
echo.
echo [2/5] Enabling Telnet control interface...
findstr /c:"extraintf=telnet" "%VLCRC%" >nul 2>&1
if errorlevel 1 (
    echo # ABRASAX AI: Enable Telnet remote control >> "%VLCRC%"
    echo extraintf=telnet >> "%VLCRC%"
    echo telnet-port=4212 >> "%VLCRC%"
    echo telnet-password=abrasax >> "%VLCRC%"
    echo [✓] Telnet interface enabled on port 4212
) else (
    echo [✓] Telnet interface already configured
)

:: ============================================================================
:: 3. ENABLE WEB INTERFACE (fancy HTML5 remote)
:: ============================================================================
echo.
echo [3/5] Setting up Web UI remote...
set "WEB_DIR=%APPDATA%\vlc\lua\http"
if not exist "%WEB_DIR%" mkdir "%WEB_DIR%"
if not exist "%WEB_DIR%\.hosts" (
    echo localhost > "%WEB_DIR%\.hosts"
    echo 127.0.0.1 >> "%WEB_DIR%\.hosts"
    echo ::1 >> "%WEB_DIR%\.hosts"
    echo [✓] Web UI access list created (localhost only)
) else (
    echo [✓] Web UI already configured
)

:: ============================================================================
:: 4. ENABLE SCENE DETECTION (auto-thumbnail generation)
:: ============================================================================
echo.
echo [4/5] Enabling AI scene detection...
set "THUMBS=C:\Users\BASEDGOD\Desktop\_SCRIPTS\vlc\thumbnails"
if not exist "%THUMBS%" mkdir "%THUMBS%"
findstr /c:"scene-filter" "%VLCRC%" >nul 2>&1
if errorlevel 1 (
    echo # ABRASAX AI: Scene detection for thumbnail generation >> "%VLCRC%"
    echo scene-filter=scene >> "%VLCRC%"
    echo scene-ratio=100 >> "%VLCRC%"
    echo scene-prefix=abrasax_snap_ >> "%VLCRC%"
    echo scene-path=%THUMBS% >> "%VLCRC%"
    echo scene-format=png >> "%VLCRC%"
    echo scene-width=320 >> "%VLCRC%"
    echo scene-height=180 >> "%VLCRC%"
    echo [✓] Scene detection enabled (snapshots every 100 frames)
) else (
    echo [✓] Scene detection already configured
)

:: ============================================================================
:: 5. ENABLE VLC LOGGING (for AI analysis)
:: ============================================================================
echo.
echo [5/5] Enabling debug logging for AI analysis...
set "LOGDIR=C:\Users\BASEDGOD\Desktop\_SCRIPTS\vlc\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
findstr /c:"verbose=2" "%VLCRC%" >nul 2>&1
if errorlevel 1 (
    echo # ABRASAX AI: Verbose logging for AI analysis >> "%VLCRC%"
    echo verbose=2 >> "%VLCRC%"
    echo logmode=text >> "%VLCRC%"
    echo logfile=%LOGDIR%\vlc_debug.log >> "%VLCRC%"
    echo [✓] Verbose logging enabled
) else (
    echo [✓] Logging already configured
)

:: ============================================================================
:: SUMMARY
:: ============================================================================
echo.
echo ╔══════════════════════════════════════════════════════════════════════════╗
echo ║     ADD-ONS INSTALLED:                                                 ║
echo ║                                                                        ║
echo ║  [✓] HTTP Web Remote   → http://localhost:8080  (pass: abrasax)       ║
echo ║  [✓] Telnet Control    → telnet localhost 4212   (pass: abrasax)       ║
echo ║  [✓] Web UI            → http://localhost:8080                         ║
echo ║  [✓] Scene Detection   → Auto-thumbnails every 100 frames              ║
echo ║  [✓] Verbose Logging   → C:\...\_SCRIPTS\vlc\logs\vlc_debug.log       ║
echo ║  [✓] VLSub             → Subtitle downloader (already installed)       ║
echo ║                                                                        ║
echo ║  EXISTING (built-in):                                                  ║
echo ║  [✓] 497 modules      → D3D11VA, DXVA2, NVDEC, projectM, etc.         ║
echo ║  [✓] 41 video filters → adjust, sharpen, hqdn3d, gradfun, etc.        ║
echo ║  [✓] 25 audio filters → compressor, equalizer, spatializer, etc.       ║
echo ║  [✓] Lua extensions   → VLSub, HTTP, Telnet, CLI, Dummy               ║
echo ╚══════════════════════════════════════════════════════════════════════════╝
echo.
echo  PRESS ANY KEY to launch VLC with ALL add-ons active...
pause >nul

:: Launch VLC with all add-ons enabled
start "" "C:\Program Files\VideoLAN\VLC\vlc.exe" ^
    --extraintf=http --extraintf=telnet --extraintf=hotkeys ^
    --http-port=8080 --http-password=abrasax ^
    --telnet-port=4212 --telnet-password=abrasax ^
    --avcodec-hw=any --avcodec-hw-decoding=yes --avcodec-threads=16 ^
    --direct3d11-hw-decoding --dxva2=on --d3d11va=on --vout=direct3d11 ^
    --video-filter=sharpen,adjust,deinterlace ^
    --sharpen-intensity=0.35 --adjust-contrast=1.08 ^
    --deinterlace=1 --deinterlace-mode=yadif ^
    --audio-filter=compressor,equalizer,spatializer ^
    --compressor-level=4.0 --equalizer-preset=fullbass ^
    --playlist-autostart --loop --repeat ^
    --no-video-title-show --video-on-top ^
    "C:\Users\BASEDGOD\Desktop\_SCRIPTS\vlc\playlists\ehgeh.xspf"

echo.
echo [✓] VLC launched with ALL add-ons + AI enhancements
echo     Open http://localhost:8080 in browser for web remote
echo     Telnet: localhost:4212 (pass: abrasax)
echo.
pause
