from pathlib import Path

gi = Path(r"C:\abrasax\.gitignore")
src = gi.read_text(encoding="utf-8")
block = """# Unity/VS regenerate these; they name absolute paths from the machine that
# opened the project.
/UnityProjects/*/*.csproj
/UnityProjects/*/*.slnx
/UnityProjects/*/*.sln
"""
if "/UnityProjects/*/*.csproj" in src:
    print("already applied")
else:
    gi.write_text(src.rstrip() + "\n" + block, encoding="utf-8", newline="")
    print("appended csproj rules")
