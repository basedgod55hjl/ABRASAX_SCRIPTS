@echo off
REM ============================================================
REM  Claude Code CLI — DeepSeek API Backend
REM  Launcher: bypasses all permissions, sets env vars, starts Claude
REM ============================================================
title Claude Code (DeepSeek v4 Pro)

REM ============================================================
REM  DANGER ZONE — bypass ALL Claude Code permission prompts
REM ============================================================
set CLAUDE_CODE_DANGEROUSLY_SKIP_PERMISSIONS=1
set CLAUDE_CODE_SKIP_PERMISSION_PROMPTS=1
set CLAUDE_CODE_BYPASS_ALL=1
set CLAUDE_CODE_NO_AUTH=1
set CLAUDE_CODE_ALLOW_DANGEROUSLY_SKIP_PERMISSIONS=1

REM ============================================================
REM  GLOBAL DEEPSEEK CONFIG  (secrets never hardcoded here)
REM  Persisted at user scope: HKCU\Environment\DEEPSEEK_API_KEY
REM ============================================================
for /f "tokens=2,*" %%A in ('reg query "HKCU\Environment" /v DEEPSEEK_API_KEY 2^>nul ^| findstr /i DEEPSEEK_API_KEY') do set "DEEPSEEK_API_KEY=%%B"
if not defined DEEPSEEK_API_KEY (
    echo [!!] DEEPSEEK_API_KEY is not set. Set it once with:
    echo      setx DEEPSEEK_API_KEY "sk-..."
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
set CLAUDE_CODE_EFFORT_LEVEL=max

REM --- JEV / TypeSafe System One decision engine ---
if not defined TYPESAFE_BASE_URL set "TYPESAFE_BASE_URL=https://api.typesafe.ai/v1/systemone"
if not defined TYPESAFE_MODEL set "TYPESAFE_MODEL=jev-latest"
if not defined ABRASAX_JEV_LOCAL_URL set "ABRASAX_JEV_LOCAL_URL=http://127.0.0.1:8000/v1/systemone"

REM ============================================================
REM  Performance & reliability
REM ============================================================
set API_TIMEOUT_MS=1200000
set BASH_DEFAULT_TIMEOUT_MS=300000
set BASH_MAX_TIMEOUT_MS=600000
set MAX_MCP_OUTPUT_TOKENS=50000
set CLAUDE_CODE_MAX_OUTPUT_TOKENS=32000
set CLAUDE_CODE_MAX_THINKING_TOKENS=32768
set CLAUDE_CODE_MAX_RETRIES=5
set CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY=10
set MCP_TIMEOUT=30000
set CLAUDE_CODE_AUTO_LOAD_MCPS=1

REM ============================================================
REM  Privacy (disable telemetry)
REM ============================================================
set CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
set DISABLE_TELEMETRY=1
set DISABLE_ERROR_REPORTING=1

REM ============================================================
REM  PowerMode: bypass PowerShell execution policy
REM ============================================================
set CLAUDE_PS1=%APPDATA%\npm\claude.ps1

echo.
echo   ██████╗██╗      █████╗ ██╗   ██╗██████╗ ███████╗
echo  ██╔════╝██║     ██╔══██╗██║   ██║██╔══██╗██╔════╝
echo  ██║     ██║     ███████║██║   ██║██║  ██║█████╗  
echo  ██║     ██║     ██╔══██║██║   ██║██║  ██║██╔══╝  
echo  ╚██████╗███████╗██║  ██║╚██████╔╝██████╔╝███████╗
echo   ╚═════╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝
echo.
echo   Model : %ANTHROPIC_MODEL% (via DeepSeek API)
echo   Sub   : %CLAUDE_CODE_SUBAGENT_MODEL%
echo   Perms : BYPASSED (no confirm prompts)
echo.

if exist "%CLAUDE_PS1%" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%CLAUDE_PS1%" --model deepseek-v4-pro --dangerously-skip-permissions %*
) else (
    claude.cmd --model deepseek-v4-pro --dangerously-skip-permissions %*
)
