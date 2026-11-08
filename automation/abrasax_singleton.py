#!/usr/bin/env python3
"""ABRASAX singleton guard -- OSIRISBLXCK 2026-10-31.

Enforces ONE live instance per named role across the whole box. Prevents the
multi-terminal overwrite bug found on 2026-10-31 (3x orchestrator.py appending
to the same LOGS/orchestra.log, 2x host.py double-writing LOGS/host.log).

Usage:
    from abrasax_singleton import claim
    if not claim("orchestrator"):
        raise SystemExit("orchestrator already running")
    # ... run work; lock auto-releases on process exit

Lock file: C:\\abrasax\\LOGS\\locks\\<role>.lock   (JSON: pid, started, cmdline)
Staleness: a lock whose pid is dead is reclaimed automatically.
"""
import json
import os
import sys
import time

LOCK_DIR = os.path.join(os.environ.get("ABRASAX_ROOT", r"C:\abrasax"), "LOGS", "locks")


import ctypes
import datetime as dt
import ctypes.wintypes as _wt

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.OpenProcess.argtypes = [_wt.DWORD, _wt.BOOL, _wt.DWORD]
_k32.OpenProcess.restype = _wt.HANDLE
_k32.GetExitCodeProcess.argtypes = [_wt.HANDLE, ctypes.POINTER(_wt.DWORD)]
_k32.GetExitCodeProcess.restype = _wt.BOOL
_k32.CloseHandle.argtypes = [_wt.HANDLE]
_k32.CloseHandle.restype = _wt.BOOL

_QUERY_LIMITED = 0x1000
_STILL_ACTIVE = 259


def _pid_alive(pid: int) -> bool:
    """True if `pid` is a live, non-exited process. Verified 2026-10-31."""
    try:
        pid = int(pid)
    except Exception:
        return False
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    h = _k32.OpenProcess(_QUERY_LIMITED, False, pid)
    if not h:
        return False
    try:
        code = _wt.DWORD()
        if not _k32.GetExitCodeProcess(h, ctypes.byref(code)):
            return False
        return code.value == _STILL_ACTIVE
    finally:
        _k32.CloseHandle(h)


def read_lock(role: str):
    path = os.path.join(LOCK_DIR, role + ".lock")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


_k32.GetProcessTimes.argtypes = [_wt.HANDLE, ctypes.POINTER(_wt.FILETIME),
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


def claim(role: str, steal_stale: bool = True):
    """Atomically claim `role`. Returns True if we own it now."""
    os.makedirs(LOCK_DIR, exist_ok=True)
    path = os.path.join(LOCK_DIR, role + ".lock")

    for _ in range(3):
        live = holder(role)
        if live and int(live.get("pid", 0)) != os.getpid():
            return False
        if live and int(live.get("pid", 0)) == os.getpid():
            return True
        if not steal_stale and read_lock(role):
            return False

        payload = json.dumps(
            {
                "pid": os.getpid(),
                "role": role,
                "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "cmdline": " ".join(sys.argv)[:500],
            },
            indent=2,
        )
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            # exists but stale -> remove and retry
            try:
                os.remove(path)
            except Exception:
                return False
            continue
        try:
            os.write(fd, payload.encode("utf-8"))
        finally:
            os.close(fd)
        return True
    return False


def release(role: str) -> None:
    info = read_lock(role)
    if info and int(info.get("pid", 0)) == os.getpid():
        try:
            os.remove(os.path.join(LOCK_DIR, role + ".lock"))
        except Exception:
            pass


def status():
    """Return dict role -> holder info (or None) for every known lock."""
    out = {}
    if not os.path.isdir(LOCK_DIR):
        return out
    for fn in sorted(os.listdir(LOCK_DIR)):
        if not fn.endswith(".lock"):
            continue
        role = fn[: -len(".lock")]
        info = read_lock(role)
        alive = bool(info and _pid_alive(int(info.get("pid", 0))))
        out[role] = {"lock": info, "alive": alive}
    return out


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "status":
        print(json.dumps(status(), indent=2))
    elif len(sys.argv) >= 3 and sys.argv[1] == "claim":
        ok = claim(sys.argv[2])
        print("CLAIMED" if ok else "REFUSED")
        raise SystemExit(0 if ok else 1)
    else:
        print(__doc__)
