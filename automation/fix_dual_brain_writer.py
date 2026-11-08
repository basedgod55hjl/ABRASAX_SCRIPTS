"""fix_dual_brain_writer.py -- one writer for LOGS/brain_state.json.

Defect: the supervisor's AUTOSTART spec for "jev-brain-bridge" launched
ENGINE/floating_brain/jev_brain_state.py, a RETIRED writer with the old schema
(no embed_ok; embed_mode can fall back to "none"; non-atomic open("w")). The
canonical writer is tools/brain_state_writer.py. Both ran every 5 s, so the file
alternated schemas and the overlay (which rejects state older than 15 s) flipped
to stale: test_overlay_jev_wiring FAILED with age=71.3s while embed_mode flipped
between nomic-768 and err:HTTPError500.

This repoints the supervised role at the canonical writer, fixes its cwd, kills
stray copies of the retired writer, and proves exactly one writer remains.

Idempotent: safe to re-run on a fresh checkout (SCRIPTS/ is gitignored).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\abrasax")
SUP = ROOT / "SCRIPTS" / "automation" / "supervisor.py"
CANON = "C:/abrasax/tools/brain_state_writer.py"

OLD_CMD = '"cmd": [sys.executable, "-u", "jev_brain_state.py"],'
NEW_CMD = '"cmd": [sys.executable, "-u", "%s"],' % CANON
OLD_CWD = '"cwd": ROOT / "ENGINE" / "floating_brain",'
NEW_CWD = '"cwd": ROOT,  # canonical writer resolves its own paths from ROOT'


def main() -> int:
    src = SUP.read_text(encoding="utf-8")
    # undo the mangled first attempt if it is present (comment inside a list)
    src = src.replace(
        '"cmd": [sys.executable, "-u", "%s"  # tools/brain_state_writer.py is the ONE writer],'
        % CANON,
        NEW_CMD,
    )
    if CANON in src and OLD_CWD not in src:
        print("already patched")
    else:
        if OLD_CMD not in src:
            print("FAIL: bridge cmd line not found; supervisor.py has drifted")
            return 2
        bak = SUP.with_suffix(".py.bak-dualwriter")
        if not bak.exists():
            shutil.copy2(SUP, bak)
            print("backup -> %s" % bak)
        patched = src.replace(OLD_CMD, NEW_CMD + "  # the ONE writer", 1)
        if patched == src:
            print("FAIL: cmd replacement did not apply")
            return 3
        # cwd must be ROOT, not the engine dir (the writer uses absolute paths,
        # but a stray relative import must not resolve to the retired module)
        idx = patched.index(NEW_CMD)
        tail = patched[idx:]
        if OLD_CWD not in tail[:400]:
            print("FAIL: cwd line not found after cmd line")
            return 4
        patched = patched[:idx] + tail.replace(OLD_CWD, NEW_CWD, 1)
        SUP.write_text(patched, encoding="utf-8")
        print("patched supervisor.py -> canonical writer")

    rc = subprocess.run([sys.executable, "-m", "py_compile", str(SUP)],
                        capture_output=True, text=True)
    print("py_compile rc=%d %s" % (rc.returncode, rc.stderr.strip()[:400]))
    if rc.returncode:
        return 5

    ps = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
          "Where-Object {$_.CommandLine -match 'jev_brain_state'} | "
          "ForEach-Object { $_.ProcessId }")
    q = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True)
    pids = [l.strip() for l in q.stdout.splitlines() if l.strip().isdigit()]
    for pid in pids:
        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
        print("killed retired writer pid=%s" % pid)
    if not pids:
        print("no retired writer running")

    q2 = subprocess.run(["powershell", "-NoProfile", "-Command",
                         "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                         "Where-Object {$_.CommandLine -match 'brain_state'} | "
                         "Select-Object -ExpandProperty CommandLine"],
                        capture_output=True, text=True)
    lines = [l.strip() for l in q2.stdout.splitlines() if l.strip()]
    print(json.dumps({"writers": lines}, indent=2))
    ok = len(lines) >= 1 and all("brain_state_writer" in l for l in lines)
    print("SINGLE_WRITER=%s" % ok)
    return 0 if ok else 6


if __name__ == "__main__":
    sys.exit(main())
