"""fix_llamacpp_winproc_import.py - use os.path, not Path, in a file that never imported it.

fix_headless_spawns.py inserted a `Path(__file__)` anchor into
tools/llamacpp_serve.py, which imports `os` but not `pathlib`, so the tool
failed at import with NameError: name 'Path' is not defined. Caught by running
`--stop`, not by py_compile (py_compile cannot see a NameError).

Idempotent.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\tools\llamacpp_serve.py")

OLD = '''sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from abrasax import winproc  # noqa: E402
'''
NEW = '''sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from abrasax import winproc  # noqa: E402
'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if NEW in src:
        print("already applied")
        return 0
    if src.count(OLD) != 1:
        raise SystemExit(f"anchor {src.count(OLD)}x")
    TARGET.write_text(src.replace(OLD, NEW, 1), encoding="utf-8", newline="")
    print("patched", TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
