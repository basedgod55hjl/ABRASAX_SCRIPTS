"""fix_verifier_started_after_snapshot.py -- a just-started service is not a mystery.

Measured 2026-11-01 16:38Z: STACK RUN went red with

    FAIL  down jev-fused is explained  [down with no proven external cause]

because the state snapshot was written at 16:38:24 (jev-fused down) and the
supervisor started jev-fused at 16:38:37 -- twelve seconds later, in the same
tick cycle. The next tick showed it up and the check passed with no change.

A verifier that goes red for one tick after a legitimate start trains people to
ignore it. Read the ledger: a service with a `start` event at or after the
state's own timestamp is *recovering*, not unexplained. It is still reported,
as INFO, so the fact is visible without being an incident.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\SCRIPTS\verify_stack_run.py")

HELPER_ANCHOR = "def verify() -> dict:"

HELPER = '''def _started_since(ts: str) -> list[str]:
    """Services with a ledger `start` event at/after the state snapshot `ts`."""
    try:
        lines = LEDGER.read_text(encoding="utf-8", errors="replace").splitlines()[-400:]
    except OSError:
        return []
    out: set[str] = set()
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("event") != "start":
            continue
        if str(row.get("ts") or "") >= ts:
            svc = row.get("svc")
            if isinstance(svc, str):
                out.add(svc)
    return sorted(out)


'''

OLD = '''    for svc in state.get("down", []):
        if svc not in KNOWN_ABSENT:
            check(f"down {svc} is explained", False, "down with no proven external cause")
'''

NEW = '''    recovering = _started_since(str(state.get("ts") or "")) if state else []
    for svc in state.get("down", []):
        if svc in KNOWN_ABSENT:
            continue
        if svc in recovering:
            checks.append({"check": f"down {svc} is explained", "ok": True,
                           "detail": "started by the supervisor after this snapshot "
                                     "(recovering)"})
            continue
        check(f"down {svc} is explained", False, "down with no proven external cause")
'''

NEW_RETURN = '''        "recovering": recovering,
'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "_started_since" in src:
        print("already patched")
        return 0
    if OLD not in src or HELPER_ANCHOR not in src:
        print("ANCHOR NOT FOUND -- refusing to guess")
        return 1
    bak = TARGET.with_suffix(".py.bak-recovering-" + dt.date.today().strftime("%Y%m%d"))
    bak.write_text(src, encoding="utf-8")
    src = src.replace(HELPER_ANCHOR, HELPER + HELPER_ANCHOR, 1)
    src = src.replace(OLD, NEW, 1)
    src = src.replace('        "parity": parity,\n', '        "parity": parity,\n' + NEW_RETURN, 1)
    TARGET.write_text(src, encoding="utf-8")
    print(f"patched {TARGET.name} (backup {bak.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
