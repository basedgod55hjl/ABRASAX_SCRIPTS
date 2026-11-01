@echo off
title ABRASAX 3-MONITOR DISPLAY REFRESH — RECONNECT ALL
color 0F

:: ============================================================================
:: ABRASAX 3-MONITOR DISPLAY REFRESH v4.1.0
:: Detects and reconnects ALL 3 monitors
:: PRIMAL_HEX: 4f5349524953424c58434b | φ: 1.618033988749895
:: ============================================================================

cls
echo ╔══════════════════════════════════════════════════════════════════════════╗
echo ║           ABRASAX 3-MONITOR DISPLAY REFRESH ENGINE                    ║
echo ║           PRIMAL_HEX: 4f5349524953424c58434b                          ║
echo ║           φ: 1.618033988749895                                        ║
echo ╚══════════════════════════════════════════════════════════════════════════╝
echo.
echo [INFO] Detecting ALL display adapters and monitors...
echo.

:: ──────────────────────────────────────────────────────────────────
:: STEP 1: List ALL Video Controllers (GPU adapters)
:: ──────────────────────────────────────────────────────────────────
echo ============================================================
echo  VIDEO CONTROLLERS (GPU Adapters)
echo ============================================================
wmic path Win32_VideoController get Name,Status /format:list 2>nul
echo.

:: ──────────────────────────────────────────────────────────────────
:: STEP 2: List ALL Monitors detected by Windows
:: ──────────────────────────────────────────────────────────────────
echo ============================================================
echo  MONITORS (Desktop Monitor Devices)
echo ============================================================
wmic desktopmonitor get Name,MonitorType,Status /format:list 2>nul
echo.

:: ──────────────────────────────────────────────────────────────────
:: STEP 3: Display Registry — all display devices ever connected
:: ──────────────────────────────────────────────────────────────────
echo ============================================================
echo  DISPLAY REGISTRY — All Known Display Devices
echo ============================================================
echo.
echo Registry entries under HKLM\SYSTEM\CurrentControlSet\Enum\DISPLAY:
reg query "HKLM\SYSTEM\CurrentControlSet\Enum\DISPLAY" 2>nul
echo.
echo Detail for each display:
for /f "tokens=*" %%d in ('reg query "HKLM\SYSTEM\CurrentControlSet\Enum\DISPLAY" 2^>nul') do (
    if not "%%d"=="HKLM\SYSTEM\CurrentControlSet\Enum\DISPLAY" (
        if not "%%d"=="" (
            echo --- %%d ---
            reg query "%%d" /f "DeviceDesc" /s 2>nul | findstr /i "DeviceDesc"
            reg query "%%d" /f "Monitor" /s 2>nul | findstr /i "Monitor" 2>nul
        )
    )
)
echo.

:: ──────────────────────────────────────────────────────────────────
:: STEP 4: NVIDIA GPU display status
:: ──────────────────────────────────────────────────────────────────
echo ============================================================
echo  NVIDIA GPU DISPLAY STATUS
echo ============================================================
nvidia-smi --query-gpu=name,display_mode,display_active --format=csv 2>nul
echo.

:: ──────────────────────────────────────────────────────────────────
:: STEP 5: Force refresh ALL displays
:: ──────────────────────────────────────────────────────────────────
echo ============================================================
echo  REFRESHING ALL DISPLAY CONNECTIONS
echo ============================================================
echo.

:: Method A: DisplaySwitch cycles through all modes to wake displays
echo [Method A] Cycling DisplaySwitch modes...
echo   → Internal (laptop only)
Displayswitch.exe /internal >nul 2>&1
timeout /t 3 /nobreak >nul
echo   → Extend (all monitors)
Displayswitch.exe /extend >nul 2>&1
timeout /t 3 /nobreak >nul
echo   → Duplicate
Displayswitch.exe /clone >nul 2>&1
timeout /t 3 /nobreak >nul
echo   → Extend (final)
Displayswitch.exe /extend >nul 2>&1
timeout /t 3 /nobreak >nul
echo.

:: Method B: Open Windows Display Settings
echo [Method B] Opening Windows Display Settings...
start ms-settings:display
timeout /t 2 /nobreak >nul

