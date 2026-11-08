"""fix_tick_identity.py -- prove there is ONE ticker from the ledger, not from ps.

Follow-up to fix_process_match_false_positive.py. Counting supervisor processes
cannot answer "is there one ticker":

  * venv_gui pythonw RE-EXECS, so one supervisor is a shim+child pair;
  * spawners launch supervisor.py pairs that take 3-5 s to lose the pidfile
    claim, which is longer than any settling window a verifier can afford
    (measured 2026-11-01 16:37Z: two such pairs were "stable" across a 2.5 s
    sample and made STACK RUN: FAIL while the run was healthy).

The ledger is the ground truth: every tick appends an event. Record the pid in
it, then "one ticker" becomes a fact about the last N ticks, not a guess about
the process table.

  * supervisor.py: tick ledger event carries "pid".
  * verify_stack_run.py: check the last 3 tick events share one pid, and report
    other supervisor-shaped processes as INFO instead of failing on them.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(r"C:\abrasax")
SUP = ROOT / "SCRIPTS" / "automation" / "supervisor.py"
VER = ROOT / "SCRIPTS" / "verify_stack_run.py"

SUP_OLD = '    _ledger({"event": "tick", **summary})\n'
SUP_NEW = '    _ledger({"event": "tick", "pid": os.getpid(), **summary})\n'

VER_CHECK_OLD = '''    roots, all_sup_pids, transient = _logical_supervisors()
    check("exactly one logical supervisor", len(roots) == 1,
          f"logical={roots} stable_pids={all_sup_pids} transient_spawns={transient}")
'''

VER_CHECK_NEW = '''    roots, all_sup_pids, transient = _logical_supervisors()
    # Process counting cannot prove "one ticker": a venv shim is two pids, and a
    # spawner's loser lives ~3-5 s before the pidfile claim rejects it. The
    # ledger can: every tick records its pid. Count that instead, and report the
    # process table as information.
    tick_pids = _last_tick_pids()
    check("one ticker in the ledger", len(tick_pids) == 1 and hb_pid in tick_pids,
          f"last tick pids={tick_pids} heartbeat_pid={hb_pid}")
    checks.append({"check": "supervisor processes (info)", "ok": True,
                   "detail": f"logical={roots} pids={all_sup_pids} "
                             f"transient_spawns={transient}"})
'''

HELPER_ANCHOR = "def verify() -> dict:"
HELPER = '''def _last_tick_pids(n: int = 3) -> list[int]:
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


def main() -> int:
    sup = SUP.read_text(encoding="utf-8")
    ver = VER.read_text(encoding="utf-8")
    if '"pid": os.getpid(), **summary' in sup and "_last_tick_pids" in ver:
        print("already patched")
        return 0
    if SUP_OLD not in sup:
        print("supervisor ANCHOR NOT FOUND -- refusing to guess")
        return 1
    if VER_CHECK_OLD not in ver or HELPER_ANCHOR not in ver:
        print("verifier ANCHOR NOT FOUND -- refusing to guess")
        return 1
    stamp = dt.date.today().strftime("%Y%m%d")
    SUP.with_suffix(f".py.bak-tickpid-{stamp}").write_text(sup, encoding="utf-8")
    VER.with_suffix(f".py.bak-tickpid-{stamp}").write_text(ver, encoding="utf-8")
    SUP.write_text(sup.replace(SUP_OLD, SUP_NEW, 1), encoding="utf-8")
    ver = ver.replace(HELPER_ANCHOR, HELPER + HELPER_ANCHOR, 1)
    ver = ver.replace(VER_CHECK_OLD, VER_CHECK_NEW, 1)
    if "LEDGER = " not in ver:
        ver = ver.replace('PIDFILE = LOGS / "supervisor.pid"',
                          'PIDFILE = LOGS / "supervisor.pid"\n'
                          'LEDGER = LOGS / "supervisor-ledger.jsonl"', 1)
    VER.write_text(ver, encoding="utf-8")
    print("patched supervisor.py (tick pid) + verify_stack_run.py (ledger ticker check)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
