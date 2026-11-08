"""patch_verify_stack_run_settle.py -- count only STABLE supervisors.

Measured 2026-11-01 16:24Z: verify_stack_run.py reported two logical supervisors
because a user-side spawner launches supervisor.py periodically without the
shim; the copy dies on the pidfile claim within a second. Counting raw pids
called that a failure, which would train everyone to ignore the verifier.

Fix: sample the process table twice ~2.5 s apart and keep only pids present in
both samples. A loser that cannot claim the pidfile is gone by the second
sample, so the count describes the run, not a spawn attempt.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\SCRIPTS\verify_stack_run.py")

START = "def _supervisor_procs() -> list[tuple[int, int]]:"
END = "def verify() -> dict:"

NEW = '''def _sample_supervisor_procs() -> list[tuple[int, int]]:
    """(pid, parent_pid) for every process whose command line is supervisor.py."""
    try:
        ps = ("Get-CimInstance Win32_Process | Where-Object {$_.CommandLine -like "
              "'*supervisor.py*'} | ForEach-Object { \\"$($_.ProcessId) $($_.ParentProcessId)\\" }")
        txt = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, timeout=40).stdout
    except Exception:  # noqa: BLE001
        return []
    out: list[tuple[int, int]] = []
    for line in txt.splitlines():
        parts = line.split()
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            out.append((int(parts[0]), int(parts[1])))
    return out


def _collapse(first: list[tuple[int, int]],
              second: list[tuple[int, int]]) -> tuple[list[int], list[int], int]:
    """Pure: keep only pids seen in BOTH samples, then collapse shim->child pairs.

    Returns (logical_roots, stable_pids, transient_count). pythonw.exe in
    C:\\\\ABRASAX\\\\PYTHON\\\\.venv_gui re-execs itself, so ONE logical supervisor is a
    parent/child pid pair; a spawner that loses the pidfile claim disappears
    between samples, so it must not be counted as a second supervisor.
    """
    stable = {p for p, _ in first} & {p for p, _ in second}
    transient = len({p for p, _ in first} | {p for p, _ in second}) - len(stable)
    procs = [(p, parent) for p, parent in second if p in stable]
    roots = [p for p, parent in procs if parent not in stable]
    return sorted(roots), sorted(stable), transient


def _logical_supervisors(settle_s: float = 2.5) -> tuple[list[int], list[int], int]:
    first = _sample_supervisor_procs()
    time.sleep(settle_s)
    return _collapse(first, _sample_supervisor_procs())


'''

OLD_CHECK = '''    roots, all_sup_pids = _logical_supervisors()
    check("exactly one logical supervisor", len(roots) == 1,
          f"logical={roots} raw_pids={all_sup_pids}")'''

NEW_CHECK = '''    roots, all_sup_pids, transient = _logical_supervisors()
    check("exactly one logical supervisor", len(roots) == 1,
          f"logical={roots} stable_pids={all_sup_pids} transient_spawns={transient}")'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "_collapse(" in src:
        print("already patched")
        return 0
    i, j = src.index(START), src.index(END)
    src = src[:i] + NEW + src[j:]
    if OLD_CHECK not in src:
        print("CHECK ANCHOR NOT FOUND -- refusing to guess")
        return 1
    src = src.replace(OLD_CHECK, NEW_CHECK, 1)
    TARGET.write_text(src, encoding="utf-8")
    print("patched verify_stack_run.py with settle-and-intersect")
    return 0


if __name__ == "__main__":
    sys.exit(main())