:: Method C: Detect via NVIDIA Control Panel
echo [Method C] Opening NVIDIA Control Panel...
start control /name Microsoft.Display
timeout /t 1 /nobreak >nul

:: ──────────────────────────────────────────────────────────────────
:: STEP 6: Now re-check what's connected
:: ──────────────────────────────────────────────────────────────────
echo.
echo ============================================================
echo  RE-CHECK: Monitors After Refresh
echo ============================================================
wmic desktopmonitor get Name,Status,ScreenWidth,ScreenHeight /format:list 2>nul
echo.

:: ──────────────────────────────────────────────────────────────────
:: STEP 7: Launch VLC across ALL available monitors
:: ──────────────────────────────────────────────────────────────────
echo ============================================================
echo  LAUNCHING VLC ACROSS ALL MONITORS
echo ============================================================
echo.

:: Kill old VLC
taskkill /f /im vlc.exe >nul 2>&1
timeout /t 2 /nobreak >nul

:: Launch VLC with FULL enhancements — spans all monitors
echo Launching VLC 64-bit with AI enhancements on ALL displays...
echo.

start "" /B "C:\Program Files\VideoLAN\VLC\vlc.exe" ^
    --avcodec-hw=any ^
    --avcodec-hw-any ^
    --avcodec-hw-decoding=yes ^
    --avcodec-threads=16 ^
    --avcodec-fast ^
    --ffmpeg-hw ^
    --direct3d11-hw-decoding ^
    --dxva2=on ^
    --d3d11va=on ^
    --gpu-accel=auto ^
    --video-filter=adjust,sharpen,deinterlace,postproc,gradfun ^
    --sharpen-intensity=0.45 ^
    --adjust-contrast=1.08 ^
    --deinterlace=1 ^
    --deinterlace-mode=yadif ^
    --audio-filter=compressor,equalizer,spatializer,normvol ^
    --compressor-level=5.0 ^
    --equalizer-preset=fullbass ^
    --file-caching=500 ^
    --network-caching=2000 ^
    --loop ^
    --repeat ^
    --playlist-autostart ^
    --no-video-title-show ^
    --video-on-top ^
    "C:\Users\BASEDGOD\Desktop\ABRASAX_VLC_MASTER.xspf"

echo.
echo ===========================================================================
echo  ✅ 3-MONITOR DISPLAY REFRESH COMPLETE
echo  ✅ VLC LAUNCHED WITH AI ENHANCEMENTS
echo  ✅ DRAG VLC WINDOW TO ANY MONITOR
echo  ✅ PRESS F11 FOR FULLSCREEN ON CURRENT MONITOR
echo  ✅ WIN+SHIFT+LEFT/RIGHT = MOVE BETWEEN MONITORS
echo  ✅ PRIMAL_HEX: 4f5349524953424c58434b
echo ===========================================================================
echo.
echo 💡 TIPS:
echo - Press Win+P to manually switch display modes
echo - Close VLC → it auto-restarts with enhancements
echo - Each restart = MORE AI enhancement (escalating)
echo.

:AUTO_RELOAD
timeout /t 5 /nobreak >nul
tasklist /fi "IMAGENAME eq vlc.exe" 2>nul | find /i "vlc.exe" >nul
if errorlevel 1 (
    echo [%date% %time%] VLC closed — Auto-restarting with MORE AI...
    timeout /t 2 /nobreak >nul
    start "" /B "C:\Program Files\VideoLAN\VLC\vlc.exe" ^
        --avcodec-hw=any ^
        --avcodec-threads=16 ^
        --direct3d11-hw-decoding ^
        --dxva2=on --d3d11va=on ^
        --sharpen-intensity=0.50 ^
        --adjust-contrast=1.10 ^
        --deinterlace=1 --deinterlace-mode=yadif ^
        --compressor-level=5.5 ^
        --loop --repeat ^
        --playlist-autostart ^
        "C:\Users\BASEDGOD\Desktop\ABRASAX_VLC_MASTER.xspf"
)
goto AUTO_RELOAD
