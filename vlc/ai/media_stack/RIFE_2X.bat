@echo off
REM ============================================================
REM  RIFE_2X — frame interpolation 2x pipeline (extract -> RIFE -> remux@2x)
REM  Verified 2026-10-03: rife-ncnn-vulkan TNTwise + rife-v4.12-lite, -j 2:2:2
REM  Usage: RIFE_2X.bat input.mp4 [output.mp4] [out_fps=60]
REM ============================================================
setlocal
set FF=%LOCALAPPDATA%\hermes\tools\ffmpeg-9.0.1-win32-x64\bin\ffmpeg.exe
set RIFEDIR=%USERPROFILE%\Desktop\ABRASAX_GOD_OS\tools\rife-ncnn-vulkan
set IN=%~1
set OUT=%~2
set FPS=%~3
if "%FPS%"=="" set FPS=60
if "%IN%"=="" (echo Usage: %~nx0 ^<input^> [output] [fps] & pause & exit /b 1)
if "%OUT%"=="" set OUT=%~dpn1_2x.mp4
set WORK=%TEMP%\rife_work

if not exist "%IN%" (echo [X] input not found: %IN% & pause & exit /b 1)
if exist "%WORK%" rmdir /s /q "%WORK%"
mkdir "%WORK%\in" 2>nul
mkdir "%WORK%\out" 2>nul

echo [1/3] Extracting frames...
"%FF%" -y -v error -i "%IN%" "%WORK%\in\%%08d.png" || (echo [X] extract failed & pause & exit /b 1)
dir /b "%WORK%\in" | find /c /v "" > "%WORK%\in_count.txt"

echo [2/3] RIFE 2x interpolation (v4.12-lite, threads 2:2:2)...
pushd "%RIFEDIR%"
rife-ncnn-vulkan.exe -i "%WORK%\in" -o "%WORK%\out" -m rife-v4.12-lite -j 2:2:2 || (popd & echo [X] RIFE failed & pause & exit /b 1)
popd

echo [3/3] Remuxing at %FPS% fps with NVENC...
"%FF%" -y -v error -framerate %FPS% -i "%WORK%\out\%%08d.png" -i "%IN%" -map 0:v -map 1:a? -c:v hevc_nvenc -preset p7 -tune uhq -cq 26 -b_ref_mode middle -c:a copy "%OUT%" || (echo [X] remux failed & pause & exit /b 1)

echo [OK] %OUT%   (workspace: %WORK%)
pause
endlocal
