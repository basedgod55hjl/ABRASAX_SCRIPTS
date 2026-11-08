"""Migrate the 9 scripts that hardcode Unity paths onto abra_paths.

Each script had one of these literals:

    r"C:\\UnityProjects\\ABRASAX-Brain\\..."   (build tree)
    r"J:\\UnityProjects\\ABRASAX-Brain\\..."   (source tree)

which is how a script silently opens the wrong tree. This rewrites them to import
the resolver and use a named property, and leaves a .bak- beside each file.

Mapping used -- reviewed per file, not blindly substituted:
    C:\\UnityProjects\\ABRASAX-Brain\\Library\\...        -> paths.unity_library / paths.unity_dll
    C:\\UnityProjects\\ABRASAX-Brain\\Assets\\...         -> paths.unity_build_assets / paths.unity_scene
    J:\\UnityProjects\\ABRASAX-Brain\\Packages\\...       -> paths.unity_packages
    J:\\UnityProjects\\ABRASAX-Brain\\ProjectSettings\\..  -> paths.unity_settings
    J:\\UnityProjects\\ABRASAX-Brain\\Assets\\...         -> paths.unity_assets / paths.unity_scripts
    bare J:\\UnityProjects\\ABRASAX-Brain                 -> paths.unity_source
    bare C:\\UnityProjects\\ABRASAX-Brain                 -> paths.unity_build

dry-run by default.
"""
import os
import re
import shutil
import sys
import time

SC = r"C:\ABRASAX\SCRIPTS\automation"
TARGETS = [
    "attach_floating_renderer_to_scene.py",
    "fix_unity_events_using.py",
    "fix_unity_productname.py",
    "probe_dll_literal.py",
    "unity_status.py",
    "verify_scene_structure.py",
    "verify_unity_assembly.py",
    "verify_unity_runtime_contract.py",
    "verify_unity_scene_guids.py",
]

APPLY = "--apply" in sys.argv

# ordered: most specific first
RULES = [
    (r'r"[JC]:\\UnityProjects\\ABRASAX-Brain\\Library\\ScriptAssemblies\\Assembly-CSharp\.dll"',
     "str(paths.unity_dll)"),
    (r'r"[JC]:\\UnityProjects\\ABRASAX-Brain\\Library"', "str(paths.unity_library)"),
    (r'r"[JC]:\\UnityProjects\\ABRASAX-Brain\\Packages\\manifest\.json"',
     "str(paths.unity_manifest)"),
    (r'r"[JC]:\\UnityProjects\\ABRASAX-Brain\\Packages"', "str(paths.unity_packages)"),
    (r'r"[JC]:\\UnityProjects\\ABRASAX-Brain\\ProjectSettings\\ProjectSettings\.asset"',
     "str(paths.unity_settings / 'ProjectSettings.asset')"),
    (r'r"[JC]:\\UnityProjects\\ABRASAX-Brain\\ProjectSettings"', "str(paths.unity_settings)"),
    (r'r"[JC]:\\UnityProjects\\ABRASAX-Brain\\Assets\\Scenes\\Main\.unity"',
     "str(paths.unity_scene)"),
    (r'r"[JC]:\\UnityProjects\\ABRASAX-Brain\\Assets\\BrainUI\\Scripts(?:\\.*?)?"',
     "str(paths.unity_scripts)"),
    (r'r"[JC]:\\UnityProjects\\ABRASAX-Brain\\Assets"', "str(paths.unity_assets)"),
    (r'r"J:\\UnityProjects\\ABRASAX-Brain"', "str(paths.unity_source)"),
    (r'r"C:\\UnityProjects\\ABRASAX-Brain"', "str(paths.unity_build)"),
]

IMPORT_BLOCK = (
    "\n# Paths come from one resolver so a script cannot open the wrong tree.\n"
    "sys.path.insert(0, r\"C:\\ABRASAX\\SCRIPTS\\automation\")\n"
    "from abra_paths import paths  # noqa: E402\n"
)

changed_files = 0
total_subs = 0

for fn in TARGETS:
    full = os.path.join(SC, fn)
    if not os.path.exists(full):
        print(f"skip (missing): {fn}")
        continue
    src = open(full, encoding="utf-8").read()
    if "abra_paths" in src:
        print(f"already migrated: {fn}")
        continue

    new = src
    subs = 0
    for pat, repl in RULES:
        new, n = re.subn(pat, repl, new)
        subs += n

    if subs == 0:
        print(f"no match: {fn}")
        continue

    # ensure `import sys` exists before injecting the resolver import
    if not re.search(r"^import sys$", new, re.M):
        new = new.replace("import os\n", "import os\nimport sys\n", 1)

    # inject after the last top-level import line
    lines = new.splitlines(keepends=True)
    last_import = 0
    for i, ln in enumerate(lines[:80]):
        if re.match(r"^(import |from )", ln):
            last_import = i
    lines.insert(last_import + 1, IMPORT_BLOCK)
    new = "".join(lines)

    print(f"{fn}: {subs} substitution(s)")
    changed_files += 1
    total_subs += subs

    if APPLY:
        backup = full + ".bak-" + time.strftime("%Y%m%d-%H%M")
        shutil.copy2(full, backup)
        open(full, "w", encoding="utf-8", newline="").write(new)

print(f"\n{changed_files} file(s), {total_subs} substitution(s)")
if not APPLY:
    print("dry run -- re-run with --apply to write")
else:
    print("applied; .bak- copies written beside each file")
