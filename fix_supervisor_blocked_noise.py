"""fix_supervisor_blocked_noise.py - a blocked service must not write the ledger every tick.

MEASURED 2026-11-01, one absent ComfyUI tree, six identical ledger lines in 3.5 min:

    17:04:25 blocked imagegen  missing working directory: C:\\abrasax\\TOOLS\\AI-ImageGen
    17:05:07 blocked imagegen  (same)
    17:05:49 blocked imagegen  (same)
    17:06:31 blocked imagegen  (same)
    17:07:13 blocked imagegen  (same)
    17:07:55 blocked imagegen  (same)

Cause: the blocked branch popped ``_last_start[sid]``, so the 180 s cooldown
never applied. A missing install cannot appear within one tick, so the ledger
filled with samples of a fact that had not changed - and ``_preflight`` ran a
filesystem probe every tick for nothing.

Fix: keep the cooldown stamp on a blocked start (retry every COOLDOWN_S), and
write the ``blocked`` event only when the *reason* changes. State changes go in
the ledger; samples do not.

Idempotent: re-running changes nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\SCRIPTS\automation\supervisor.py")

OLD_TRACK = '''COOLDOWN_S = 180
'''
NEW_TRACK = '''COOLDOWN_S = 180
# Last block reason per service: the ledger records state CHANGES. Measured
# 2026-11-01, one absent install wrote six identical `blocked` lines in 3.5 min
# because the blocked branch reset the cooldown on every tick.
_last_block: dict[str, str] = {}


def _record_block(sid: str, result: dict) -> bool:
    """Log `blocked` only when the reason changes. True if this call logged it."""
    reason = str(result.get("error") or result.get("kind") or "blocked")
    if _last_block.get(sid) == reason:
        return False
    _last_block[sid] = reason
    _ledger({"event": "blocked", "svc": sid, **result})
    return True
'''

OLD_BLOCKED = '''        if result.get("blocked"):
            # Do not record cooldown or "started" for a service we never launched.
            _last_start.pop(sid, None)
            _ledger({"event": "blocked", "svc": sid, **result})
            events.append({"svc": sid, "state": "blocked", **result})
            continue'''
NEW_BLOCKED = '''        if result.get("blocked"):
            # Keep the cooldown stamp: nothing was launched, but a service blocked
            # by a missing install cannot become startable within one tick either.
            # Popping it here re-ran the preflight and re-wrote the ledger on every
            # tick (six identical lines in 3.5 min, measured 17:04:25-17:07:55).
            _record_block(sid, result)
            events.append({"svc": sid, "state": "blocked", **result})
            continue'''

OLD_BIND = '''        gate = bind_never_opened(spec)
        if gate is not None:
            _last_start.pop(sid, None)
            _ledger({"event": "blocked", "svc": sid, **gate})
            events.append({"svc": sid, "state": "blocked", **gate})
            continue'''
NEW_BIND = '''        gate = bind_never_opened(spec)
        if gate is not None:
            # Same rule: a process that exits before binding is retried on the
            # cooldown, and reported when the reason changes.
            _record_block(sid, gate)
            events.append({"svc": sid, "state": "blocked", **gate})
            continue'''

OLD_STARTED = '''        started.append(sid)
        _ledger({"event": "start", "svc": sid, **result})'''
NEW_STARTED = '''        _last_block.pop(sid, None)  # a real start clears the blocked memory
        started.append(sid)
        _ledger({"event": "start", "svc": sid, **result})'''

PATCHES = [(OLD_TRACK, NEW_TRACK), (OLD_BLOCKED, NEW_BLOCKED),
           (OLD_BIND, NEW_BIND), (OLD_STARTED, NEW_STARTED)]


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "_record_block" in src:
        print("already applied")
        return 0
    for old, new in PATCHES:
        if src.count(old) != 1:
            raise SystemExit(f"anchor not unique ({src.count(old)}x): {old[:70]!r}")
        src = src.replace(old, new, 1)
    TARGET.write_text(src, encoding="utf-8", newline="")
    print("patched", TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
