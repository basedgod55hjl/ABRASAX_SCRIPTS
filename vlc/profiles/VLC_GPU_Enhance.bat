@echo off
REM ============================================================================
REM  VLC_GPU_Enhance.bat — wrapper for VLC_GPU_Enhance.ps1
REM  Needed because this system's PowerShell execution policy blocks unsigned
REM  scripts (-File fails with "is not digitally signed"). Bypass is scoped to
REM  this one invocation; the machine-wide policy is NOT changed.
REM
REM  Usage:  VLC_GPU_Enhance.bat -InFile "G:\path\video.mp4" -Preset hybrid
REM          VLC_GPU_Enhance.bat -Preset list
REM          ...or drag a video file onto this .bat to run the default preset.
REM ============================================================================
setlocal

set "PS1=%~dp0VLC_GPU_Enhance.ps1"

if "%~1"=="" (
    echo.
    echo   No arguments given. Showing available presets...
    echo.
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Preset list
    echo.
    echo   Usage:  %~nx0 -Input "G:\path\video.mp4" -Preset ^<name^>
    echo   Or just drag a video file onto this .bat.
    echo.
    pause
    exit /b 0
)

REM Drag-and-drop support: if the first arg is an existing file, treat as -InFile
if exist "%~1" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -InFile "%~1" -Preset %PRESET%
) else (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
)

endlocal
