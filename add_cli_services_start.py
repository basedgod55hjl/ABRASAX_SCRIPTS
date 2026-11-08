"""add_cli_services_start.py - expose `abrasax services --start` on the real CLI.

``abrasax/cli.py`` builds the ``services`` table itself instead of calling
``abrasax.services.main``, so the flags added there are invisible to
``python -m abrasax services`` unless they are declared here too. This patch
declares ``--start`` / ``--no-models`` and delegates to
``services.start_stack`` (the single launcher path).

Idempotent: re-running changes nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\abrasax")
TARGET = ROOT / "abrasax" / "cli.py"

OLD_ARGS = '''    p_svc.add_argument("--json", action="store_true")
'''
NEW_ARGS = '''    p_svc.add_argument("--json", action="store_true")
    # "start all" was a PowerShell path with no CLI verb: the operator could see
    # 19 rows and could not act on them. Delegates to the one launcher so the
    # catalog never grows a second copy of a launch command.
    p_svc.add_argument("--start", action="store_true",
                       help="bring the stack up first (SCRIPTS/launchers/"
                            "start_abrasax_stack.ps1), then print this table")
    p_svc.add_argument("--no-models", action="store_true",
                       help="with --start: skip the LM Studio model check")
'''

OLD_BODY = '''    elif args.command == "services":
        from . import services
        if args.timeout is not None and args.timeout <= 0:'''
NEW_BODY = '''    elif args.command == "services":
        from . import services
        if getattr(args, "start", False):
            _rc = services.start_stack(("-NoModels",) if args.no_models else ())
            if _rc:
                print(f"launcher exited {_rc}; this table is what is actually up",
                      file=sys.stderr)
        if args.timeout is not None and args.timeout <= 0:'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if 'p_svc.add_argument("--start"' in src:
        print("already applied")
        return 0
    for old, new in ((OLD_ARGS, NEW_ARGS), (OLD_BODY, NEW_BODY)):
        if src.count(old) != 1:
            raise SystemExit(f"anchor not unique ({src.count(old)}x): {old[:70]!r}")
        src = src.replace(old, new, 1)
    TARGET.write_text(src, encoding="utf-8", newline="")
    print("patched", TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
