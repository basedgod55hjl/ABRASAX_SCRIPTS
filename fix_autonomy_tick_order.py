"""fix_autonomy_tick_order.py - the autonomy call ran before the liveness it needs.

Measured 2026-11-01T18:11:00Z, one tick after wiring:

    {"event": "autonomy_error",
     "error": "UnboundLocalError(\\"cannot access local variable 'up_ids' ...\\")"}

wire_autonomy.py anchored on `chk = integrity()`, which sits ABOVE the block that
computes `up_ids`. The call was skipped (the try/except kept the tick alive, as
designed), so nothing was written and the router kept using the config policy.

Moved to immediately after `down_ids`, so the mode is computed from the same
verdict the state file publishes, and before `summary` so `llm_mode` can be part
of it.

Idempotent.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\SCRIPTS\automation\supervisor.py")

BLOCK = '''    # Local-first routing: the router may only prefer local providers while it
    # knows they are up, and this tick is that knowledge. Written after the
    # summary so a crash cannot leave a half-formed decision behind.
    try:
        from abrasax import autonomy
        _llm_mode = autonomy.snapshot(up_ids=up_ids, write_state=True)
    except Exception as exc:  # noqa: BLE001 - routing policy must not kill a tick
        _llm_mode = {"error": repr(exc)}
        _ledger({"event": "autonomy_error", "error": repr(exc)})

'''

ANCHOR = '''    down_ids = {e["svc"] for e in events if e.get("state") == "down"} - up_ids
'''
NEW_BLOCK = ANCHOR + '''    # Local-first routing: the router may prefer local providers only while it
    # knows they are up, and this tick owns that knowledge (it is the same
    # verdict written to supervisor-state.json). Computed here, after up_ids and
    # before summary - the first version ran before up_ids existed and every tick
    # logged autonomy_error (measured 18:11:00Z).
    try:
        from abrasax import autonomy
        _llm_mode = autonomy.snapshot(up_ids=up_ids, write_state=True)
    except Exception as exc:  # noqa: BLE001 - routing policy must not kill a tick
        _llm_mode = {"error": repr(exc)}
        _ledger({"event": "autonomy_error", "error": repr(exc)})

'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if NEW_BLOCK in src:
        print("already applied")
        return 0
    if src.count(BLOCK) != 1:
        raise SystemExit(f"block anchor {src.count(BLOCK)}x")
    if src.count(ANCHOR) != 1:
        raise SystemExit(f"insert anchor {src.count(ANCHOR)}x")
    src = src.replace(BLOCK, "", 1)
    src = src.replace(ANCHOR, NEW_BLOCK, 1)
    TARGET.write_text(src, encoding="utf-8", newline="")
    print("patched", TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
