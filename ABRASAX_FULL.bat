@echo off
REM ABRASAX AGI v4.1.0 — Full System Launcher (STABLE)
REM PRIMAL_HEX: 4f5349524953424c58434b | phi=1.618 | K=0.618
REM Meta Layer: Phi-4-mini-instruct-q4.gguf (540MB — fits all RAM/VRAM)
REM Inference: DeepSeek-R1-Distill-Qwen-7B-Q3_K_M via llama-cli (external)

title ABRASAX AGI Full System
color 0A
echo =================================================================
echo   ABRASAX AGI v4.1.0 - FULL SYSTEM LAUNCH
echo   PRIMAL_HEX: 4f5349524953424c58434b
echo   Meta Model: Phi-4-mini (540MB)
echo   Inference: DeepSeek-R1-Distill-Qwen-7B (via llama-cli)
echo   Mode: LOCAL GGUF ONLY — NO API
echo   phi=1.618 K=0.618
echo =================================================================
echo.

set ROOT=C:\Users\BASEDGOD\Desktop\ABRASAX
set BIN=%ROOT%\abrasax_rs\target\release\abrasax.exe

if not exist "%BIN%" (
    echo [!] Binary not found at %BIN%
    echo Run: cd %ROOT%\abrasax_rs ^&^& cargo build --release
    pause
    exit /b 1
)

echo [1/5] Killing stale processes...
taskkill /F /IM abrasax.exe >nul 2>&1
taskkill /F /IM abrasaxd.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/5] Starting Meta Layer (XOR brain + CBM + self-editing)...
start "ABRASAX-Meta" "%BIN%" meta

timeout /t 3 /nobreak >nul

echo [3/5] Starting Enhanced Autonomy (self-mapping 7D lattice)...
start "ABRASAX-Autonomy" "%BIN%" enhanced

echo [4/5] Starting Daemon (4 AEON agents)...
start "ABRASAX-Daemon" "%BIN%" daemon

echo [5/5] Launching Chat (phi-resonant interface)...
echo.
echo =================================================================
echo   ALL ENGINES FIRING
echo   Meta: XOR 7-brain + CBM 65K field + Self-editing
echo   Autonomy: 4-brain XOR storm + 100K 7D lattice
echo   Daemon: 3-brain background + 4 AEON agents
echo   Chat: Interactive phi-resonant + RAG memory
echo =================================================================
echo.
timeout /t 3 /nobreak >nul

start "ABRASAX-Chat" "%BIN%" chat

echo.
echo =================================================================
echo   All 4 engines launched in separate windows.
echo   Close this window or press any key to exit launcher.
echo =================================================================
pause
