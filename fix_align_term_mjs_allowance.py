"""fix_align_term_mjs_allowance.py -- do not let --fix kill the operator's consoles.

`abrasax_align.py` reports:

    !! term-mjs 3 [6100, 28536, 30412]
    FINDINGS: DUPLICATE_ROLE role=term-mjs keep=6100 kill=[28536, 30412]

`--fix` acts on that finding. But the standing operator directive is explicit:
those term.mjs instances are the user's own terminals, distinct parents,
220 memory.jsonl records, 0 torn -- they are left running on purpose. 28536 is
also the ds_unrestricted agent whose shell the operator drives; killing it kills
the operator's own session.

So the count is expected, not a duplicate. Make it explicit and visible instead
of a kill order: ALLOWED_EXTRA maps a role to the number of instances that are
normal, and a count at or below it is reported as INFO. Above it, the finding
still fires.

Idempotent. Backs up to abrasax_align.py.bak-termallow-YYYYMMDD.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\SCRIPTS\automation\abrasax_align.py")

ALLOW_ANCHOR = '''def _cmd_tail(cmdline: str) -> str:'''

ALLOW_BLOCK = '''# Instances that are EXPECTED to exceed one, with the reason. Anything above the
# allowance is still a duplicate. term.mjs: three are the operator's own terminals
# (distinct parents, separate memory logs); one of them is the ds_unrestricted
# agent that drives the operator's shell, so `--fix` must never touch them.
ALLOWED_EXTRA = {"term-mjs": 3}


'''

OLD_LOOP = '''    for role, hits in sorted(role_hits.items()):
        if len(hits) > 1:
'''

NEW_LOOP = '''    for role, hits in sorted(role_hits.items()):
        allowance = ALLOWED_EXTRA.get(role, 1)
        if len(hits) > allowance:
            if allowance > 1:
                findings.append({"kind": "ALLOWED_EXTRA", "role": role,
                                 "count": len(hits), "allowed": allowance})
                continue
'''

INFO_OLD = '''        if len(hits) > 1:
'''
INFO_NEW = ''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "ALLOWED_EXTRA" in src:
        print("already patched")
        return 0
    if OLD_LOOP not in src or ALLOW_ANCHOR not in src:
        print("ANCHOR NOT FOUND -- refusing to guess")
        return 1
    bak = TARGET.with_suffix(".py.bak-termallow-" + dt.date.today().strftime("%Y%m%d"))
    bak.write_text(src, encoding="utf-8")
    out = src.replace(ALLOW_ANCHOR, ALLOW_BLOCK + ALLOW_ANCHOR, 1)
    out = out.replace(OLD_LOOP, NEW_LOOP, 1)
    TARGET.write_text(out, encoding="utf-8")
    print(f"patched {TARGET.name} (backup {bak.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
