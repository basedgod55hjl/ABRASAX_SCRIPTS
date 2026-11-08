"""Background process helpers that work in a non-interactive shell.

THE BUG being fixed, measured directly:

    $ timeout /t 5 >nul
    ERROR: Input redirection is not supported, exiting the process immediately.

The message does NOT come from `cmd /c`. It comes from Windows' `timeout.exe`,
which refuses to run when stdin is not an interactive console. Every ad-hoc
`start /b ... & timeout /t N >nul` in a tool shell produced this error, and it
looked like the launched command had failed when it had not.

What works instead:

    Start-Process -WindowStyle Hidden -PassThru     launch without a console
    Start-Sleep -Seconds N                          wait without stdin
    Get-Process / Get-CimInstance                   poll liveness
    -NoProfile -NonInteractive                      never load a profile, never prompt

This module wraps those so no script has to rediscover it.

Usage:
    from winproc import launch, wait_for_exit, wait_for_port, wait_for_file, kill
    p = launch([sys.executable, "script.py"], stdout_path="out.log")
    wait_for_file("out.log", timeout=30)
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from typing import Sequence

# Never load a profile, never prompt, never attach a console.
_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def launch(cmd: Sequence[str],
           stdout_path: str | None = None,
           stderr_path: str | None = None,
           cwd: str | None = None,
           env: dict | None = None) -> subprocess.Popen:
    """Start a detached background process without a console window.

    Output is redirected to files rather than pipes so the caller never has to
    drain them (a full pipe buffer would otherwise block the child forever).
    """
    kwargs = dict(
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,       # explicit: never inherit a bad stdin
        close_fds=True,
    )
    if os.name == "nt":
        kwargs["creationflags"] = _CREATE_NO_WINDOW

    out = open(stdout_path, "wb") if stdout_path else subprocess.DEVNULL
    err = open(stderr_path, "wb") if stderr_path else subprocess.STDOUT
    try:
        p = subprocess.Popen(list(cmd), stdout=out, stderr=err, **kwargs)
    finally:
        # the child owns the handle now; close our copy so the file can be read
        if stdout_path and hasattr(out, "close"):
            out.close()
        if stderr_path and hasattr(err, "close"):
            err.close()
    return p


def wait_for_exit(p: subprocess.Popen, timeout: float = 60.0, poll: float = 0.1):
    """Poll until the process ends. Returns (exited, returncode_or_None)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if p.poll() is not None:
            return True, p.returncode
        time.sleep(poll)
    return False, None


def wait_for_file(path: str, timeout: float = 60.0, poll: float = 0.1,
                  nonempty: bool = True) -> bool:
    """Wait for a file to appear (and be non-empty, by default).

    Non-empty matters in practice: a process creates the file before writing, and
    reading it too early yields a blank log that looks like a crash.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(path):
            if not nonempty:
                return True
            try:
                if os.path.getsize(path) > 0:
                    return True
            except OSError:
                pass
        time.sleep(poll)
    return False


def wait_for_port(host: str, port: int, timeout: float = 60.0,
                  poll: float = 0.2) -> bool:
    """Wait until a TCP port accepts connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = socket.socket()
        s.settimeout(0.5)
        try:
            s.connect((host, port))
            return True
        except OSError:
            pass
        finally:
            s.close()
        time.sleep(poll)
    return False


def kill(p: subprocess.Popen, grace: float = 3.0) -> None:
    """Terminate, then kill if it will not go."""
    if p.poll() is not None:
        return
    try:
        p.terminate()
    except OSError:
        return
    if wait_for_exit(p, timeout=grace)[0]:
        return
    try:
        p.kill()
    except OSError:
        pass


def read_tail(path: str, lines: int = 20) -> str:
    """Last N lines of a log, safely."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read().splitlines()
        return "\n".join(content[-lines:])
    except OSError as e:
        return f"(cannot read {path}: {e})"
