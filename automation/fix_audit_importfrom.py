"""Fix audit_testing.py: `from abrasax import x` did not register x as covered.

The extractor handled
    from abrasax.cbm_bridge import seed_to_cbm     -> imported.add("cbm_bridge")  OK
but not
    from abrasax import cbm, cbm_bridge            -> node.module == "abrasax"
                                                      names -> cbm, cbm_bridge
                                                      went into `bare_imports`

so test_cbm_bridge.py, which uses the second form, was invisible to the audit. It
kept reporting cbm_bridge as uncovered even after 28 passing tests were added.

Ninth false red tonight. The lesson is the same one, again: when a check disagrees
with reality, suspect the check first. The evidence that the check was wrong was
right there -- a test file importing the module existed and passed.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\audit_testing.py"
src = open(PATH, encoding="utf-8").read()

if "from abrasax import" in src or 'parts[0] == "abrasax"' in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("abrasax"):
                parts = node.module.split(".")
                if len(parts) > 1:
                    imported.add(parts[1])
                for a in node.names:
                    bare_imports.add(a.name)'''

NEW = '''        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("abrasax"):
                parts = node.module.split(".")
                if len(parts) > 1:
                    # from abrasax.NAME import ...      -> NAME is the module
                    imported.add(parts[1])
                else:
                    # from abrasax import a, b          -> a and b ARE modules
                    # (missing this made test_cbm_bridge.py invisible and kept
                    #  reporting cbm_bridge as uncovered)
                    for a in node.names:
                        imported.add(a.name)
                for a in node.names:
                    bare_imports.add(a.name)'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: ImportFrom handling")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: `from abrasax import x` now marks x as covered")
