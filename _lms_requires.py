from pathlib import Path

SUP = Path(r"C:\abrasax\SCRIPTS\automation\supervisor.py")
FIX = Path(r"C:\abrasax\SCRIPTS\fix_supervisor_lmstudio_autostart.py")

old = '''        "cmd": [str(_LMS), "server", "start"],
        "cwd": ROOT,
        "required_bind": 1234,'''
new = '''        "cmd": [str(_LMS), "server", "start"],
        "cwd": ROOT,
        "requires": [str(_LMS)],
        "required_bind": 1234,'''

sup = SUP.read_text(encoding="utf-8")
if '"requires": [str(_LMS)]' in sup:
    print("supervisor already has requires")
else:
    assert sup.count(old) == 1, sup.count(old)
    SUP.write_text(sup.replace(old, new, 1), encoding="utf-8", newline="")
    print("supervisor patched with requires")

fix = FIX.read_text(encoding="utf-8")
if '"requires": [str(_LMS)]' in fix:
    print("fix script already has requires")
else:
    assert fix.count(old) == 1, fix.count(old)
    FIX.write_text(fix.replace(old, new, 1), encoding="utf-8", newline="")
    print("fix script patched with requires")
