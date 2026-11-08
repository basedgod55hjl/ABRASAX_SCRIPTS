from pathlib import Path

gi = Path(r"C:\abrasax\.gitignore")
src = gi.read_text(encoding="utf-8")
block = """
# ---- Unity generated caches (per project) ----
# Measured 2026-11-01: UnityProjects/ABRASAX-CLI-Demo is 25,337 files / 1.29 GB,
# almost all of it Library/ (ArtifactDB, Bee traces, shader caches). `git add -A`
# spent >10 min CPU-bound on it and had to be killed twice; a repo that carries
# regenerable caches cannot be staged. Track Assets/, Packages/, ProjectSettings/;
# let Unity rebuild the rest.
/UnityProjects/*/Library/
/UnityProjects/*/Temp/
/UnityProjects/*/Logs/
/UnityProjects/*/obj/
/UnityProjects/*/UserSettings/
/.gitignore.debris
"""
if "/UnityProjects/*/Library/" in src:
    print("already applied")
else:
    gi.write_text(src.rstrip() + "\n" + block, encoding="utf-8", newline="")
    print("appended unity cache rules")
