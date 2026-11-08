"""Fix the dependency mapper: relative imports were dropped entirely.

diagnose_import_scan.py proved it:

    cli.py       absolute=7   RELATIVE=29   (level=1 module=None names=['llm'])
    gateway.py   absolute=14  RELATIVE=1    (level=1 module=None names=['usage'])

The package uses `from . import llm` style throughout -- 29 such edges in cli.py
alone. My extractor collected only names beginning with "abrasax.", and a relative
import carries no such prefix: `ImportFrom(level=1, module=None, names=['llm'])`.

Result: every module reported as a leaf imported by nothing. The graph was not
sparse, it was empty, and it would have been reported as evidence that "nothing
calls anything" -- the exact opposite of the truth.

Fix: treat level>0 as an intra-package edge and resolve both forms:
    from . import llm            -> module=llm
    from .llm import ask         -> module=llm
    from abrasax.llm import ask  -> module=llm
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\map_dependencies.py"
src = open(PATH, encoding="utf-8").read()

if "RELATIVE" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''def module_imports(path: str) -> set[str]:
    """Top-level and intra-package imports of one Python file."""
    try:
        src = open(path, encoding="utf-8", errors="replace").read()
        tree = ast.parse(src)
    except (OSError, SyntaxError):
        return set()
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name.split(".")[0])
                if a.name.startswith("abrasax."):
                    parts = a.name.split(".")
                    if len(parts) > 1:
                        out.add("abrasax." + parts[1])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out.add(node.module.split(".")[0])
                if node.module.startswith("abrasax") and len(node.module.split(".")) > 1:
                    out.add("abrasax." + node.module.split(".")[1])
            if node.level and node.module:
                out.add(node.module.split(".")[0])
    return out'''

NEW = '''def module_imports(path: str) -> set[str]:
    """Intra-package imports of one Python file, in BOTH forms.

    This package uses relative imports heavily -- measured 29 in cli.py alone:
        from . import llm
        from .llm import ask
    A relative import is ImportFrom(level=1, module=None, names=['llm']), which
    carries no "abrasax." prefix. The previous version kept only prefixed names, so
    every one of those edges vanished and all 33 modules looked like leaves.

    RELATIVE marks an edge as intra-package; the caller strips the prefix.
    """
    try:
        src = open(path, encoding="utf-8", errors="replace").read()
        tree = ast.parse(src)
    except (OSError, SyntaxError):
        return set()
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name.split(".")[0])
                if a.name.startswith("abrasax."):
                    parts = a.name.split(".")
                    if len(parts) > 1:
                        out.add("abrasax." + parts[1])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # from . import x        -> module is None, x is the target
                if node.module:
                    out.add("abrasax." + node.module.split(".")[0])
                for a in node.names:
                    if a.name != "*":
                        out.add("abrasax." + a.name.split(".")[0])
            elif node.module:
                out.add(node.module.split(".")[0])
                if node.module.startswith("abrasax") and len(node.module.split(".")) > 1:
                    out.add("abrasax." + node.module.split(".")[1])
    # never count a module importing itself
    here = "abrasax." + os.path.splitext(os.path.basename(path))[0]
    out.discard(here)
    return out'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: module_imports")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: relative imports now produce edges")
