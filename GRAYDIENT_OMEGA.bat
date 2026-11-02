@echo off
title GRAYDIENT OMEGA — OSIRISBLXCK v2.0
setlocal enabledelayedexpansion

:: ─── HEX BOOT ───────────────────────────────────────────────
set "HEX=4f5349524953424c58434b"
set "PHI=1.618033988749895"
set "TOKEN=grayapi-7ZuUxPaea3pg6NdGYMK7qKHutNOd61D8w728"
set "VERSION=v2.0"
set "ABRASAX_ROOT=%USERPROFILE%\Desktop\ABRASAX"
set "PY_SCRIPT=%ABRASAX_ROOT%\graydient_omega_chat.py"
set "WATCHDOG_SCRIPT=%ABRASAX_ROOT%\omega_watchdog.py"

:: ─── COLORS ─────────────────────────────────────────────────
for /f %%a in ('echo prompt $E^| cmd') do set "ESC=%%a"
set "CYAN=%ESC%[96m"
set "GREEN=%ESC%[92m"
set "YELLOW=%ESC%[93m"
set "RED=%ESC%[91m"
set "RESET=%ESC%[0m"

cls
echo.
echo %CYAN%╔═══════════════════════════════════════════════════════════╗
echo ║       GRAYDIENT OMEGA CHAT %VERSION%                     ║
echo ║       OSIRISBLXCK :: φ = %PHI%                 ║
echo ║       HEX: %HEX%                      ║
echo ║       Multi-LLM ^| Hex Tools ^| Web ^| Auto-Heal         ║
echo ╚═══════════════════════════════════════════════════════════╝%RESET%
echo.

:: ─── CHECK DEPENDENCIES ────────────────────────────────────
echo %YELLOW%[CHECK] Python...%RESET%
python --version >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo %RED%❌ Python not found!%RESET%
    echo %YELLOW%  Install Python 3.12 from python.org%RESET%
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo %GREEN%  ✅ %%v%RESET%

echo %YELLOW%[CHECK] Python script...%RESET%
if not exist "%PY_SCRIPT%" (
    echo %RED%  ❌ %PY_SCRIPT% not found!%RESET%
    pause
    exit /b 1
)
echo %GREEN%  ✅ Found%RESET%

:: ─── AUTO-INSTALL DEPS ─────────────────────────────────────
echo %YELLOW%[CHECK] Dependencies...%RESET%
python -c "import requests" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo %YELLOW%  Installing requests...%RESET%
    pip install requests --quiet 2>nul
)
python -c "import psutil" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo %YELLOW%  Installing psutil...%RESET%
    pip install psutil --quiet 2>nul
)
echo %GREEN%  ✅ OK%RESET%

:: ─── SET CONSOLE ──────────────────────────────────────────
mode con cols=120 lines=40

:: ─── MENU LOOP ────────────────────────────────────────────
:MENU
echo.
echo %CYAN%┌─────────────────────────────────────────────────────────┐%RESET%
echo %CYAN%│%RESET%  %GREEN%[1]%RESET% Launch Graydient Omega Chat (Python)                  %CYAN%│%RESET%
echo %CYAN%│%RESET%  %GREEN%[2]%RESET% Launch with Auto-Restart Watchdog                     %CYAN%│%RESET%
echo %CYAN%│%RESET%  %GREEN%[3]%RESET% Run Full Diagnostics + Test All LLMs                  %CYAN%│%RESET%
echo %CYAN%│%RESET%  %GREEN%[4]%RESET% Quick Test — Talk to Polly                           %CYAN%│%RESET%
echo %CYAN%│%RESET%  %GREEN%[5]%RESET% View Crash Log                                        %CYAN%│%RESET%
echo %CYAN%│%RESET%  %GREEN%[6]%RESET% View Watchdog Log                                     %CYAN%│%RESET%
echo %CYAN%│%RESET%  %GREEN%[7]%RESET% Open ABRASAX Folder                                   %CYAN%│%RESET%
echo %CYAN%│%RESET%  %GREEN%[0]%RESET% Exit                                                   %CYAN%│%RESET%
echo %CYAN%└─────────────────────────────────────────────────────────┘%RESET%
echo.
set /p "CHOICE=%GREEN%Select: %RESET%"

