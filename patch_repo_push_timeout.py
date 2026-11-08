"""patch_repo_push_timeout.py — give pushes a real timeout.

`repo.sync` pushed with a 300 s ceiling. ABRASAX_SCRIPTS stages ~75 MB and
ABRASAX-7D-Crystal carries checkpoints, so a slow uplink would abort mid-push
and leave a half-created repo. 30 minutes, and the mirror restore path already
allowed that.

Idempotent; leaves a .bak the first time.
"""
from __future__ import annotations

import sys
from pathlib import Path

P = Path(r"C:\ABRASAX\tools\abx\repo.py")
OLD_DEF = 'def _push(tree: Path, remote: str, refspec: str, timeout: float = 300.0) -> dict[str, Any]:'
NEW_DEF = 'def _push(tree: Path, remote: str, refspec: str, timeout: float = 1800.0) -> dict[str, Any]:'
OLD_CALL = '    push = _push(tree, remote, f"HEAD:{branch}")'
NEW_CALL = '    push = _push(tree, remote, f"HEAD:{branch}", timeout=1800.0)'


def main() -> int:
    src = P.read_text(encoding="utf-8")
    if NEW_DEF in src and NEW_CALL in src:
        print("already patched")
        return 0
    if src.count(OLD_DEF) != 1:
        print(f"FAIL anchor _push def matched {src.count(OLD_DEF)}x")
        return 1
    if src.count(OLD_CALL) != 1:
        print(f"FAIL anchor sync call matched {src.count(OLD_CALL)}x")
        return 1
    (P.with_suffix(".py.bak-pushtimeout")).write_text(src, encoding="utf-8")
    out = src.replace(OLD_DEF, NEW_DEF).replace(OLD_CALL, NEW_CALL)
    P.write_text(out, encoding="utf-8")
    print("patched", P)
    return 0


if __name__ == "__main__":
    sys.exit(main())
