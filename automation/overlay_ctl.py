"""Control the ABRASAX floating-brain ImGui overlay from the command line.

The desktop `.bat` launcher needs three things that are painful to do in batch:

  * a single-instance guard, so double-clicking twice does not stack windows
  * a clean stop, for `ABRASAX-FloatingBrain.bat stop`
  * a renderer probe that cannot hang when nothing is listening on :9700

Batch would have to parse CIM output with string tools; every launcher in this
repo that tried that ended up targeting the wrong tree. So the logic lives here
and the .bat only calls it.

Commands
    status   exit 0 if an overlay instance is running, 1 otherwise
    stop     terminate every overlay instance (idempotent, exit 0)
    probe    exit 0 if the renderer answers /frame.png, 1 otherwise

A "instance" is counted by process ROOT, not by PID. On Windows a
`python.exe` from a venv is a launcher that spawns the real interpreter, so one
overlay is normally 2-3 PIDs (`cmd.exe -> shim -> uv python`). Counting PIDs
reported phantom duplicates in this repo before.
"""
from __future__ import annotations

import subprocess
import sys
import urllib.request
from pathlib import Path

MATCH = "imgui_overlay.py"
RENDERER = "http://127.0.0.1:9700/frame.png"
CREATE_NO_WINDOW = 0x08000000

# The overlay is always a python process. Filtering by NAME first kills a whole
# class of false matches that bit this file: PowerShell matches itself (the query
# contains this string), and any shell whose command line merely mentions the
# script -- a `bash -c` wrapper, a grep, a `Get-CimInstance` pipeline -- matches
# too. Command-line text is not identity; the image name is.
SELF_NAMES = {"powershell.exe", "pwsh.exe"}

PS_QUERY = (
    "Get-CimInstance Win32_Process | "
    "Where-Object { $_.CommandLine -like '*" + MATCH + "*' } | "
    "ForEach-Object { '{0}|{1}|{2}' -f $_.ProcessId, $_.ParentProcessId, $_.Name }"
)


def _ps(script: str, timeout: float = 60.0) -> str:
    """Run a PowerShell snippet without a console and without a shell."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
        return r.stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def processes() -> list[dict]:
    rows = []
    for line in _ps(PS_QUERY).splitlines():
        parts = line.strip().split("|")
        if len(parts) != 3 or not parts[0].isdigit():
            continue
        if parts[2].strip().lower() in SELF_NAMES:
            continue
        if not parts[2].strip().lower().startswith("python"):
            continue
        rows.append(
            {
                "pid": int(parts[0]),
                "ppid": int(parts[1]),
                "name": parts[2].strip().lower(),
            }
        )
    return rows


def roots(rows: list[dict]) -> list[dict]:
    """One entry per instance: the matched process whose parent is not matched."""
    pids = {r["pid"] for r in rows}
    return [r for r in rows if r["ppid"] not in pids]


def _sentinel() -> Path:
    """Marker that tells the supervising .bat the exit was intentional."""
    return Path(__file__).resolve().parent.parent.parent / "LOGS" / ".floating-brain.stop"


def probe(timeout: float = 4.0) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(RENDERER, timeout=timeout) as r:
            body = r.read(64)
        if r.status == 200 and body[:8] == b"\x89PNG\r\n\x1a\n":
            return True, f"renderer :9700 ok ({len(body)}+ bytes, PNG)"
        return False, f"renderer :9700 answered {r.status} but not a PNG"
    except Exception as e:  # noqa: BLE001 - a probe must never raise
        return False, f"renderer :9700 unreachable ({type(e).__name__})"


def stop() -> int:
    rows = processes()

    # THE SENTINEL COMES FIRST. The desktop launcher supervises the overlay and
    # restarts it whenever it exits non-zero, so a bare taskkill looks like a
    # crash and the window comes straight back -- "stop" that does not stop.
    # The launcher deletes this file when it starts, so a stale marker from a
    # previous stop cannot block a later start.
    _sentinel().write_text("stop\n", encoding="ascii")

    if not rows:
        print("no overlay running (stop marker set)")
        return 0

    by_pid = {r["pid"]: r for r in rows}
    py = [r for r in rows if r["name"].startswith("python")] or rows

    def has_python_ancestor(row: dict) -> bool:
        p = by_pid.get(row["ppid"])
        while p is not None:
            if p["name"].startswith("python"):
                return True
            p = by_pid.get(p["ppid"])
        return False

    # Kill the OUTERMOST python of each chain with /T. Killing every matched
    # python separately double-kills children: the first taskkill /T already
    # took the grandchild, so the second reports NativeCommandError. One
    # instance therefore equals one kill, and saying "2 instances" was wrong.
    heads = [r for r in py if not has_python_ancestor(r)]
    killed = 0
    for r in heads:
        out = _ps(f"taskkill /F /T /PID {r['pid']} 2>&1 | Out-String", timeout=30)
        line = next((ln.strip() for ln in out.splitlines() if "SUCCESS" in ln.upper()), "")
        print(f"  kill pid={r['pid']} ({r['name']}): {line or 'no confirmation'}")
        if line:
            killed += 1
    print(f"stopped {killed} instance(s)")
    return 0


def status(verbose: bool = True) -> int:
    rows = processes()
    inst = roots(rows)
    if verbose:
        if not rows:
            print("overlay : not running")
        else:
            print(f"overlay : {len(inst)} instance(s), {len(rows)} process(es)")
            for r in inst:
                tree, frontier = [r["pid"]], [r["pid"]]
                while frontier:
                    parent = frontier.pop()
                    for x in rows:
                        if x["ppid"] == parent and x["pid"] not in tree:
                            tree.append(x["pid"])
                            frontier.append(x["pid"])
                print(f"  root pid={r['pid']} {r['name']}  (pids {tree} = 1 instance)")
            if len(inst) > 1:
                print("  WARNING: more than one instance; the guard would have prevented this")
        ok, msg = probe() if verbose else (False, "")
        if verbose:
            print(f"          {msg}")
    return 0 if inst else 1


def main(argv: list[str]) -> int:
    cmd = (argv[1] if len(argv) > 1 else "status").lower()
    if cmd == "status":
        return status()
    if cmd == "stop":
        return stop()
    if cmd == "probe":
        ok, msg = probe()
        print(msg)
        return 0 if ok else 1
    if cmd == "quiet":
        return status(verbose=False)
    print(f"unknown command {cmd!r}; use status | stop | probe | quiet", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
