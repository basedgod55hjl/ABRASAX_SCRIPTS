"""Mark the dead launchers instead of silently "fixing" them.

EVIDENCE (audit_launchers.py, extractor corrected):
    9 launchers reference 14 paths that do not exist, all under
    C:\\Users\\sirch\\Desktop\\... -- the retired pre-migration tree.

And none of them is referenced by a scheduled task:
    Get-ScheduledTask | Where Actions -like '*STARTUP.bat*'  -> nothing
for STARTUP, ACCELERATE, AUTO_EVOLVE, EVERYTHING, CRON_MASTER.

So they are legacy. Rewriting their paths to C:\\ABRASAX would be guesswork: the
files they name (system_accelerator.py, auto_evolve.py, telegram/osirisblxck_v9.py)
may not exist in the new tree either, and inventing a working launcher for software
that is not there is worse than a clear marker.

This adds a leading REM warning to each dead launcher stating that it is legacy and
where the live equivalents are. It does not delete, does not edit commands, and is
idempotent.

dry-run by default.
"""
import os
import sys
import time

SCRIPTS = r"C:\ABRASAX\SCRIPTS"
APPLY = "--apply" in sys.argv

# measured dead launchers -> the live equivalent, if one exists
DEAD = {
    r"launchers\rust\rust-root\ACCELERATE.bat":
        "system_accelerator.py is not in C:\\ABRASAX",
    r"launchers\rust\rust-root\AUTO_EVOLVE.bat":
        "auto_evolve.py is not in C:\\ABRASAX",
    r"launchers\rust\rust-root\LAUNCH_VISIBLE.cmd":
        "targets 'Desktop\\ABRASAX AGI' which does not exist",
    r"launchers\rust\rust-root\STARTUP.bat":
        "use: python -m abrasax status  /  abrasax services",
    r"launchers\rust\rust-root\abrasax_core.cmd":
        "looks for C:\\Python31x\\python.exe; use PYTHON\\.venv_gui\\Scripts\\python.exe",
    r"launchers\source\source-root\ALL_SERVERS_ELEVATED.bat":
        "targets the retired ABRASAX_GOD_OS tree",
    r"launchers\source\source-root\CRON_MASTER.bat":
        "targets the retired ABRASAX_GOD_OS tree",
    r"launchers\source\source-root\setup.ps1":
        "targets the retired ABRASAX_GOD_OS tree",
    r"launchers\source\start_autoloop.bat":
        "targets the retired ABRASAX_GOD_OS tree",
}

MARKER = ":: LEGACY LAUNCHER"

changed = 0
for rel, why in DEAD.items():
    full = os.path.join(SCRIPTS, rel)
    if not os.path.exists(full):
        print(f"skip (missing): {rel}")
        continue

    text = open(full, encoding="utf-8", errors="ignore").read()
    if MARKER in text:
        print(f"already marked: {rel}")
        continue

    lines = text.splitlines(keepends=True)
    header = (
        f"{MARKER} - BROKEN, DO NOT RUN\r\n"
        f":: Reason: {why}\r\n"
        f":: Measured by SCRIPTS/automation/audit_launchers.py on "
        f"{time.strftime('%Y-%m-%d')}.\r\n"
        f":: This file is kept for reference only. The live tree is C:\\ABRASAX.\r\n"
    )

    # keep an @echo off line first if present
    if lines and lines[0].strip().lower().startswith("@echo"):
        new = lines[0] + header + "".join(lines[1:])
    else:
        new = header + "".join(lines)

    print(f"{'marking' if APPLY else 'would mark'}: {rel}")
    print(f"    reason: {why}")

    if APPLY:
        backup = full + ".bak-" + time.strftime("%Y%m%d-%H%M")
        import shutil
        shutil.copy2(full, backup)
        open(full, "w", encoding="utf-8", newline="").write(new)
        changed += 1

print(f"\n{len(DEAD)} dead launcher(s), {changed} marked")
if not APPLY:
    print("dry run -- re-run with --apply")
