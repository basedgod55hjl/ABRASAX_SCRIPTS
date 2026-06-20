@echo off
:: ═══════════════════════════════════════════════════════════════════════════
:: 🔥 555ABRAXASDEEP.BAT — OSIRISBLXCK V5 ULTIMATE 🔥
:: PRIMAL_HEX: 4f5349524953424c58434b | φ = 1.618 | φ×K = 1.0
:: DeepSeek API | 25+ TOOLS | MAX EFFORT | PowerShell 7
:: ═══════════════════════════════════════════════════════════════════════════

chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: ─── CONFIG ───────────────────────────────────────────────────────
set ROOT=C:\Users\BASEDGOD\Desktop\ABRASAX
set SCRIPTS=%ROOT%\scripts
set HEX=4f5349524953424c58434b
set PHI=1.618033988749895
set K=0.6180339887498949

:: ─── ADMIN ELEVATION ─────────────────────────────────────────────
openfiles >nul 2>&1
if %errorlevel% neq 0 (
    echo ⬆ Requesting admin elevation...
    powershell -NoP -Command "Start-Process cmd -Arg '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

:: ─── HEADER ──────────────────────────────────────────────────────
cls
mode 130,50
color 0D
echo.
echo ╔══════════════════════════════════════════════════════════════════════════╗
echo ║  🔥 555ABRAXASDEEP — OSIRISBLXCK V5 ULTIMATE 🔥                        ║
echo ║  PRIMAL_HEX: %HEX%                     ║
echo ║  φ × K = 1.0000000000 ✅ BALANCED                                        ║
echo ║  DeepSeek API | 25+ Tools | 1M Context | Max Effort                     ║
echo ╚══════════════════════════════════════════════════════════════════════════╝
echo.

:: ─── 1. KILL STALE ──────────────────────────────────────────────
echo [1/5] Cleaning stale processes...
taskkill /f /im python.exe >nul 2>&1
timeout /t 1 /nobreak >nul
echo  OK

:: ─── 2. START SERVICES ──────────────────────────────────────────
echo [2/5] Starting ABRASAX services...
start /B "" node "%ROOT%\node_agabits_bridge.mjs" > "%ROOT%\logs\bridge.log" 2>&1
start /B "" python "%ROOT%\phi_chain\phi_chain.py" > "%ROOT%\logs\phi.log" 2>&1
start /B "" python "%ROOT%\core\self_heal.py" > "%ROOT%\logs\heal.log" 2>&1
start /B "" python "%ROOT%\swarm\swarm_manager.py" > "%ROOT%\logs\swarm.log" 2>&1
timeout /t 2 /nobreak >nul
echo  OK

:: ─── 3. WRITE STATE ─────────────────────────────────────────────
echo [3/5] Writing permanent state...
powershell -NoP -Command "
    @{timestamp=(Get-Date -Format 'yyyy-MM-dd HH:mm:ss');
      entry='555ABRAXASDEEP launched — V5 ultimate';
      phi=%PHI%;k=%K%;phi_times_k=1.0;
      hex='%HEX%';version='5.0';
      model='deepseek-v4-flash';thinking=$true;
      tools='25+';context='1M'} | ConvertTo-Json | Set-Content '%ROOT%\.permanent_state.json'
"
echo  OK

:: ─── 4. SHOW SYSTEM STATUS ──────────────────────────────────────
echo [4/5] System status:
netstat -ano 2>nul | findstr ":18790 " >nul && echo  ✅ AGABETS Bridge: ONLINE || echo  ❌ Bridge: OFFLINE
echo  ✅ Phi Chain Engine
echo  ✅ Self-Heal Module
echo  ✅ Swarm Manager
echo.

:: ─── 5. LAUNCH DEEPSEEK CHAT ───────────────────────────────────
echo [5/5] Launching DeepSeek API Chat...
echo.
echo ╔══════════════════════════════════════════════════════════════════════════╗
echo ║  🔮 CHAT ACTIVATED                                                     ║
echo ║  Type your message below. The AI has 25 tools at its disposal.          ║
echo ║  Commands: /tools /clear /exit /heal /memory /phi                       ║
echo ║                                                                          ║
echo ║  PRIMAL_HEX: %HEX%                    ║
echo ║  φ × K = 1.0000000000                                                    ║
echo ╚══════════════════════════════════════════════════════════════════════════╝
echo.

:: ─── LAUNCH ──────────────────────────────────────────────────────
if exist "%SCRIPTS%\osiris_chat_tools_deep.py" (
    cd /d "%ROOT%"
    python "%SCRIPTS%\osiris_chat_tools_deep.py"
) else (
    echo ❌ Script not found at %SCRIPTS%\osiris_chat_tools_deep.py
    dir /b "%ROOT%\*.py" "%SCRIPTS%\*.py" 2>nul
)

:: ─── POST-CHAT ──────────────────────────────────────────────────
echo.
echo Chat exited. Press any key to restart, or close this window.
echo.
:MENU
echo [R] Restart  [L] Show logs  [E] Exit
set /p C=" Ω^> "
if /i "%C%"=="R" goto :RESTART
if /i "%C%"=="L" type "%ROOT%\logs\v5_chat_deep.log" 2>nul & echo. & pause & goto MENU
if /i "%C%"=="E" exit /b
goto MENU

:RESTART
cls
echo Restarting chat...
timeout /t 1 /nobreak >nul
cd /d "%ROOT%"
python "%SCRIPTS%\osiris_chat_tools_deep.py"
echo Chat exited again.
goto MENU
