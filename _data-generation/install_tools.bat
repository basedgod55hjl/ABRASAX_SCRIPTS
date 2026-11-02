@echo off
echo ====================================
echo  ABRASAX Package Installer
echo ====================================
echo Installing development tools via winget...
echo.

REM Check if winget is available
where winget >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] winget not found. Install App Installer from Microsoft Store.
    pause
    exit /b 1
)

echo [1/6] Installing Git...
winget install --id Git.Git -e --silent --accept-package-agreements
if %ERRORLEVEL% EQU 0 ( echo [OK] Git installed ) else ( echo [WARN] Git install returned %ERRORLEVEL% )

echo [2/6] Installing Visual Studio Code...
winget install --id Microsoft.VisualStudioCode -e --silent --accept-package-agreements
if %ERRORLEVEL% EQU 0 ( echo [OK] VS Code installed ) else ( echo [WARN] VS Code install returned %ERRORLEVEL% )

echo [3/6] Installing Node.js LTS...
winget install --id OpenJS.NodeJS.LTS -e --silent --accept-package-agreements
if %ERRORLEVEL% EQU 0 ( echo [OK] Node.js installed ) else ( echo [WARN] Node.js install returned %ERRORLEVEL% )

echo [4/6] Installing Python 3...
winget install --id Python.Python.3.12 -e --silent --accept-package-agreements
if %ERRORLEVEL% EQU 0 ( echo [OK] Python installed ) else ( echo [WARN] Python install returned %ERRORLEVEL% )

echo [5/6] Installing FFmpeg...
winget install --id Gyan.FFmpeg -e --silent --accept-package-agreements
if %ERRORLEVEL% EQU 0 ( echo [OK] FFmpeg installed ) else ( echo [WARN] FFmpeg install returned %ERRORLEVEL% )

echo [6/6] Installing 7-Zip...
winget install --id 7zip.7zip -e --silent --accept-package-agreements
if %ERRORLEVEL% EQU 0 ( echo [OK] 7-Zip installed ) else ( echo [WARN] 7-Zip install returned %ERRORLEVEL% )

echo.
echo ====================================
echo  Installation complete!
echo  Check output above for any warnings.
echo ====================================
pause
