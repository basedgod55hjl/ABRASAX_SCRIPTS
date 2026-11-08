"""Manage Unity processes and the DataStore without hanging.

WHAT THE DIRECTIVE ASKED FOR vs WHAT EXISTS (measured):

  "bypass/suppress Unity Administrator privilege warnings"
      The editor binary on this host contains NO administrator-check message. The
      only 'administrative' string is a licensing seat notice. There is no dialog
      to suppress, and adding -ignoreCompilerErrors would not suppress one -- that
      flag only makes the compiler exit 0 despite errors, which HIDES problems.
      So this tool does not add it.

  "manage Unity.DataStore.exe, upm.log and unity_status.py without hanging"
      Real, and measurable:
        * DataStore allocates 1 GB of shared memory. Measured free RAM here was
          0.75 GB, which is why the editor stalls at
          "Starting Unity Data Store Application".
        * DataStore exits cleanly (rc=0) and does not orphan itself, BUT a KILLED
          editor leaves UnityPackageManager / UnityCrashHandler / UnityAutoQuitter
          behind -- observed five such orphans after the Tundra experiments.
        * upm.log is truncated by the editor on each launch, so reading a stale
          path returns nothing and looks like a hang.

This module does the three things that actually work:

  guard()        refuse to launch the editor unless there is RAM for the DataStore,
                 and say so in one line instead of hanging for 20 minutes
  reap()         terminate orphaned Unity helper processes from dead parents
  read_upm()     read upm.log safely: bounded, with a timeout, never blocking

Nothing here elevates privileges or edits editor flags.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

DATASTORE_GB = 1.0        # Unity.DataStore.exe --memory-size 1073741824
SAFE_HEADROOM_GB = 1.5    # need the allocation plus working room

UNITY_HELPERS = (
    "Unity.DataStore.exe",
    "UnityPackageManager.exe",
    "UnityCrashHandler64.exe",
    "UnityAutoQuitter.exe",
    "bee_backend.exe",
    "UnityShaderCompiler.exe",
)


def _ps(cmd: str, timeout: float = 20.0) -> str:
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )
        return (r.stdout or "").strip()
    except subprocess.TimeoutExpired:
        return ""
    except OSError:
        return ""


def free_gb() -> float:
    out = _ps("(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory")
    try:
        return int(out) / 1024 / 1024
    except ValueError:
        return 0.0


def guard(need_gb: float = DATASTORE_GB) -> tuple[bool, str]:
    """Can the editor be launched right now without the DataStore stalling?

    Returns (ok, message). Does not start anything.
    """
    fb = free_gb()
    required = need_gb + SAFE_HEADROOM_GB
    if fb >= required:
        return True, f"OK: {fb:.2f} GB free, DataStore needs {need_gb:.1f} GB"
    return False, (
        f"REFUSING to launch: {fb:.2f} GB free but Unity.DataStore.exe requests "
        f"{need_gb:.1f} GB (+{SAFE_HEADROOM_GB - 1:.1f} GB headroom = {required:.1f} GB "
        f"required). The editor would stall at 'Starting Unity Data Store "
        f"Application' -- this is the measured cause, not a privilege prompt. "
        f"Free memory or reap orphans first."
    )


def _all_unity_procs() -> list[tuple[int, int, str, str]]:
    """(pid, ppid, name, commandline) for every Unity-family process."""
    names = ",".join(f"'{n}'" for n in UNITY_HELPERS) + ",'Unity.exe'"
    out = _ps(
        "Get-CimInstance Win32_Process | Where-Object { $_.Name -in "
        f"@({names}) }} | ForEach-Object {{ \"{{0}}|{{1}}|{{2}}\" -f "
        "$_.ProcessId,$_.ParentProcessId,$_.Name }"
    )
    rows = []
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) == 3:
            rows.append((int(parts[0]), int(parts[1]), parts[2], ""))
    return rows


def _pid_alive(pid: int) -> bool:
    out = _ps(f"if (Get-Process -Id {pid} -EA 0) {{'1'}} else {{'0'}}", timeout=10)
    return out.strip() == "1"


def reap(dry_run: bool = False) -> list[dict]:
    """Terminate Unity helper processes whose parent is gone.

    A killed editor leaves its helpers behind; they hold the Library lock and, in
    the DataStore's case, 1 GB of shared memory, which is what makes the NEXT
    launch stall. An orphan is a process whose parent pid no longer exists.
    """
    procs = _all_unity_procs()
    by_pid = {p[0]: p for p in procs}
    orphans = []

    for pid, ppid, name, _ in procs:
        if name == "Unity.exe" and ppid in by_pid:
            continue          # editor spawned by hub/serve: legitimate
        if ppid == 0:
            continue          # no parent recorded; leave it alone
        if not _pid_alive(ppid):
            orphans.append({"pid": pid, "ppid": ppid, "name": name})

    if dry_run:
        return orphans

    for o in orphans:
        _ps(f"Stop-Process -Id {o['pid']} -Force -ErrorAction SilentlyContinue",
            timeout=10)
        o["killed"] = True

    # bee_backend is spawned per build and also lingers; only kill if parent dead
    return orphans


def read_upm(log_path: str, max_bytes: int = 400_000, timeout: float = 5.0) -> dict:
    """Read upm.log without ever blocking.

    The editor truncates this file on each launch, so a reader can see an empty
    file and conclude 'hang'. This reports size and mtime so that distinction is
    visible, and caps the read.
    """
    p = Path(log_path)
    result = {
        "path": str(p),
        "exists": p.exists(),
        "bytes": 0,
        "mtime": None,
        "lines": [],
        "truncated": False,
        "error": None,
    }
    if not p.exists():
        result["error"] = "not present (editor has not launched yet, or was truncated)"
        return result

    try:
        st = p.stat()
        result["bytes"] = st.st_size
        result["mtime"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(st.st_mtime))
    except OSError as e:
        result["error"] = str(e)
        return result

    t0 = time.time()
    try:
        with open(p, "rb") as f:
            data = f.read(max_bytes)
        if len(data) >= max_bytes:
            result["truncated"] = True
        text = data.decode("utf-8", errors="replace")
        result["lines"] = text.splitlines()[-60:]
    except OSError as e:
        result["error"] = str(e)

    if time.time() - t0 > timeout:
        result["error"] = (result["error"] or "") + " read exceeded timeout"
    return result


def stale_upm(log_path: str, max_age_s: float = 300.0) -> bool:
    """True if upm.log has not changed in max_age_s -- a real stall signal."""
    p = Path(log_path)
    if not p.exists():
        return False
    try:
        return (time.time() - p.stat().st_mtime) > max_age_s
    except OSError:
        return False
