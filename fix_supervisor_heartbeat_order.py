"""fix_supervisor_heartbeat_order.py -- make the heartbeat write fail loud, and first.

Defect (measured 2026-11-01 16:19Z): tick() wrote LOGS/supervisor-state.json and
then LOGS/supervisor-heartbeat.txt inside one `try: ... except OSError: pass`.
Two consequences:

  1. If the heartbeat write is the one that fails, the state file is already
     fresh while the heartbeat is stale. The heartbeat is the ONLY signal the
     external watchdogs read ("heartbeat frozen" == dead supervisor), so they
     spawn a second supervisor -- which is how two tickers ended up racing and
     emitting duplicate start events for floating-brain / floating-brain-overlay.
  2. `except OSError: pass` destroys the evidence, so the ledger never records
     that a write failed at all.

This patch writes the heartbeat first, writes each file in its own guarded
block, and records a `write_error` ledger event instead of swallowing it.

Idempotent: exits 0 with "already patched" if the new form is present.
Writes supervisor.py.bak-heartbeatorder-YYYYMMDD before editing.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\SCRIPTS\automation\supervisor.py")

OLD = '''    try:
        LOGS.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        HEARTBEAT.write_text(f"{ts} pid={os.getpid()} up={len(summary['up'])} "
                             f"down={len(summary['down'])} "
                             f"started={len(started)} integrity_ok={chk['ok']}\\n",
                             encoding="utf-8")
    except OSError:
        pass
'''

NEW = '''    # Heartbeat FIRST. It is the only signal the external watchdogs read, so a
    # stale heartbeat with a fresh state file reads as "supervisor is dead" and
    # makes a second ticker start (measured 2026-11-01: two supervisors racing,
    # duplicate start events for floating-brain and its overlay). Each write is
    # guarded on its own and a failure is recorded, never swallowed.
    hb = (f"{ts} pid={os.getpid()} up={len(summary['up'])} "
          f"down={len(summary['down'])} "
          f"started={len(started)} integrity_ok={chk['ok']}\\n")
    LOGS.mkdir(parents=True, exist_ok=True)
    for _path, _body in ((HEARTBEAT, hb),
                         (STATE, json.dumps(summary, indent=2))):
        try:
            _path.write_text(_body, encoding="utf-8")
        except OSError as _exc:
            _ledger({"event": "write_error", "path": str(_path),
                     "error": repr(_exc)})
'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if NEW.splitlines()[0].strip() in src:
        print("already patched")
        return 0
    if OLD not in src:
        print("ANCHOR NOT FOUND -- refusing to guess")
        return 1
    bak = TARGET.with_suffix(".py.bak-heartbeatorder-" + dt.date.today().strftime("%Y%m%d"))
    bak.write_text(src, encoding="utf-8")
    TARGET.write_text(src.replace(OLD, NEW, 1), encoding="utf-8")
    print(f"patched {TARGET} (backup {bak.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
