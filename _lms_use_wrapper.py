from pathlib import Path

SUP = Path(r"C:\abrasax\SCRIPTS\automation\supervisor.py")
FIX = Path(r"C:\abrasax\SCRIPTS\fix_supervisor_lmstudio_autostart.py")

old = '''        "cmd": [str(_LMS), "server", "start"],
        "cwd": ROOT,'''
new = '''        # Not `lms server start` directly: stopping the server deletes
        # ~/.lmstudio/.internal/temp and the next load fails with ENOENT
        # (measured twice, 2026-11-01T18:57Z), so the wrapper recreates it and
        # waits for /v1/models before this process exits 0.
        "cmd": [sys.executable, str(ROOT / "tools" / "lmstudio_start.py")],
        "cwd": ROOT,'''

for p in (SUP, FIX):
    s = p.read_text(encoding="utf-8")
    if 'lmstudio_start.py' in s:
        print("already applied:", p.name)
        continue
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"{p}: anchor count {n}")
    p.write_text(s.replace(old, new, 1), encoding="utf-8", newline="")
    print("patched", p)
