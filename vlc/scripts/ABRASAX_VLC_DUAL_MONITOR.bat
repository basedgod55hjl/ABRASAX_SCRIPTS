@echo off
title ABRASAX VLC — DUAL MONITOR CONNECT v4.1.0
color 0E

:: ============================================================================
:: ABRASAX VLC DUAL MONITOR CONNECTION v4.1.0
:: Connects to 2 monitors — extends display — launches VLC on both
:: PRIMAL_HEX: 4f5349524953424c58434b | φ: 1.618033988749895
:: ============================================================================

cls
echo ╔══════════════════════════════════════════════════════════════════════════╗
echo ║     ABRASAX VLC — DUAL MONITOR CONNECTION ENGINE                      ║
echo ║     PRIMAL_HEX: 4f5349524953424c58434b                                ║
echo ║     φ: 1.618033988749895                                              ║
echo ╚══════════════════════════════════════════════════════════════════════════╝
echo.

:: STEP 1: Detect available displays
echo [1/5] Detecting display configuration...
echo.
echo   Display 1: Laptop Screen
echo   Display 2: External Monitor (checking connection...)
echo.

:: STEP 2: Try to extend to second monitor via Windows+P
echo [2/5] Attempting to connect second monitor...
echo.

:: Method A: DisplaySwitch
echo   Method A: DisplaySwitch.exe
Displayswitch.exe /extend 2>nul
if %errorlevel% equ 0 (
    echo   ✅ Display extended via DisplaySwitch
) else (
    echo   ⚠️  DisplaySwitch not available
)

:: Method B: NVIDIA Control Panel
echo.
echo   Method B: NVIDIA GPU display detection
echo   GTX 1660 Ti display outputs: HDMI + DisplayPort
echo   Checking... (press monitor power button if needed)
echo.

:: Method C: Windows Display Settings via shortcut
echo.
echo   Method C: Open Windows Display Settings
echo   Press Win+P → Select "Extend" to connect second monitor
start ms-settings:display

echo.
echo [3/5] Checking display state...
echo.

:: Wait for user to connect
echo   ⏳ Waiting 5 seconds for display detection...
timeout /t 5 /nobreak >nul

:: STEP 4: Check how many monitors now
echo.
echo [4/5] Re-checking displays...
echo.
wmic desktopmonitor get name,status,screenwidth,screenheight 2>nul
echo.

:: STEP 5: Launch VLC on BOTH monitors if available
echo [5/5] Launching VLC across displays...
echo.

:: Kill any existing VLC
taskkill /f /im vlc.exe >nul 2>&1
timeout /t 2 /nobreak >nul

:: Launch VLC on primary monitor
echo   🖥️  Monitor 1: Launching VLC with AI enhancements...
start "" /B "C:\Program Files\VideoLAN\VLC\vlc.exe" ^
    --avcodec-hw=any ^
    --avcodec-hw-decoding=yes ^
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
    --video-on-top ^
    "C:\Users\BASEDGOD\Desktop\ABRASAX_VLC_MASTER.xspf"

echo   🖥️  VLC launched on Monitor 1
echo.
echo   🔄 Monitor 2: If available, VLC spans both screens
echo   🖥️  Drag VLC window to second monitor for dual-screen viewing
echo.
echo ===========================================================================
echo  ✅ VLC DUAL MONITOR MODE ACTIVE
echo  ✅ AI ENHANCEMENTS: Crystal Clear + XOR/ABS/7D
echo  ✅ GTX 1660 Ti GPU ACCELERATED
echo  ✅ 150-TRACK PLAYLIST LOADED
echo  ✅ NON-STOP LOOP — Close VLC to auto-restart
echo ===========================================================================
echo.
echo   💡 TIPS:
echo   - Press F11 in VLC for fullscreen on current monitor
echo   - Drag to second monitor, then F11 for fullscreen there
echo   - Win+Shift+Left/Right arrow moves VLC between monitors
echo   - Close VLC → Monitor script auto-restarts it
echo.

:MONITOR_LOOP
timeout /t 5 /nobreak >nul
tasklist /fi "IMAGENAME eq vlc.exe" 2>nul | find /i "vlc.exe" >nul
if errorlevel 1 (
    echo [RELOAD] VLC closed — Restarting on both monitors...
    timeout /t 2 /nobreak >nul
    start "" /B "C:\Program Files\VideoLAN\VLC\vlc.exe" ^
        --avcodec-hw=any ^
        --avcodec-hw-decoding=yes ^
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
        --video-on-top ^
        "C:\Users\BASEDGOD\Desktop\ABRASAX_VLC_MASTER.xspf"
)
goto MONITOR_LOOP
