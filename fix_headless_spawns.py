"""fix_headless_spawns.py - no child of the windowless runtime may open a console.

MEASURED 2026-11-01T19:1xZ on the live stack (SCRIPTS/_probe_visible_consoles.py):

    visible console windows on the desktop: 3
      - 2 x "Administrator: Windows PowerShell"  (the operator's own term.cmd)
      - 1 x llama-server.exe, pid 9028, the :8083 service this tree started

So `llamacpp-local` was sitting on the desktop as a black window. Cause:
`tools/llamacpp_serve.py` spawned it with CREATE_NEW_PROCESS_GROUP and no
CREATE_NO_WINDOW, and `pythonw.exe` cannot give a console child a hidden
console - Windows allocates a new one.

Sites fixed here (all in the live path):

  tools/llamacpp_serve.py   llama-server spawn, nvidia-smi probe, taskkill/gpu
                            powershell helpers
  tools/lmstudio_start.py   every `lms` invocation
  abrasax/services.py       the `services --start` launcher call (powershell)

Each goes through `abrasax.winproc` so there is one rule, not five opinions.

Idempotent: re-running changes nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\abrasax")

LLAMA = ROOT / "tools" / "llamacpp_serve.py"
LMS = ROOT / "tools" / "lmstudio_start.py"
SERV = ROOT / "abrasax" / "services.py"

IMPORT_BLOCK = '''import urllib.request
'''
IMPORT_NEW = '''import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from abrasax import winproc  # noqa: E402
'''

LLAMA_POPEN_OLD = '''    proc = subprocess.Popen(args, cwd=BACKEND, stdout=logf, stderr=subprocess.STDOUT,
                            env=env, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)'''
LLAMA_POPEN_NEW = '''    # CREATE_NO_WINDOW or the child console appears on the desktop: measured
    # 2026-11-01, pid 9028 was a visible llama-server window on :8083.
    proc = winproc.spawn(args, detached=True, cwd=BACKEND, stdout=logf,
                         stderr=subprocess.STDOUT, env=env)'''

LLAMA_SMI_OLD = '''        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=30).stdout.strip()'''
LLAMA_SMI_NEW = '''        out = winproc.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=30).stdout.strip()'''

LLAMA_PS_OLD = '''    r = subprocess.run(["powershell", "-NoProfile", "-Command",'''
LLAMA_PS_NEW = '''    r = winproc.run(["powershell", "-NoProfile", "-Command",'''

LMS_RUN_OLD = '''        cp = subprocess.run([str(LMS), *args], capture_output=True, text=True,
                            timeout=timeout, encoding="utf-8", errors="replace")'''
LMS_RUN_NEW = '''        cp = winproc.run([str(LMS), *args], capture_output=True, text=True,
                          timeout=timeout, encoding="utf-8", errors="replace")'''

LMS_IMPORT_OLD = '''import urllib.request
from pathlib import Path
'''
LMS_IMPORT_NEW = '''import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from abrasax import winproc  # noqa: E402
'''

SERV_OLD = '''    exe = shutil.which("powershell") or "powershell"
    cmd = [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(LAUNCHER)]
    cmd.extend(extra_argv)
    cp = subprocess.run(cmd, cwd=str(ROOT))
    return int(cp.returncode or 0)'''
SERV_NEW = '''    exe = shutil.which("powershell") or "powershell"
    cmd = [exe, "-NoProfile", "-ExecutionPolicy", "Bypass",
           "-WindowStyle", "Hidden", "-File", str(LAUNCHER)]
    cmd.extend(extra_argv)
    # Windowless parent + console child = a new console window unless the flag
    # is set; `services --start` is called from pythonw by the supervisor path.
    from . import winproc
    cp = winproc.run(cmd, cwd=str(ROOT))
    return int(cp.returncode or 0)'''

PATCHES = {
    LLAMA: [(IMPORT_BLOCK, IMPORT_NEW), (LLAMA_POPEN_OLD, LLAMA_POPEN_NEW),
            (LLAMA_SMI_OLD, LLAMA_SMI_NEW), (LLAMA_PS_OLD, LLAMA_PS_NEW)],
    LMS: [(LMS_IMPORT_OLD, LMS_IMPORT_NEW), (LMS_RUN_OLD, LMS_RUN_NEW)],
    SERV: [(SERV_OLD, SERV_NEW)],
}


def main() -> int:
    changed = []
    for path, pairs in PATCHES.items():
        src = path.read_text(encoding="utf-8")
        before = src
        for old, new in pairs:
            if new in src:
                continue
            n = src.count(old)
            if n != 1:
                raise SystemExit(f"{path}: anchor {n}x: {old[:60]!r}")
            src = src.replace(old, new, 1)
        if src != before:
            path.write_text(src, encoding="utf-8", newline="")
            changed.append(path)
    for p in changed:
        print("patched", p)
    if not changed:
        print("already applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
