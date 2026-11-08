import io, os, shutil

P = r"C:\ABRASAX\SCRIPTS\automation\supervisor.py"
src = io.open(P, encoding="utf-8").read()

OLD = '''    exe = spec.get("cmd") or []
    if exe and str(exe[0]).lower().endswith(".exe"):
        why = _exe_unrunnable(Path(exe[0]))
        if why:
            return {"error": f"unrunnable binary: {Path(exe[0]).name} ({why})",
                    "blocked": True}
    return None
'''

NEW = '''    exe = spec.get("cmd") or []
    if exe and str(exe[0]).lower().endswith(".exe"):
        target = Path(exe[0])
        if not target.exists():
            # Report the flag that is actually wrong. imagegen's entry names
            # Data/Packages/ComfyUI/venv/Scripts/python.exe, which does not exist
            # on this machine; calling that "python.exe missing" is misleading.
            return {"error": f"missing executable: {target}", "blocked": True}
        why = _exe_unrunnable(target)
        if why:
            return {"error": f"unrunnable binary: {target.name} ({why})",
                    "blocked": True}
    return None
'''

if OLD not in src:
    raise SystemExit("ANCHOR NOT FOUND")
src = src.replace(OLD, NEW, 1)

bak = P + ".bak-exeprobe2"
if not os.path.exists(bak):
    shutil.copy2(P, bak)
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("patched", P, os.path.getsize(P), "bytes")
