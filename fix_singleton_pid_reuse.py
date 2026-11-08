"""fix_singleton_pid_reuse.py -- a lock must prove identity, not just liveness.

Measured 2026-11-01 16:32Z. C:\\abrasax\\LOGS\\locks\\host.lock recorded
pid 6988, started 2026-11-01T02:58:01Z. The real host.py was gone hours ago, but
pid 6988 had been recycled by a **chrome.exe renderer**, so `_pid_alive(6988)`
returned True and `holder("host")` reported a live host forever:

  * a real host.py could never start (claim -> holder -> False -> exit 0), with
    only a printed line to show for it;
  * `align`/`reconcile` would have "kept" a Chrome renderer as the role owner.

Windows recycles pids aggressively, so pid liveness is not identity. The lock
already stores `started`; a process that began AFTER the lock was written
cannot be the process that wrote it. Compare creation time to `started` and
treat "created later than the lock" as a reused pid -> stale -> claimable.

Idempotent. Backs up to abrasax_singleton.py.bak-pidreuse-YYYYMMDD.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\SCRIPTS\automation\abrasax_singleton.py")

OLD = '''def holder(role: str):
    """Return the live holder dict for `role`, or None if free/stale."""
    info = read_lock(role)
    if not info:
        return None
    if _pid_alive(int(info.get("pid", 0))):
        return info
    return None
'''

NEW = '''_k32.GetProcessTimes.argtypes = [_wt.HANDLE, ctypes.POINTER(_wt.FILETIME),
                             ctypes.POINTER(_wt.FILETIME),
                             ctypes.POINTER(_wt.FILETIME),
                             ctypes.POINTER(_wt.FILETIME)]
_k32.GetProcessTimes.restype = _wt.BOOL


def _proc_created_epoch(pid: int):
    """UTC epoch seconds when `pid` started, or None if it cannot be read."""
    try:
        pid = int(pid)
    except Exception:
        return None
    if pid == os.getpid():
        return None  # our own creation time is not needed for the check
    h = _k32.OpenProcess(_QUERY_LIMITED, False, pid)
    if not h:
        return None
    try:
        created = _wt.FILETIME()
        zero = _wt.FILETIME()
        if not _k32.GetProcessTimes(h, ctypes.byref(created), ctypes.byref(zero),
                                    ctypes.byref(zero), ctypes.byref(zero)):
            return None
        ticks = (created.dwHighDateTime << 32) | created.dwLowDateTime
        return ticks / 10_000_000.0 - 11644473600.0   # 1601-01-01 -> 1970-01-01
    finally:
        _k32.CloseHandle(h)


def _lock_started_epoch(info) -> float | None:
    raw = str((info or {}).get("started") or "")
    try:
        return dt.datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.timezone.utc).timestamp()
    except ValueError:
        return None


def holder(role: str):
    """Return the live holder dict for `role`, or None if free/stale.

    Liveness alone is not enough: Windows recycles pids, so a stale lock can
    name a *different* live process (measured 2026-11-01: host.lock pid 6988
    became a chrome.exe renderer). A process created after the lock was
    written cannot be the owner, so that is treated as stale.
    """
    info = read_lock(role)
    if not info:
        return None
    pid = int(info.get("pid", 0))
    if not _pid_alive(pid):
        return None
    started = _lock_started_epoch(info)
    created = _proc_created_epoch(pid)
    if started is not None and created is not None and created > started + 2.0:
        return None      # pid was reused by an unrelated process
    return info
'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "_proc_created_epoch" in src:
        print("already patched")
        return 0
    if OLD not in src:
        print("ANCHOR NOT FOUND -- refusing to guess")
        return 1
    bak = TARGET.with_suffix(".py.bak-pidreuse-" + dt.date.today().strftime("%Y%m%d"))
    bak.write_text(src, encoding="utf-8")
    out = src.replace(OLD, NEW, 1)
    if "import datetime as dt" not in out:
        out = out.replace("import ctypes\n", "import ctypes\nimport datetime as dt\n", 1)
    TARGET.write_text(out, encoding="utf-8")
    print(f"patched {TARGET} (backup {bak.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
