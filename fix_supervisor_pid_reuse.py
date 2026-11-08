"""fix_supervisor_pid_reuse.py -- the pidfile owner must be the owner, not a recycled pid.

Measured 2026-11-01 16:36Z, twice in one session. LOGS/supervisor.pid held a pid
whose process had been killed; Windows recycled that pid, so:

   31148 -> supervisor (killed)   then   31148 -> chrome.exe

`_claim_pidfile()` only asked `_pid_alive(31148)` -> True -> "supervisor already
running" -> the new supervisor exited 0 and NOTHING ran. The same trap held
LOGS/locks/host.lock earlier today (a chrome renderer "owned" the host role).

The pidfile stores only a pid, and other tools read it as int(), so the format
cannot change. Identity is recovered from the file's own mtime: the owner wrote
that file, so a process CREATED AFTER the file was written cannot be its author.
A reused pid is therefore stale and claimable.

Residual (documented): a pid recycled by another process that started BEFORE the
pidfile was written is indistinguishable without a cmdline probe; that window is
seconds wide and the next tick repairs it.

Idempotent. Backs up to supervisor.py.bak-pidreuse-YYYYMMDD.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\SCRIPTS\automation\supervisor.py")

HELPER_ANCHOR = "def _claim_pidfile() -> bool:"

HELPER = '''def _proc_created_epoch(pid: int):
    """UTC epoch seconds when `pid` started, or None if unreadable."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    try:
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = ctypes.c_void_p
        k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        k32.GetProcessTimes.argtypes = [ctypes.c_void_p,
                                        ctypes.POINTER(ctypes.c_uint32 * 2),
                                        ctypes.POINTER(ctypes.c_uint32 * 2),
                                        ctypes.POINTER(ctypes.c_uint32 * 2),
                                        ctypes.POINTER(ctypes.c_uint32 * 2)]
        handle = k32.OpenProcess(0x1000, 0, pid)      # QUERY_LIMITED_INFORMATION
        if not handle:
            return None
        try:
            created = (ctypes.c_uint32 * 2)()
            zero = (ctypes.c_uint32 * 2)()
            if not k32.GetProcessTimes(ctypes.c_void_p(handle), created, zero,
                                       zero, zero):
                return None
            ticks = (created[1] << 32) | created[0]
            return ticks / 10_000_000.0 - 11644473600.0
        finally:
            k32.CloseHandle(ctypes.c_void_p(handle))
    except Exception:  # noqa: BLE001
        return None


def _pidfile_owner() -> int:
    """The pid in LOGS/supervisor.pid IF that pid is really the process that
    wrote it. 0 means free / stale / recycled.

    Windows recycles pids: measured 2026-11-01, a killed supervisor's pid came
    back as chrome.exe and blocked every new supervisor with "already running".
    A process created after the pidfile was written cannot have written it.
    """
    try:
        pid = int(PIDFILE.read_text().strip())
    except (OSError, ValueError):
        return 0
    if not pid or pid == os.getpid():
        return pid
    if not _pid_alive(pid):
        return 0
    try:
        wrote_at = PIDFILE.stat().st_mtime
    except OSError:
        return 0
    created = _proc_created_epoch(pid)
    if created is not None and created > wrote_at + 2.0:
        return 0          # pid was reused by a process younger than the file
    return pid


'''

OLD_CLAIM = '''        except FileExistsError:
            try:
                pid = int(PIDFILE.read_text().strip())
            except (OSError, ValueError):
                pid = 0
            if pid and pid != os.getpid() and _pid_alive(pid):
                return False              # a live supervisor owns it
'''
NEW_CLAIM = '''        except FileExistsError:
            pid = _pidfile_owner()
            if pid and pid != os.getpid():
                return False              # a real, live supervisor owns it
'''

OLD_ONCE = '''                try:
                    _owner = int(PIDFILE.read_text().strip())
                except (OSError, ValueError):
                    _owner = 0
                if _owner and _owner != os.getpid() and _pid_alive(_owner):
'''
NEW_ONCE = '''                _owner = _pidfile_owner()
                if _owner and _owner != os.getpid():
'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "_pidfile_owner" in src:
        print("already patched")
        return 0
    for anchor in (HELPER_ANCHOR, OLD_CLAIM, OLD_ONCE):
        if anchor not in src:
            print(f"ANCHOR NOT FOUND: {anchor.splitlines()[0]!r} -- refusing to guess")
            return 1
    bak = TARGET.with_suffix(".py.bak-pidreuse-" + dt.date.today().strftime("%Y%m%d"))
    bak.write_text(src, encoding="utf-8")
    out = src.replace(HELPER_ANCHOR, HELPER + HELPER_ANCHOR, 1)
    out = out.replace(OLD_CLAIM, NEW_CLAIM, 1).replace(OLD_ONCE, NEW_ONCE, 1)
    TARGET.write_text(out, encoding="utf-8")
    print(f"patched {TARGET} (backup {bak.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
