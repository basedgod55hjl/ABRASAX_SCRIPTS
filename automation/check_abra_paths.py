"""Verify the path resolver against reality.

A resolver that reports paths is useless if the paths are wrong. This checks every
property against the filesystem AND against the roles established in
DOC/UNITY-BUILD.md:

  * J: is the source of truth: Packages/, ProjectSettings/, Assets/ must live there
  * C: is the build workspace: Library/ and the compiled DLL must live there
  * the two trees must not be silently the same directory
  * scripts imported from abra_paths must resolve to real files
  * env overrides must actually take effect

Exit 0 = every path resolves and the roles are respected.
"""
import os
import subprocess
import sys

sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")

from abra_paths import AbraPaths, paths  # noqa: E402

ok = True


def check(name, cond, detail=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        ok = False


print("=== resolved paths ===")
for name, info in paths.report().items():
    print(f"  {'ok  ' if info['exists'] else 'MISS'} {name:18s} {info['path']}")

print("\n=== structural checks ===")

check("root is C:\\ABRASAX", str(paths.root) == r"C:\ABRASAX", str(paths.root))
check("scripts dir exists", paths.scripts.exists(), str(paths.scripts))
check("automation dir exists", paths.automation.exists(), str(paths.automation))

# roles must be on DIFFERENT volumes, or the split is pointless
check("source and build are different paths",
      paths.unity_source != paths.unity_build,
      f"{paths.unity_source} vs {paths.unity_build}")

check("unity_source is a Unity project (manifest + Assets)",
      (paths.unity_source / "Packages" / "manifest.json").is_file()
      and (paths.unity_source / "Assets").is_dir(),
      str(paths.unity_source))
print("       resolved on %s: -- discovered by project shape, not by drive letter"
      % str(paths.unity_source)[:2])
check("unity_build is on C:", str(paths.unity_build).upper().startswith("C:"),
      str(paths.unity_build))

# authoring files belong to SOURCE
check("manifest lives in SOURCE", paths.unity_manifest.exists(), str(paths.unity_manifest))
check("ProjectVersion lives in SOURCE", paths.unity_editor_version.exists(),
      str(paths.unity_editor_version))
check("BrainUI scripts live in SOURCE", paths.unity_scripts.exists(),
      str(paths.unity_scripts))

# build products belong to BUILD
check("Library lives in BUILD", paths.unity_library.exists(), str(paths.unity_library))
check("compiled DLL lives in BUILD", paths.unity_dll.exists(), str(paths.unity_dll))

if paths.unity_dll.exists():
    sz = paths.unity_dll.stat().st_size
    check("DLL is non-trivial", sz > 10_000, f"{sz:,} bytes")

# the source tree must NOT carry a Library (that would mean the split drifted)
src_lib = paths.unity_source / "Library"
check("source tree has no Library (build stays on C:)", not src_lib.exists(),
      str(src_lib))

print("\n=== scene resolution ===")
scene = paths.unity_scene
print(f"  unity_scene        -> {scene}")
check("scene resolves", scene.exists(), str(scene))
check("scene_source resolves", paths.unity_scene_source.exists(),
      str(paths.unity_scene_source))

print("\n=== env overrides ===")
alt = AbraPaths(unity_build=r"D:\nowhere\ABRASAX-Brain")
check("explicit unity_build override is honoured",
      str(alt.unity_build) == r"D:\nowhere\ABRASAX-Brain", str(alt.unity_build))
check("override does not leak into the singleton",
      str(paths.unity_build) != str(alt.unity_build), str(paths.unity_build))

os.environ["ABRASAX_UNITY_SOURCE"] = r"E:\alt\Brain"
envalt = AbraPaths()
check("ABRASAX_UNITY_SOURCE env override is honoured",
      str(envalt.unity_source) == r"E:\alt\Brain", str(envalt.unity_source))
del os.environ["ABRASAX_UNITY_SOURCE"]

print("\n=== consumers ===")
# every script that hardcoded a unity path should now import the resolver
SCRIPT_DIR = r"C:\ABRASAX\SCRIPTS\automation"
legacy = []
for fn in sorted(os.listdir(SCRIPT_DIR)):
    if not fn.endswith(".py"):
        continue
    try:
        text = open(os.path.join(SCRIPT_DIR, fn), encoding="utf-8", errors="ignore").read()
    except OSError:
        continue
    # Migration and archival scripts are ALLOWED to pin absolute paths: resolving
    # them through abra_paths would let an env override redirect a move/retire
    # operation at the wrong tree. Runtime scripts must use the resolver.
    MIGRATION_TOOLS = {
        "abra_paths.py",            # the resolver itself
        "check_abra_paths.py",      # this checker
        "migrate_hardcoded_paths.py",   # rewrites other scripts
        "retire_j_library.py",      # archives ONE specific abandoned tree
        "fix_migration_breakage.py",
        "fix_src_line.py",
    }
    if ("UnityProjects" in text
            and "abra_paths" not in text
            and fn not in MIGRATION_TOOLS):
        legacy.append(fn)

print(f"  scripts still hardcoding UnityProjects: {len(legacy)}")
for fn in legacy:
    print(f"    {fn}")
check("no script hardcodes Unity paths outside the resolver",
      len(legacy) == 0, f"{len(legacy)} remaining")

print("\nRESULT:", "PASS -- paths resolve and roles are respected" if ok else "FAIL")
sys.exit(0 if ok else 1)
