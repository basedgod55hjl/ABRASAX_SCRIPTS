"""fix_singleton_path_scope.py -- keep SCRIPTS\\automation on sys.path at import.

Follow-up to fix_import_side_effect_singletons.py. That patch moved BOTH the
sys.path insert and the claim into _claim_singleton(), so `import orchestrator`
no longer added C:\\abrasax\\SCRIPTS\\automation to sys.path. tests/test_jev_gate.py
relied on it:

    from abrasax_singleton import read_lock, release  # (path added by orchestrator)

    ModuleNotFoundError: No module named 'abrasax_singleton'

The path insert is harmless at import (it mutates sys.path, not a lock), so it
belongs at module scope; only the CLAIM belongs in main(). This restores the
path without restoring the import-time singleton behaviour.

Idempotent. Backs up to <file>.bak-pathscope-YYYYMMDD.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(r"C:\abrasax")
PATH_BLOCK = ('import sys as _sys\n'
              '_sys.path.insert(0, r"C:\\abrasax\\SCRIPTS\\automation")\n')

TARGETS = ("orchestrator.py", "host.py")


def patch(name: str) -> bool:
    path = ROOT / name
    src = path.read_text(encoding="utf-8")
    if "import sys as _sys\n_sys.path.insert(0, r\"C:\\abrasax\\SCRIPTS\\automation\")" in src:
        print(f"{name}: already patched")
        return True
    anchor = "def _claim_singleton(role: str) -> bool:"
    if anchor not in src:
        print(f"{name}: ANCHOR NOT FOUND -- refusing to guess")
        return False
    bak = path.with_suffix(".py.bak-pathscope-" + dt.date.today().strftime("%Y%m%d"))
    bak.write_text(src, encoding="utf-8")
    src = src.replace(anchor, PATH_BLOCK + "\n\n" + anchor, 1)
    path.write_text(src, encoding="utf-8")
    print(f"{name}: patched (backup {bak.name})")
    return True


def main() -> int:
    ok = all([patch(name) for name in TARGETS])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
