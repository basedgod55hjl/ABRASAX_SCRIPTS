from pathlib import Path

gi = Path(r"C:\abrasax\.gitignore")
lines = gi.read_text(encoding="utf-8").splitlines()
if "UnityProjects/**/Library/" in lines:
    print("already applied")
    raise SystemExit(0)

text = "\n".join(lines) + "\n"
old = """/UnityProjects/*/Library/
/UnityProjects/*/Temp/
/UnityProjects/*/Logs/
/UnityProjects/*/obj/
/UnityProjects/*/UserSettings/
"""
new = """# `**/` not `*/`: a nested project must be covered too. FINDINGS_UNITY_CSPROJ.md
# measured 1,424 tracked files / 69.1 MB under just one Library/ (662 .meta,
# 448 .cs from PackageCache, 88 .bhc shader caches); all of it is rebuilt from
# Packages/manifest.json + packages-lock.json, which stay tracked.
UnityProjects/**/Library/
UnityProjects/**/Temp/
UnityProjects/**/Logs/
UnityProjects/**/obj/
UnityProjects/**/UserSettings/
"""
old2 = """/UnityProjects/*/*.csproj
/UnityProjects/*/*.slnx
/UnityProjects/*/*.sln
"""
new2 = """UnityProjects/**/*.csproj
UnityProjects/**/*.slnx
UnityProjects/**/*.sln
"""
assert text.count(old) == 1, text.count(old)
assert text.count(old2) == 1, text.count(old2)
text = text.replace(old, new, 1).replace(old2, new2, 1)
gi.write_text(text, encoding="utf-8", newline="")
print("broadened to **")