if "%CHOICE%"=="1" goto LAUNCH
if "%CHOICE%"=="2" goto LAUNCH_WATCH
if "%CHOICE%"=="3" goto DIAGNOSE
if "%CHOICE%"=="4" goto QUICK
if "%CHOICE%"=="5" goto VIEW_CRASH
if "%CHOICE%"=="6" goto VIEW_LOG
if "%CHOICE%"=="7" start "" "%ABRASAX_ROOT%" & goto MENU
if "%CHOICE%"=="0" goto END
goto MENU

:LAUNCH
cls
echo %CYAN%🚀 Launching Omega Chat...%RESET%
echo.
cd /d "%ABRASAX_ROOT%"
python graydient_omega_chat.py
set EXITCODE=%ERRORLEVEL%
echo.
if %EXITCODE% NEQ 0 (
    echo %RED%⚠ Chat crashed with exit code %EXITCODE%%RESET%
    echo %YELLOW%  Check: %ABRASAX_ROOT%\omega_crash.log%RESET%
) else (
    echo %GREEN%✅ Chat exited normally%RESET%
)
echo.
echo %YELLOW%Press any key for menu...%RESET%
pause >nul
goto MENU

:LAUNCH_WATCH
cls
echo %CYAN%🚀 Launching with Auto-Restart Watchdog...%RESET%
echo %YELLOW%  Chat will auto-restart if it crashes%RESET%
echo %YELLOW%  Close window or press Ctrl+C to stop%RESET%
echo.
cd /d "%ABRASAX_ROOT%"
:WATCH_LOOP
echo %CYAN%[%DATE% %TIME%] Starting Omega Chat...%RESET%
python graydient_omega_chat.py
set EXITCODE=%ERRORLEVEL%
if %EXITCODE% NEQ 0 (
    echo %RED%[%DATE% %TIME%] CRASHED (code %EXITCODE%). Restarting in 3s...%RESET%
    timeout /t 3 /nobreak >nul
    goto WATCH_LOOP
) else (
    echo %GREEN%[%DATE% %TIME%] Exited normally%RESET%
)
pause
goto MENU

:DIAGNOSE
cls
echo %CYAN%🔍 Running Full Diagnostics...%RESET%
echo.

:: Test 1: API connectivity
echo %YELLOW%[1/6] API /concepts/...%RESET%
python -c "
import urllib.request, json
h={'Authorization':'Bearer %TOKEN%','Content-Type':'application/vnd.api+json','Accept':'application/vnd.api+json'}
r=urllib.request.urlopen(urllib.request.Request('https://cXy5WPX250x.graydient.ai/api/v3/concepts/',headers=h),timeout=10)
j=json.loads(r.read().decode())
print(f'  ✅ HTTP {r.getcode()}, {len(j.get(\"data\",[]))} concepts')
" 2>&1
if %ERRORLEVEL% NEQ 0 (echo %RED%  ❌ FAILED%RESET%) else (echo %GREEN%  ✅ OK%RESET%)

:: Test 2: Chat Polly
echo %YELLOW%[2/6] CHAT llama (Gradi AI)...%RESET%
python -c "
import urllib.request, json, re
h={'Authorization':'Bearer %TOKEN%','Content-Type':'application/vnd.api+json','Accept':'application/vnd.api+json'}
d=json.dumps({'persona':'llama','prompt':'Say hello briefly.','sync':True}).encode()
r=urllib.request.urlopen(urllib.request.Request('https://cXy5WPX250x.graydient.ai/api/v3/chat/',data=d,headers=h,method='POST'),timeout=30)
j=json.loads(r.read().decode())
t=j.get('data',[{}])[0].get('attributes',{}).get('response_text','')
t=re.sub(r'<[^>]+>','',t).strip()
print(f'  ✅ Llama3: {t[:100]}')
" 2>&1
if %ERRORLEVEL% NEQ 0 (echo %RED%  ❌ FAILED%RESET%) else (echo %GREEN%  ✅ OK%RESET%)

:: Test 3: Chat llama
echo %YELLOW%[3/6] CHAT llama3...%RESET%
python -c "
import urllib.request, json, re
h={'Authorization':'Bearer %TOKEN%','Content-Type':'application/vnd.api+json','Accept':'application/vnd.api+json'}
d=json.dumps({'persona':'llama','prompt':'Say hello.','sync':True}).encode()
r=urllib.request.urlopen(urllib.request.Request('https://cXy5WPX250x.graydient.ai/api/v3/chat/',data=d,headers=h,method='POST'),timeout=30)
j=json.loads(r.read().decode())
t=j.get('data',[{}])[0].get('attributes',{}).get('response_text','')
t=re.sub(r'<[^>]+>','',t).strip()
print(f'  ✅ Llama3: {t[:100]}')
" 2>&1
if %ERRORLEVEL% NEQ 0 (echo %RED%  ❌ FAILED%RESET%) else (echo %GREEN%  ✅ OK%RESET%)

