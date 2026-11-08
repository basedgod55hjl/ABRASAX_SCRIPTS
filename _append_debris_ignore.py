from pathlib import Path

gi = Path(r"C:\abrasax\.gitignore")
src = gi.read_text(encoding="utf-8")
block = Path(r"C:\abrasax\.gitignore.debris").read_text(encoding="utf-8")
if "/_*.err" in src:
    print("already applied")
else:
    gi.write_text(src.rstrip() + "\n\n" + block, encoding="utf-8", newline="")
    print("appended debris rules")
