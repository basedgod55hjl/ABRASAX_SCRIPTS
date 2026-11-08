"""append_leak_status.py — append the verified status block to the security doc.

PowerShell here-strings kept mangling this through the shell layer, so the text
lives in a file and is appended verbatim. Idempotent: refuses to append twice.

    python SCRIPTS/append_leak_status.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "DOC" / "SECURITY-PAT-20261101.md"
MARK = "STATUS UPDATE 2026-11-01"

BLOCK = f"""
## {MARK} -- re-verified, STILL EXPOSED

An earlier pass in this session read the unauthenticated 404s below as "GitHub
has GC'd the commit". That was wrong: unauthenticated requests against this
PRIVATE repo return 404 for every path, so the probe measured privacy, not
deletion. Authenticated re-check (`SCRIPTS/check_leak_status.py`,
`SCRIPTS/verify_leak_content.py`):

- `GET /repos/basedgod55hjl/ABRASAX-REBUILD/commits/47bdb9f` -> **200**
- `GET .../contents/SCRIPTS/automation/run_mesh.ps1?ref=47bdb9f` -> **200**
- the file at that SHA holds a 93-char token that is **byte-identical to the live
  token this host authenticates with** (compared in-process; only booleans and
  lengths were printed, never the value)
- the same file at `HEAD` (main, `18e66cf`) is clean: 0 token-shaped strings

So the action list above is still the action list: revoke the PAT at
https://github.com/settings/tokens, issue a replacement into `C:\\vlc-build\\.env`,
and ask Support to GC `ABRASAX-REBUILD`. Rewriting history does not revoke an
object that still answers 200 to anyone with read access.

**Rebuild note.** The 20 repos rebuilt on 2026-11-01 are fresh roots and carry no
leaked history. `ABRASAX-REBUILD` is the only repo still carrying it -- rebuilding
it is the cheapest permanent fix, provided the PAT is rotated **first**.

_Appended {time.strftime('%Y-%m-%d %H:%M %Z', time.localtime())}._
"""


def main() -> int:
    text = DOC.read_text(encoding="utf-8")
    if MARK in text:
        print("already appended")
        return 0
    DOC.write_text(text.rstrip() + "\n" + BLOCK, encoding="utf-8")
    print(f"appended {len(BLOCK)} chars to {DOC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