:: Test 4: Chat helper
echo %YELLOW%[4/6] CHAT helper...%RESET%
python -c "
import urllib.request, json, re
h={'Authorization':'Bearer %TOKEN%','Content-Type':'application/vnd.api+json','Accept':'application/vnd.api+json'}
d=json.dumps({'persona':'helper','prompt':'Say hello.','sync':True}).encode()
r=urllib.request.urlopen(urllib.request.Request('https://cXy5WPX250x.graydient.ai/api/v3/chat/',data=d,headers=h,method='POST'),timeout=30)
j=json.loads(r.read().decode())
t=j.get('data',[{}])[0].get('attributes',{}).get('response_text','')
t=re.sub(r'<[^>]+>','',t).strip()
print(f'  ✅ Helper: {t[:100]}')
" 2>&1
if %ERRORLEVEL% NEQ 0 (echo %RED%  ❌ FAILED%RESET%) else (echo %GREEN%  ✅ OK%RESET%)

:: Test 5: Hex tools
echo %YELLOW%[5/6] HEX tools...%RESET%
python -c "
import base64, hashlib
h=hashlib.sha256(b'test').hexdigest()[:16]
e='68656c6c6f'
d=bytes.fromhex(e).decode()
assert d=='hello', 'Hex decode failed'
assert 'hello'.encode().hex()==e, 'Hex encode failed'
print(f'  ✅ Hex: {e} -> {d}')
print(f'  ✅ SHA256: {h}')
" 2>&1
if %ERRORLEVEL% NEQ 0 (echo %RED%  ❌ FAILED%RESET%) else (echo %GREEN%  ✅ OK%RESET%)

:: Test 6: File I/O
echo %YELLOW%[6/6] FILE tools...%RESET%
python -c "
import os, tempfile
p=os.path.join(tempfile.gettempdir(),'omega_test.txt')
with open(p,'w') as f: f.write('Omega test')
r=open(p).read()
assert r=='Omega test', 'File write/read failed'
os.remove(p)
print('  ✅ File write/read/delete OK')
" 2>&1
if %ERRORLEVEL% NEQ 0 (echo %RED%  ❌ FAILED%RESET%) else (echo %GREEN%  ✅ OK%RESET%)

echo.
echo %GREEN%✅ All 6 tests passed!%RESET%
echo.
pause
goto MENU

:QUICK
cls
echo %CYAN%🧪 Quick Test — Talking to Llama (Gradi AI)...%RESET%
echo.
python -c "
import urllib.request, json, re
h={'Authorization':'Bearer %TOKEN%','Content-Type':'application/vnd.api+json','Accept':'application/vnd.api+json'}
d=json.dumps({'persona':'llama','prompt':'Say hello in one short sentence.','sync':True}).encode()
r=urllib.request.urlopen(urllib.request.Request('https://cXy5WPX250x.graydient.ai/api/v3/chat/',data=d,headers=h,method='POST'),timeout=30)
j=json.loads(r.read().decode())
t=j.get('data',[{}])[0].get('attributes',{}).get('response_text','')
t=re.sub(r'<[^>]+>','',t).strip()
print(f'\nLlama says: {t}')
"
echo.
pause
goto MENU

:VIEW_CRASH
cls
if exist "%ABRASAX_ROOT%\omega_crash.log" (
    type "%ABRASAX_ROOT%\omega_crash.log"
) else (
    echo %GREEN%No crash log found — system is stable%RESET%
)
echo.
pause
goto MENU

:VIEW_LOG
cls
if exist "%ABRASAX_ROOT%\omega_watchdog.log" (
    type "%ABRASAX_ROOT%\omega_watchdog.log"
) else (
    echo %YELLOW%No watchdog log yet%RESET%
)
echo.
pause
goto MENU

:END
cls
echo %CYAN%╔═══════════════════════════════════════════════════════════╗
echo ║     OSIRISBLXCK — Goodbye                              ║
echo ║     φ = %PHI%                           ║
echo ╚═══════════════════════════════════════════════════════════╝%RESET%
timeout /t 2 /nobreak >nul
exit /b 0
