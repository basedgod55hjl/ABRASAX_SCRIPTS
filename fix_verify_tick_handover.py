"""fix_verify_tick_handover.py - stop the run verifier from calling a clean restart "two tickers".

MEASURED 2026-11-01T17:17Z, live stack, one supervisor alive (pid 12632):

    FAIL  one ticker in the ledger  [last tick pids=[12632, 38232] heartbeat_pid=12632]

38232 was the supervisor before the launcher replaced it at 17:13. The old
supervisor was dead; its last tick (17:07:45Z) simply sat in the last three tick
rows, because ``_last_tick_pids`` counted *rows* instead of *time*. A handover
is not a second ticker.

What a second ticker really produces is two different pids ticking inside the
same interval. The check now compares time, not file position: keep ticks whose
timestamp is within ``max(tick_interval_s) + grace`` of the newest tick. A dead
predecessor falls outside that window; a rival ticker cannot.

Idempotent: re-running changes nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\abrasax")
TARGET = ROOT / "SCRIPTS" / "verify_stack_run.py"

OLD = '''def _last_tick_pids(n: int = 3) -> list[int]:
    """Distinct pids among the last `n` tick events in LOGS/supervisor-ledger.jsonl.

    A second ticker would write its own pid there. Empty list = the ledger has
    no pid field yet (older events) or no ticks.
    """
    try:
        lines = LEDGER.read_text(encoding="utf-8", errors="replace").splitlines()[-400:]
    except OSError:
        return []
    ticks: list[int] = []
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("event") != "tick":
            continue
        pid = row.get("pid")
        if isinstance(pid, int):
            ticks.append(pid)
        if len(ticks) >= n:
            break
    return sorted(set(ticks))
'''

NEW = '''# A tick that starts a hair after the previous one is still the same window;
# clocks and file writes are not exact. Anything larger is a restart, not a
# rival: a rival ticks inside the interval by definition.
_TICK_GRACE_S = 10.0


def _ts_epoch(ts: object) -> float | None:
    """Parse the ledger's UTC stamps ("2026-11-01T17:13:28Z") to epoch seconds."""
    if not isinstance(ts, str):
        return None
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None


def _last_tick_pids(n: int = 3, *, grace_s: float = _TICK_GRACE_S) -> list[int]:
    """Distinct pids among the ticks inside ONE tick window of the newest tick.

    Counting the last `n` tick rows cannot tell a second ticker from a normal
    restart: a predecessor's final tick sits next to the successor's first, and
    on 2026-11-01 17:13 that handover (38232 -> 12632) read as "two tickers"
    while only one was alive. A second ticker produces two pids ticking inside
    the same interval, so the window is what matters, not the row count.

    Empty list = the ledger has no pid field yet (older events), no ticks, or
    no parsable timestamps (the fallback keeps the old row-based behaviour).
    """
    try:
        lines = LEDGER.read_text(encoding="utf-8", errors="replace").splitlines()[-400:]
    except OSError:
        return []
    ticks: list[tuple[float, int]] = []
    intervals: list[float] = []
    unparsable: list[int] = []
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("event") != "tick":
            continue
        pid = row.get("pid")
        if not isinstance(pid, int):
            continue
        try:
            intervals.append(float(row.get("tick_interval_s") or 0.0))
        except (TypeError, ValueError):
            pass
        epoch = _ts_epoch(row.get("ts"))
        if epoch is None:
            unparsable.append(pid)
            continue
        ticks.append((epoch, pid))
        # keep a bounded amount of work: 10 windows is already generous
        if len(ticks) > 40:
            break
    if not ticks:
        return sorted(set(unparsable[:n]))
    interval = max([i for i in intervals if i > 0] or [30.0])
    newest = max(e for e, _ in ticks)
    cutoff = newest - interval - grace_s
    return sorted({pid for epoch, pid in ticks if epoch >= cutoff})
'''

HEADER_OLD = '''from __future__ import annotations
'''
HEADER_NEW = '''from __future__ import annotations

from datetime import datetime, timezone
'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if NEW in src:
        print("already applied")
        return 0
    if src.count(OLD) != 1:
        raise SystemExit(f"anchor not unique: {src.count(OLD)}")
    if "from datetime import datetime, timezone" not in src:
        if src.count(HEADER_OLD) != 1:
            raise SystemExit("header anchor not unique")
        src = src.replace(HEADER_OLD, HEADER_NEW, 1)
    src = src.replace(OLD, NEW, 1)
    TARGET.write_text(src, encoding="utf-8", newline="")
    print("patched", TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
