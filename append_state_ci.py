"""append_state_ci.py — append the CI-gate section to the session state doc.

The PowerShell one-liner kept dying in the shell quoting layer (backticks inside
double quotes), so the text is appended from Python, verbatim, and idempotently.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "DOC" / "SESSION-STATE-20261101.md"
MARK = "## 6. CI gate (added 11:00Z)"

BLOCK = f"""
{MARK}

The rebuilt repos' workflows could not fail: `ruff check . || true` is advisory,
and the compile loop ended each iteration with `echo FAIL` instead of a non-zero
exit -- and it only looked at `./*.py`. Three unimportable files in
`ABRASAX-UI/src` sat behind that green tick: a generator emitted docstring ->
shebang -> a SECOND string literal -> `from __future__`, which pushes the future
import out of the only position Python accepts.

Repaired: `DOC/templates/ci.yml` (a real gate over every `.py`, exiting
non-zero), applied to all 8 source trees and republished:

| repo | SHA |
|---|---|
| ABRASAX-UI | `9ca41b25` |
| ABRASAX-7D-Crystal | `66c63002` |
| ABRASAX-Agents | `f13ba8c9` |
| ABRASAX-DevOps | `dd158cd5` |
| ABRASAX-System32-AI | `3ed82eb1` |

Remote workflow verified byte-equal to the template (`sha256 9cdc2faee76f`).
`ABRASAX-SWARM-AI` keeps the old file: it is a mirror-restored row with no local
source, so changing it would break the restores-tree-equals-mirror guarantee.

The gate was proven able to fail **before** being trusted: `SCRIPTS/gate.sh`
exits 1 with the exact SyntaxError on a broken file in a subdirectory, and 0 on
the repaired 22-file tree (`gate_test.sh`). A gate nobody has seen fail is not
evidence.

Also fixed a false negative in the push proof itself: `repo.sync` read the remote
SHA once and reported `matches=false` for `ABRASAX-System32-AI` on a push that had
succeeded -- GitHub's commits API is eventually consistent for a few seconds.
It now re-reads up to 6 times at 2 s intervals and records `readback_attempts`.
"""


def main() -> int:
    text = DOC.read_text(encoding="utf-8")
    if MARK in text:
        print("already appended")
        return 0
    DOC.write_text(text.rstrip() + "\n" + BLOCK, encoding="utf-8")
    print(f"appended {len(BLOCK)} chars; doc now {len(DOC.read_text(encoding='utf-8'))} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
