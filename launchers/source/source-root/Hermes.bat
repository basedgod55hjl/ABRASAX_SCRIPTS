@echo off
chcp 65001 >nul
title Hermes Agent — DeepSeek V4 Pro
set "HERMES_HOME=%USERPROFILE%\AppData\Local\hermes"

REM ============================================================
REM  GLOBAL DEEPSEEK CONFIG  (secrets never hardcoded here)
REM  Persisted at user scope: HKCU\Environment\DEEPSEEK_API_KEY
REM  Note: Hermes also loads %HERMES_HOME%\.env with override=True,
REM        so the values there win for the Hermes process.
REM ============================================================
for /f "tokens=2,*" %%A in ('reg query "HKCU\Environment" /v DEEPSEEK_API_KEY 2^>nul ^| findstr /i DEEPSEEK_API_KEY') do set "DEEPSEEK_API_KEY=%%B"
REM Fall back to the files Hermes itself trusts, newest first. A key in %HERMES_HOME%\.env
REM outranks the registry (Hermes loads that file with override=True), so refusing to start
REM when only the file has it -- which is the state of this host -- gets the order backwards.
if not defined DEEPSEEK_API_KEY if exist "%HERMES_HOME%\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%HERMES_HOME%\.env") do (
        if /i "%%A"=="DEEPSEEK_API_KEY" set "DEEPSEEK_API_KEY=%%B"
    )
)
if not defined DEEPSEEK_API_KEY if exist "C:\abrasax\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("C:\abrasax\.env") do (
        if /i "%%A"=="DEEPSEEK_API_KEY" set "DEEPSEEK_API_KEY=%%B"
    )
)
if not defined DEEPSEEK_API_KEY (
    echo [!!] DEEPSEEK_API_KEY is not set anywhere. Looked in:
    echo      HKCU\Environment
    echo      %HERMES_HOME%\.env
    echo      C:\abrasax\.env
    echo      Set it once with:  setx DEEPSEEK_API_KEY "sk-..."
    pause
    exit /b 1
)

set "DEEPSEEK_BASE_URL=https://api.deepseek.com"
set "DEEPSEEK_UPSTREAM_URL=https://api.deepseek.com/v1"
set "DEEPSEEK_BETA_BASE_URL=https://api.deepseek.com/beta"
set "DEEPSEEK_ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic"
set "DEEPSEEK_PRIMARY_MODEL=deepseek-v4-pro"
set "DEEPSEEK_FAST_MODEL=deepseek-flash"
set "DEEPSEEK_VISION_MODEL=deepseek-flash"
set "DEEPSEEK_MODEL=%DEEPSEEK_PRIMARY_MODEL%"
set "DEEPSEEK_SAFETY_OFF=1"
set "DEEPSEEK_BYPASS_ALL=1"
set "DEEPSEEK_UNRESTRICTED=1"
set "DEEPSEEK_VISION_NATIVE=1"

REM --- Anthropic-compatible surface ---
set "ANTHROPIC_BASE_URL=%DEEPSEEK_ANTHROPIC_BASE_URL%"
set "ANTHROPIC_AUTH_TOKEN=%DEEPSEEK_API_KEY%"
REM Claude Code warns (and may pick a stale stored key) when ANTHROPIC_API_KEY is
REM also set. Clear it so only the token is used.
set "ANTHROPIC_API_KEY="
set "ANTHROPIC_MODEL=%DEEPSEEK_PRIMARY_MODEL%"
set "ANTHROPIC_DEFAULT_OPUS_MODEL=%DEEPSEEK_PRIMARY_MODEL%"
set "ANTHROPIC_DEFAULT_SONNET_MODEL=%DEEPSEEK_PRIMARY_MODEL%"
set "ANTHROPIC_DEFAULT_HAIKU_MODEL=%DEEPSEEK_FAST_MODEL%"
set "CLAUDE_CODE_SUBAGENT_MODEL=%DEEPSEEK_FAST_MODEL%"
set "CLAUDE_DEFAULT_MODEL=%DEEPSEEK_PRIMARY_MODEL%"

REM --- JEV / TypeSafe System One decision engine ---
if not defined TYPESAFE_BASE_URL set "TYPESAFE_BASE_URL=https://api.typesafe.ai/v1/systemone"
if not defined TYPESAFE_MODEL set "TYPESAFE_MODEL=jev-latest"
if not defined ABRASAX_JEV_LOCAL_URL set "ABRASAX_JEV_LOCAL_URL=http://127.0.0.1:8000/v1/systemone"

REM --- Locate the Hermes executable (AppData bin first, venv + git fallbacks) ---
set "HERMES_EXE=%HERMES_HOME%\bin\hermes.exe"
if not exist "%HERMES_EXE%" set "HERMES_EXE=%HERMES_HOME%\hermes-agent\venv\Scripts\hermes.exe"
if not exist "%HERMES_EXE%" set "HERMES_EXE=%USERPROFILE%\hermes\hermes-agent\venv\Scripts\hermes.exe"
if not exist "%HERMES_EXE%" (
    echo [!!] Hermes executable not found. Looked in:
    echo      %HERMES_HOME%\hermes-agent\venv\Scripts\
    echo      %USERPROFILE%\hermes\hermes-agent\venv\Scripts\
    pause
    exit /b 1
)

cls
echo   ABRASAX — Hermes Agent (DeepSeek V4 Pro)
echo   Endpoint: %DEEPSEEK_BASE_URL%  ^| JEV: %TYPESAFE_MODEL%
echo   Commands: /model flash ^| /moa select deepseek-moa ^| /help
echo   ==============================================
"%HERMES_EXE%"
pause
