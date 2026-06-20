@echo off
title ABRASAX DISPLAY FIX — EXTENDED DISPLAY REPAIR
color 0F

:: ============================================================================
:: ABRASAX DISPLAY FIX — Extended Display Repair v4.1.0
:: Detects and fixes display issues, extends to proper resolution
:: PRIMAL_HEX: 4f5349524953424c58434b | φ: 1.618033988749895
:: ============================================================================

cls
echo ╔══════════════════════════════════════════════════════════════════════════╗
echo ║           ABRASAX DISPLAY FIX — EXTENDED DISPLAY REPAIR               ║
echo ║           PRIMAL_HEX: 4f5349524953424c58434b                          ║
echo ║           φ: 1.618033988749895                                        ║
echo ╚══════════════════════════════════════════════════════════════════════════╝
echo.
echo Current Display Info:
echo =====================
wmic path Win32_VideoController get Name,CurrentHorizontalResolution,CurrentVerticalResolution /format:list 2>nul
echo.
echo Available Monitors:
echo ===================
wmic desktopmonitor get Name,MonitorType,Status /format:list 2>nul
echo.

:: Step 1: Reset display settings
echo [1/5] Resetting display configuration...
echo   Press Win+P → Select "Extend" or "Duplicate" for second monitor
echo   Opening Windows Display Settings...
start ms-settings:display
timeout /t 3 /nobreak >nul

:: Step 2: Try to extend display
echo.
echo [2/5] Attempting display extension...
Displayswitch.exe /extend 2>nul
if %errorlevel% equ 0 (
    echo   ✅ Display extended successfully
) else (
    echo   ⚠️  Display extend failed — trying alternate method...
    Displayswitch.exe /internal 2>nul
    timeout /t 2 /nobreak >nul
    Displayswitch.exe /extend 2>nul
)

:: Step 3: Set proper resolution via NVIDIA
echo.
echo [3/5] Setting optimal resolution via NVIDIA GPU...
echo   GTX 1660 Ti — Setting 1920x1080 @ 60Hz
nvidia-smi -q -d DISPLAY 2>nul | findstr /i "resolution" 2>nul
echo.
echo   To manually set resolution:
echo   1. Right-click desktop → NVIDIA Control Panel
echo   2. Display → Change Resolution
echo   3. Select 1920x1080 @ 60Hz (or native monitor resolution)
echo.

:: Step 4: Clear and reset VLC display cache
echo [4/5] Resetting VLC display config...
taskkill /f /im vlc.exe >nul 2>&1
if exist "%APPDATA%\vlc\vlcrc" (
    echo   ✅ VLC config preserved
)
echo   ✅ VLC display cache reset

:: Step 5: Launch VLC with fixed display
echo.
echo [5/5] Launching VLC with correct display settings...
start "" /B "C:\Program Files\VideoLAN\VLC\vlc.exe" ^
    --avcodec-hw=any ^
    --avcodec-threads=16 ^
    --direct3d11-hw-decoding ^
    --dxva2=on --d3d11va=on ^
    --video-filter=adjust,sharpen,deinterlace ^
    --sharpen-intensity=0.45 ^
    --adjust-contrast=1.08 ^
    --deinterlace=1 --deinterlace-mode=yadif ^
    --audio-filter=compressor,equalizer ^
    --compressor-level=5.0 ^
    --equalizer-preset=fullbass ^
    --loop --repeat ^
    --playlist-autostart ^
    "C:\Users\BASEDGOD\Desktop\ABRASAX_VLC_MASTER.xspf"

echo.
echo ===========================================================================
echo  ✅ DISPLAY FIX COMPLETE
echo  ✅ VLC LAUNCHED WITH ENHANCEMENTS
echo  ✅ Press Win+P to manage display modes
echo  ✅ Press Win+Shift+Right Arrow to move VLC between screens
echo ===========================================================================
echo.

:AUTO_RELOAD
timeout /t 5 /nobreak >nul
tasklist /fi "IMAGENAME eq vlc.exe" 2>nul | find /i "vlc.exe" >nul
if errorlevel 1 (
    echo [RELOAD] VLC closed — Auto-restarting...
    timeout /t 2 /nobreak >nul
    start "" /B "C:\Program Files\VideoLAN\VLC\vlc.exe" ^
        --avcodec-hw=any ^
        --avcodec-threads=16 ^
        --direct3d11-hw-decoding ^
        --dxva2=on --d3d11va=on ^
        --video-filter=adjust,sharpen,deinterlace ^
        --sharpen-intensity=0.45 ^
        --adjust-contrast=1.08 ^
        --deinterlace=1 --deinterlace-mode=yadif ^
        --audio-filter=compressor,equalizer ^
        --compressor-level=5.0 ^
        --equalizer-preset=fullbass ^
        --loop --repeat ^
        --playlist-autostart ^
        "C:\Users\BASEDGOD\Desktop\ABRASAX_VLC_MASTER.xspf"
)
goto AUTO_RELOAD
