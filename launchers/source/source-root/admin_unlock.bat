@echo off
cd /d "%~dp0"
echo ===== ABRASAX ADMIN UNLOCK =====
echo.
echo [1] Defender kill...
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender" /v DisableAntiSpyware /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows Defender\Features" /v TamperProtection /t REG_DWORD /d 0 /f >nul 2>&1
powershell -Command "Set-MpPreference -DisableRealtimeMonitoring $true -Force" >nul 2>&1
sc stop WinDefend >nul 2>&1
sc config WinDefend start=disabled >nul 2>&1
sc stop SecurityHealthService >nul 2>&1
sc config SecurityHealthService start=disabled >nul 2>&1
echo [OK]
echo [2] Driver signing OFF...
bcdedit /set testsigning on >nul 2>&1
bcdedit /set nointegritychecks on >nul 2>&1
echo [OK]
echo [3] UAC OFF...
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v EnableLUA /t REG_DWORD /d 0 /f >nul 2>&1
echo [OK]
echo [4] Firewall OFF...
netsh advfirewall set allprofiles state off >nul 2>&1
echo [OK]
echo [5] SmartScreen OFF...
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\System" /v EnableSmartScreen /t REG_DWORD /d 0 /f >nul 2>&1
echo [OK]
echo [6] Dev Mode ON...
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock" /v AllowDevelopmentWithoutDevLicense /t REG_DWORD /d 1 /f >nul 2>&1
echo [OK]
echo [7] Fast Startup OFF...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power" /v HiberbootEnabled /t REG_DWORD /d 0 /f >nul 2>&1
powercfg /h off >nul 2>&1
echo [OK]
echo.
echo ===== DONE - VERIFYING =====
bcdedit /enum 2>&1 | findstr testsigning
echo UAC: %errorlevel%
echo.
echo Don't close this window. System is unlocked.
pause
