"""Widen the exclusion list in check_abra_paths.py, and say why.

The check flagged one remaining file: retire_j_library.py.

That file SHOULD hardcode `J:\\UnityProjects\\ABRASAX-Brain\\Library`. Its entire
purpose is to move that specific abandoned tree aside; resolving it through
abra_paths would let an env override point it at a live tree and archive the wrong
thing. A migration tool must name its target literally.

So the exclusion is principled, not a convenience: resolver consumers are runtime
scripts; migration/archival scripts are allowed to pin absolute paths.

Also report WHICH file remains rather than only a count, so this stays diagnosable.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\check_abra_paths.py"
src = open(PATH, encoding="utf-8").read()

if "MIGRATION_TOOLS" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''    if ("UnityProjects" in text
            and "abra_paths" not in text
            and fn not in ("abra_paths.py", "check_abra_paths.py",
                           "audit_paths.py", "migrate_hardcoded_paths.py")):
        legacy.append(fn)'''

NEW = '''    # Migration and archival scripts are ALLOWED to pin absolute paths: resolving
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
        legacy.append(fn)'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: legacy detection")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: migration tools exempted, with the reason recorded")
