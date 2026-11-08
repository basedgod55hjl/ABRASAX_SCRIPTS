#!/usr/bin/env python3
"""fix_hermes_bat_key.py -- Hermes.bat must not abort when the key lives in a .env.

Measured 2026-11-01 on this host:
    HKCU\\Environment\\DEEPSEEK_API_KEY  -> MISSING
    %LOCALAPPDATA%\\hermes\\.env         -> DEEPSEEK_API_KEY present (len 35)
    C:\\abrasax\\.env                     -> DEEPSEEK_API_KEY present

Hermes.bat read only the registry value and then `exit /b 1` with "setx DEEPSEEK_API_KEY",
so the launcher refused to start an agent that was already authenticated: Hermes loads
%HERMES_HOME%\\.env itself with override=True, i.e. the registry value is the *least*
authoritative source it has.

The guard now falls back through the two files that actually exist, in the order Hermes
itself trusts them, and only fails when none of the three has a value.

Run: python SCRIPTS/fix_hermes_bat_key.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

BAT = Path(r"C:\abrasax\SCRIPTS\launchers\source\source-root\Hermes.bat")

OLD = """for /f "tokens=2,*" %%A in ('reg query "HKCU\\Environment" /v DEEPSEEK_API_KEY 2^>nul ^| findstr /i DEEPSEEK_API_KEY') do set "DEEPSEEK_API_KEY=%%B"
if not defined DEEPSEEK_API_KEY (
    echo [!!] DEEPSEEK_API_KEY is not set. Set it once with:
    echo      setx DEEPSEEK_API_KEY "sk-..."
    pause
    exit /b 1
)"""

NEW = """for /f "tokens=2,*" %%A in ('reg query "HKCU\\Environment" /v DEEPSEEK_API_KEY 2^>nul ^| findstr /i DEEPSEEK_API_KEY') do set "DEEPSEEK_API_KEY=%%B"
REM Fall back to the files Hermes itself trusts, newest first. A key in %HERMES_HOME%\\.env
REM outranks the registry (Hermes loads that file with override=True), so refusing to start
REM when only the file has it -- which is the state of this host -- gets the order backwards.
if not defined DEEPSEEK_API_KEY if exist "%HERMES_HOME%\\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%HERMES_HOME%\\.env") do (
        if /i "%%A"=="DEEPSEEK_API_KEY" set "DEEPSEEK_API_KEY=%%B"
    )
)
if not defined DEEPSEEK_API_KEY if exist "C:\\abrasax\\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("C:\\abrasax\\.env") do (
        if /i "%%A"=="DEEPSEEK_API_KEY" set "DEEPSEEK_API_KEY=%%B"
    )
)
if not defined DEEPSEEK_API_KEY (
    echo [!!] DEEPSEEK_API_KEY is not set anywhere. Looked in:
    echo      HKCU\\Environment
    echo      %HERMES_HOME%\\.env
    echo      C:\\abrasax\\.env
    echo      Set it once with:  setx DEEPSEEK_API_KEY "sk-..."
    pause
    exit /b 1
)"""

MARK = "Looked in:"


def main() -> int:
    if not BAT.exists():
        print(f"MISSING {BAT}")
        return 2
    text = BAT.read_text(encoding="utf-8-sig", errors="replace")
    applied = MARK in text and "C:\\abrasax\\.env" in text

    if "--check" in sys.argv:
        print(("PASS " if applied else "FAIL ") + f"Hermes.bat key fallbacks={applied}")
        return 0 if applied else 1

    if applied:
        print("already patched: Hermes.bat")
        return 0
    if OLD not in text:
        print("FAIL  key guard anchor not found (file changed?)")
        return 1

    bak = BAT.with_suffix(".bat.bak-keyfallback")
    if not bak.exists():
        bak.write_text(text, encoding="utf-8")
    BAT.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched Hermes.bat: registry -> %HERMES_HOME%\\.env -> C:\\abrasax\\.env")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
