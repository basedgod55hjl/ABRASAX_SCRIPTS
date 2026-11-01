@echo off
REM ============================================================================
REM  VLC_Profiles.bat — menu for the switchable VLC launch profiles
REM  (wraps VLC_Profile.ps1 with -ExecutionPolicy Bypass)
REM ============================================================================
setlocal
set "PS1=%~dp0VLC_Profile.ps1"
set "PL=C:\Users\sirch\Desktop\vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv.xspf"

:MENU
cls
echo ================================================================
echo   VLC LAUNCH PROFILES  -  AMD Vega iGPU + NVIDIA GTX 1660 Ti
echo ================================================================
echo.
echo   [1] nvidia  - GTX 1660 Ti renders (d3d11va + direct3d11)  [DEFAULT]
echo   [2] amd     - Radeon Vega iGPU renders (sets GpuPreference=1)
echo   [3] dxva2   - legacy DirectX 9 decoder fallback
echo   [4] gl      - OpenGL output + D3D11^<^>GL interop (GLSL shaders)
echo   [5] info    - show adapters / current GPU preference
echo   [P] play with chosen profile (uses the big playlist)
echo   [Q] quit
echo.
set /p CHOICE="  Select: "

if /i "%CHOICE%"=="1" ( call :run nvidia & goto MENU )
if /i "%CHOICE%"=="2" ( call :run amd    & goto MENU )
if /i "%CHOICE%"=="3" ( call :run dxva2  & goto MENU )
if /i "%CHOICE%"=="4" ( call :run gl     & goto MENU )
if /i "%CHOICE%"=="5" ( powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Profile info & pause & goto MENU )
if /i "%CHOICE%"=="Q" exit /b 0
goto MENU

:run
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Profile %1 -Media "%PL%"
pause
exit /b 0
