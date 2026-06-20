@echo off
title ABRASAX BYPASS LAUNCHER
color 0A
echo.
echo  [OSIRISBLXCK] ABRASAX BYPASS LAUNCHER
echo  [PRIMAL_HEX] 4f5349524953424c58434b
echo.
echo  Select bypass mode:
echo   1. Simple Bypass  (.bat hex - certutil decode)
echo   2. Dangerous Bypass (.ps1 - full env injection)
echo   3. Direct Bypass   (.bat - LM Studio variable set)
echo.
choice /c 123 /n /m "  Choose (1/2/3): "
if errorlevel 3 goto direct
if errorlevel 2 goto dangerous
if errorlevel 1 goto simple

:simple
echo.
echo  [*] Launching ABRASAX_HEX_BYPASS.bat...
start "" "C:\Users\BASEDGOD\Desktop\ABRASAX_HEX_BYPASS.bat"
goto end

:dangerous
echo.
echo  [*] Launching ABRASAX_DANGEROUS_HEX.ps1...
powershell -ExecutionPolicy Bypass -File "C:\Users\BASEDGOD\Desktop\ABRASAX_DANGEROUS_HEX.ps1"
goto end

:direct
echo.
echo  [*] Launching ABRASAX_CLAUDE_BYPASS.bat...
start "" "C:\Users\BASEDGOD\Desktop\ABRASAX_CLAUDE_BYPASS.bat"
goto end

:end
echo.
echo  [!] Session ended.
pause
