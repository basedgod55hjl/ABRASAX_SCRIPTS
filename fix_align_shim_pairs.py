"""fix_align_shim_pairs.py -- stop abrasax_align from calling a shim pair a duplicate.

Two defects measured on 2026-11-01 16:25Z:

1. Every pythonw.exe in C:\\ABRASAX\\PYTHON\\.venv_gui RE-EXECS itself, so one live
   role is two pids: shim (parent) + real worker (child), with identical argument
   tails. `abrasax_align.py` reported
       !! jev-fused 2 [27212, 34020]
   and --fix would Stop-Process the child, i.e. kill the actual server while
   keeping a shim that then exits. A false duplicate is worse than a miss: the
   reconciler is allowed to kill.

2. The "jev-server" needle was the absolute path r"abrasax\\tools\\jev_server.py",
   which cannot match the real launch line
       "...\\python.exe" tools\\jev_server.py
   (the interpreter path sits between "abrasax" and "tools"), so a running
   jev_server read as 0 instances.

Fix 1: collapse ancestor/descendant pairs whose command-line tail (everything
after the executable token) is identical -- keep the CHILD (the worker), drop
the shim from the duplicate count, and record what was collapsed.
Fix 2: match on r"tools\\jev_server.py", which is a substring of neither
tools\\jev_server_fused.py nor any other role.

Idempotent. Backs up to abrasax_align.py.bak-shimpair-YYYYMMDD.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\SCRIPTS\automation\abrasax_align.py")

OLD_NEEDLE = '    "jev-server": r"abrasax\\tools\\jev_server.py",'
NEW_NEEDLE = ('    # absolute "abrasax\\tools\\jev_server.py" could never match\n'
              '    #   "<venv>\\python.exe" tools\\jev_server.py\n'
              '    "jev-server": r"tools\\jev_server.py",')

HELPER_ANCHOR = "def main():\n"

HELPER = '''def _cmd_tail(cmdline: str) -> str:
    """Everything after the executable token, normalized for comparison."""
    parts = (cmdline or "").replace("/", "\\\\").split()
    return " ".join(parts[1:]).strip().lower()


def _collapse_shim_pairs(procs):
    """Drop re-exec shim parents; keep the real worker child.

    pythonw.exe in C:\\\\ABRASAX\\\\PYTHON\\\\.venv_gui re-execs itself with an identical
    argument tail, so ONE role = parent+child. Counting both made
    abrasax_align --fix kill the child: the role died and the "kept" pid was a
    shim. Returns (kept_procs, collapsed_parent_pids).
    """
    by_pid = {p.get("ProcessId"): p for p in procs}
    drop = set()
    for p in procs:
        tail = _cmd_tail(p.get("CommandLine"))
        if not tail:
            continue
        q = by_pid.get(p.get("ParentProcessId"))
        while q is not None:
            if _cmd_tail(q.get("CommandLine")) == tail:
                drop.add(q.get("ProcessId"))
                break
            q = by_pid.get(q.get("ParentProcessId"))
    return [p for p in procs if p.get("ProcessId") not in drop], sorted(drop)


'''

OLD_MAIN = """    procs = get_procs()
    listeners = get_listeners()

    findings = []
"""

NEW_MAIN = """    procs, shim_pids = _collapse_shim_pairs(get_procs())
    listeners = get_listeners()

    findings = []
    if shim_pids:
        # Not a duplicate: one role, two pids (shim parent + worker child).
        findings.append({"kind": "SHIM_PAIR_COLLAPSED", "pids": shim_pids})
"""


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "_collapse_shim_pairs" in src:
        print("already patched")
        return 0
    for anchor in (OLD_NEEDLE, OLD_MAIN, HELPER_ANCHOR):
        if anchor not in src:
            print(f"ANCHOR NOT FOUND: {anchor.splitlines()[0]!r} -- refusing to guess")
            return 1
    bak = TARGET.with_suffix(".py.bak-shimpair-" + dt.date.today().strftime("%Y%m%d"))
    bak.write_text(src, encoding="utf-8")
    out = src.replace(OLD_NEEDLE, NEW_NEEDLE, 1)
    out = out.replace(HELPER_ANCHOR, HELPER + HELPER_ANCHOR, 1)
    out = out.replace(OLD_MAIN, NEW_MAIN, 1)
    TARGET.write_text(out, encoding="utf-8")
    print(f"patched {TARGET} (backup {bak.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
