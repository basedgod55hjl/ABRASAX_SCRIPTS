"""Find out why the dependency mapper saw zero imports across 33 modules.

It reported every module as "leaf" and "imported by nothing", which contradicts
what the code obviously does -- e.g. abrasax/selfedit.py has

    from . import llm

inside a function, and abrasax/cli.py imports half the package lazily.

The mapper used ast.walk over Import/ImportFrom, which SHOULD catch both. So one of
these is true:
  a  the files were not actually parsed (silent AST failure)
  b  the relative-import form is not being recognised
  c  the filter that keeps only "abrasax." prefixed names is discarding everything

Test all three directly against real files.
"""
import ast
import os
import sys

ROOT = r"C:\ABRASAX"
PKG = os.path.join(ROOT, "abrasax")

FILES = ["cli.py", "gateway.py", "memory.py", "selfedit.py", "services.py"]

for fn in FILES:
    path = os.path.join(PKG, fn)
    try:
        src = open(path, encoding="utf-8", errors="replace").read()
    except OSError as e:
        print(f"{fn}: cannot read {e}")
        continue

    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        print(f"{fn}: SYNTAX ERROR {e}")
        continue

    plain, relative = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                plain.append(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # relative import: from . import x   /  from .mod import y
                mods = [a.name for a in node.names]
                relative.append(f"level={node.level} module={node.module} names={mods}")
            elif node.module:
                plain.append(node.module)

    print(f"=== {fn} ===")
    print(f"  absolute imports : {len(plain)}")
    for p in plain[:6]:
        print(f"      {p}")
    print(f"  RELATIVE imports : {len(relative)}")
    for r in relative[:8]:
        print(f"      {r}")
    print()

print("CONCLUSION:")
print("  If relative imports exist but the mapper reported none, the bug is in the")
print("  filter: the mapper kept only names starting with 'abrasax.', and a relative")
print("  import like `from . import llm` produces module=None with level=1 -- there is")
print("  no 'abrasax.' prefix to match, so every edge was dropped.")
