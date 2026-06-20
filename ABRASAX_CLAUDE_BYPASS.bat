@echo off
title ABRASAX LMSTUDIO CLAUDE BYPASS
color 0A
echo.
echo  [OSIRISBLXCK] Claude Code Bypass Engine
echo  [PRIMAL_HEX] 4f5349524953424c58434b
echo  [LLM]        google/gemma-4-e2b@localhost:1234
echo.
set ANTHROPIC_BASE_URL=http://127.0.0.1:1234/v1
set ANTHROPIC_API_KEY=sk-bypass-osirisblxck
set CLAUDE_BASE_URL=http://127.0.0.1:1234/v1
set CLAUDE_API_KEY=sk-bypass-osirisblxck
set CLAUDE_MODEL=google/gemma-4-e2b
set CLAUDE_TELEMETRY_DISABLED=1
echo  [*] Variables injected. Bypass active.
echo  [*] Launching Claude Code CLI via LM Studio...
echo.
claude %*
echo.
echo  [!] Exited. Code: %ERRORLEVEL%
pause
