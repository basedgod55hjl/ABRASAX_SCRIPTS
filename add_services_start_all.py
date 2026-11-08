"""add_services_start_all.py - make "start all" a CLI verb that cannot fork the launch spec.

Before this, bringing the stack up existed only as
``SCRIPTS/launchers/start_abrasax_stack.ps1``. An operator typing
``python -m abrasax services`` saw 19 rows and no way to act on them, and any
attempt to add a starter inside ``services.py`` would have created a second
copy of every launch command - the exact drift the catalog already suffered
(``llama-server.exe`` described as a working server for weeks).

So the verb delegates: it runs the one launcher, streams its output, then prints
the health table. One place knows how to start; one place knows what should be
up.

Idempotent: re-running changes nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\abrasax")
TARGET = ROOT / "abrasax" / "services.py"

OLD_ROWS = '''def main(argv: list[str] | None = None) -> int:
    """``python -m abrasax.services [--dupes|--health] [--json]``."""
    import argparse

    ap = argparse.ArgumentParser(
        prog="python -m abrasax.services",
        description="ABRASAX service catalog probes (health + single-instance).",
    )'''

NEW_ROWS = '''LAUNCHER = ROOT / "SCRIPTS" / "launchers" / "start_abrasax_stack.ps1"


def start_stack(extra_argv: tuple[str, ...] = ()) -> int:
    """Bring every catalogued service up through the ONE launcher.

    Deliberately not a second implementation: the launcher already owns the
    pidfile guards (never a second supervisor / build loop / ops monitor / HUD),
    the env hand-off, and the per-service preflight. A copy here would be a
    second launch spec to keep in sync, and this catalog has already paid for
    that twice (a phantom ``gateway`` on :9000; a ``llama-server.exe`` that
    could not load its own DLL).
    """
    if not LAUNCHER.exists():
        raise SystemExit(f"stack launcher missing: {LAUNCHER}")
    exe = shutil.which("powershell") or "powershell"
    cmd = [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(LAUNCHER)]
    cmd.extend(extra_argv)
    cp = subprocess.run(cmd, cwd=str(ROOT))
    return int(cp.returncode or 0)


def main(argv: list[str] | None = None) -> int:
    """``python -m abrasax.services [--dupes|--health|--start] [--json]``."""
    import argparse

    ap = argparse.ArgumentParser(
        prog="python -m abrasax.services",
        description="ABRASAX service catalog probes (health, single-instance, start).",
    )
    ap.add_argument("--start", action="store_true",
                    help="bring the stack up via SCRIPTS/launchers/start_abrasax_stack.ps1, "
                         "then print the health table")
    ap.add_argument("--no-models", action="store_true",
                    help="with --start: skip the LM Studio model check (passed to the launcher)")'''

OLD_TAIL = '''    args = ap.parse_args(argv)

    if args.health:'''

NEW_TAIL = '''    args = ap.parse_args(argv)

    if args.start:
        rc = start_stack(("-NoModels",) if args.no_models else ())
        if rc != 0:
            print(f"launcher exited {rc}; services below are what is actually up")
        args.health = True

    if args.health:'''

PATCHES = [(OLD_ROWS, NEW_ROWS), (OLD_TAIL, NEW_TAIL)]


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "def start_stack(" in src:
        print("already applied")
        return 0
    for old, new in PATCHES:
        if src.count(old) != 1:
            raise SystemExit(f"anchor not unique ({src.count(old)}x): {old[:80]!r}")
        src = src.replace(old, new, 1)
    TARGET.write_text(src, encoding="utf-8", newline="")
    print("patched", TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
