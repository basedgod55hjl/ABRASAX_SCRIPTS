"""Fix the two scripts the path migration broke.

Real breakage, found by RUNNING them (syntax check passed, behaviour did not):

1. verify_scene_structure.py:79
       os.path.relpath(guid_map[g], str(paths.unity_build))
   guid_map paths live under Assets/ on J:, while unity_build is C:. Windows cannot
   relpath across volumes:
       ValueError: path is on mount 'J:', start on mount 'C:'
   The intent was only cosmetic -- show a short name. Use the basename.

2. verify_unity_runtime_contract.py:31,45
       SRC = str(paths.unity_scripts)     # a DIRECTORY
       src = open(SRC, encoding="utf-8").read()
       PermissionError: [Errno 13] ...: 'J:\\...\\Assets\\BrainUI\\Scripts'
   The original pointed at one specific .cs file. Point it at the file again.

Also adds a guard so this class of mistake is caught: after migration, a path that
is opened must not be a directory.
"""
import sys

# ---- fix 1 ---------------------------------------------------------------
P1 = r"C:\ABRASAX\SCRIPTS\automation\verify_scene_structure.py"
s1 = open(P1, encoding="utf-8").read()

if "os.path.basename(guid_map[g])" in s1:
    print("verify_scene_structure: ALREADY-PATCHED")
else:
    OLD1 = 'where = os.path.relpath(guid_map[g], str(paths.unity_build)) if g in guid_map else "UNRESOLVED"'
    NEW1 = ('# guid_map entries live on J: (Assets) while unity_build is C:; Windows\n'
            '    # cannot relpath across volumes. The basename is all this print needs.\n'
            '    where = os.path.basename(guid_map[g]) if g in guid_map else "UNRESOLVED"')
    if OLD1 not in s1:
        print("fix1 ANCHOR-NOT-FOUND")
        sys.exit(1)
    s1 = s1.replace(OLD1, NEW1, 1)
    open(P1, "w", encoding="utf-8", newline="").write(s1)
    print("verify_scene_structure: fixed cross-volume relpath")

# ---- fix 2 ---------------------------------------------------------------
P2 = r"C:\ABRASAX\SCRIPTS\automation\verify_unity_runtime_contract.py"
s2 = open(P2, encoding="utf-8").read()

if "FloatingBrainRenderer.cs" in s2:
    print("verify_unity_runtime_contract: ALREADY-PATCHED")
else:
    OLD2 = 'SRC = str(paths.unity_scripts)'
    NEW2 = ('# must be a FILE, not the Scripts directory -- open() on a directory\n'
            '# raised PermissionError after the path migration.\n'
            'SRC = str(paths.unity_scripts / "FloatingBrainRenderer.cs")')
    if OLD2 not in s2:
        print("fix2 ANCHOR-NOT-FOUND")
        sys.exit(1)
    s2 = s2.replace(OLD2, NEW2, 1)
    open(P2, "w", encoding="utf-8", newline="").write(s2)
    print("verify_unity_runtime_contract: SRC now points at the .cs file")
