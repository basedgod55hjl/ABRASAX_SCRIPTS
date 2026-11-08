@echo off
chcp 65001 >nul
title Claude Code — DeepSeek V4 Pro

:: =============================================================================
:: ABRASAX — Claude Code with DeepSeek V4 Pro
:: =============================================================================

:: =============================================================================
:: GLOBAL DEEPSEEK CONFIG (secrets never hardcoded here)
:: Persisted at user scope: HKCU\Environment\DEEPSEEK_API_KEY
:: =============================================================================
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

:: Anthropic-compatible surface (Claude Code)
set "ANTHROPIC_BASE_URL=%DEEPSEEK_ANTHROPIC_BASE_URL%"
set "ANTHROPIC_AUTH_TOKEN=%DEEPSEEK_API_KEY%"
:: Claude Code warns (and may pick a stale stored key) when ANTHROPIC_API_KEY is
:: also set. Clear it so only the token is used.
set "ANTHROPIC_API_KEY="
set "ANTHROPIC_MODEL=%DEEPSEEK_PRIMARY_MODEL%"
set "ANTHROPIC_DEFAULT_OPUS_MODEL=%DEEPSEEK_PRIMARY_MODEL%"
set "ANTHROPIC_DEFAULT_SONNET_MODEL=%DEEPSEEK_PRIMARY_MODEL%"
set "ANTHROPIC_DEFAULT_HAIKU_MODEL=%DEEPSEEK_FAST_MODEL%"
set "CLAUDE_CODE_SUBAGENT_MODEL=%DEEPSEEK_FAST_MODEL%"

:: JEV / TypeSafe System One decision engine
if not defined TYPESAFE_BASE_URL set "TYPESAFE_BASE_URL=https://api.typesafe.ai/v1/systemone"
if not defined TYPESAFE_MODEL set "TYPESAFE_MODEL=jev-latest"
if not defined ABRASAX_JEV_LOCAL_URL set "ABRASAX_JEV_LOCAL_URL=http://127.0.0.1:8000/v1/systemone"

:: Force model — prevents Claude from trying "deepseek-v4-ultra"
set "CLAUDE_DEFAULT_MODEL=%DEEPSEEK_PRIMARY_MODEL%"

:: Max thinking tokens for reasoning
set "CLAUDE_MAX_THINKING_TOKENS=32768"

:: Skip permission prompts for speed
set "CLAUDE_CODE_SKIP_PERMISSIONS=1"

:: Disable telemetry/checks
set "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1"

cls
echo.
echo   ABRASAX OSIRISBLXCK — Claude Code
echo   Model:   DeepSeek V4 Pro
echo   API:     api.deepseek.com/anthropic
echo   Thinking: 32768 tokens max
echo   Mode:    Skip Permissions
echo   ==============================================
echo.

:: Use /model flag to force model on startup
"%USERPROFILE%\AppData\Roaming\npm\claude.cmd" --model deepseek-v4-pro %*
