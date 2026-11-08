@echo off
rem ABRASAX boot chain (logon task AbrasaxStackBoot) — idempotent, no models.
rem 1) canonical stack starter (supervisor, build loop, ops monitor, HUD)
rem 2) resurrect watchdog (the no-one-dies layer; starts pinner/keeper/overlay/...)
rem 3) GGUFF loop pinned to deepseek (run-deepseek.cmd, NOT run.cmd)
echo [boot_abrasax] %DATE% %TIME% >> C:\ABRASAX\LOGS\boot_abrasax.log
powershell -NoProfile -ExecutionPolicy Bypass -File C:\ABRASAX\SCRIPTS\launchers\start_abrasax_stack.ps1 -NoModels -Quiet >> C:\ABRASAX\LOGS\boot_abrasax.log 2>&1
start "" /min powershell -NoProfile -Command "Start-Process -FilePath 'C:\Users\lucar\AppData\Local\Programs\Python\Python311\pythonw.exe' -ArgumentList 'C:\vlc-build\resurrect_watchdog.py' -WorkingDirectory 'C:\vlc-build' -WindowStyle Hidden"
start "" /min cmd /c C:\ABRASAX\GGUFF\run-deepseek.cmd
exit /b 0
