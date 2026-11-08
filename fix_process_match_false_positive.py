"""fix_process_match_false_positive.py -- a wrapper is not the process it names.

Measured 2026-11-01 16:32Z: verify_stack_run.py reported TWO logical supervisors,
the second being

  powershell.exe -Command "... Stop-Process -Id 31148 ... Start-Process ... supervisor.py ..."

A PowerShell whose *command line mentions* supervisor.py was counted as a
supervisor. Same family of bug as align calling a shim pair a duplicate: matching
must look at the process's own identity, not at any string it carries.

Rule applied in both places:
  * verify_stack_run.py: a supervisor is a process whose image is a Python
    interpreter AND whose command line contains supervisor.py as a whole token.
  * abrasax_align.py: never classify a shell wrapper (powershell/pwsh/cmd/conhost)
    as a role, whatever its command line quotes.

Idempotent. Backs up each edited file to .bak-procmatch-YYYYMMDD.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(r"C:\abrasax")
VER = ROOT / "SCRIPTS" / "verify_stack_run.py"
ALIGN = ROOT / "SCRIPTS" / "automation" / "abrasax_align.py"

VER_OLD = '''def _sample_supervisor_procs() -> list[tuple[int, int]]:
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
'''

VER_NEW = '''SHELL_IMAGES = {"powershell.exe", "pwsh.exe", "cmd.exe", "conhost.exe",
                "bash.exe", "wmic.exe", "windowsterminal.exe"}


def _is_supervisor_proc(name: str, cmdline: str) -> bool:
    """Pure predicate: is THIS process a supervisor, not a wrapper that names one?

    A PowerShell that restarts the supervisor quotes "supervisor.py" in its own
    command line (measured 2026-11-01); matching any string a process carries
    counted it as a second supervisor.
    """
    image = (name or "").strip().lower()
    if image in SHELL_IMAGES:
        return False
    if not image.startswith("python"):
        return False
    cmd = (cmdline or "").replace("/", "\\\\").lower()
    for tok in cmd.replace('"', " ").split():
        if tok.endswith("supervisor.py") or tok.endswith("supervisor.py\\\\"):
            return True
    return False


def _sample_supervisor_procs() -> list[tuple[int, int]]:
    """(pid, parent_pid) for every process that IS a supervisor."""
    try:
        ps = ("Get-CimInstance Win32_Process | Where-Object {$_.Name -like 'python*'} | "
              "ForEach-Object { \\"$($_.ProcessId)|$($_.ParentProcessId)|$($_.Name)|$($_.CommandLine)\\" }")
        txt = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, timeout=40).stdout
    except Exception:  # noqa: BLE001
        return []
    out: list[tuple[int, int]] = []
    for line in txt.splitlines():
        parts = line.split("|", 3)
        if len(parts) < 4:
            continue
        pid, ppid, name, cmd = parts
        if not (pid.isdigit() and ppid.isdigit()):
            continue
        if _is_supervisor_proc(name, cmd):
            out.append((int(pid), int(ppid)))
    return out
'''

ALIGN_OLD = '''    role_hits = defaultdict(list)
    for p in procs:
        cl = (p.get("CommandLine") or "").replace("/", "\\\\")
        for role, needle in ROLES.items():
            if needle.lower() in cl.lower():
                role_hits[role].append(p)
'''

ALIGN_NEW = '''    role_hits = defaultdict(list)
    for p in procs:
        # A wrapper that mentions the script is not the script: a PowerShell
        # restarting the overlay quotes "imgui_overlay.py" in its own command
        # line (measured 2026-11-01) and was counted as a second instance.
        if str(p.get("Name") or "").strip().lower() in (
                "powershell.exe", "pwsh.exe", "cmd.exe", "conhost.exe",
                "bash.exe", "wmic.exe"):
            continue
        cl = (p.get("CommandLine") or "").replace("/", "\\\\")
        for role, needle in ROLES.items():
            if needle.lower() in cl.lower():
                role_hits[role].append(p)
'''


def _patch(path: Path, old: str, new: str, marker: str) -> bool:
    src = path.read_text(encoding="utf-8")
    if marker in src:
        print(f"{path.name}: already patched")
        return True
    if old not in src:
        print(f"{path.name}: ANCHOR NOT FOUND -- refusing to guess")
        return False
    bak = path.with_suffix(".py.bak-procmatch-" + dt.date.today().strftime("%Y%m%d"))
    bak.write_text(src, encoding="utf-8")
    path.write_text(src.replace(old, new, 1), encoding="utf-8")
    print(f"{path.name}: patched (backup {bak.name})")
    return True


def main() -> int:
    ok = _patch(VER, VER_OLD, VER_NEW, "_is_supervisor_proc")
    ok = _patch(ALIGN, ALIGN_OLD, ALIGN_NEW, "A wrapper that mentions the script") and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
