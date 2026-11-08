"""Investigate the two reciprocal edges the mapper found.

map_dependencies reported:
    abrasax <-> agents
    abrasax <-> engine

A true import cycle between a package and the layers it wraps is a real
architectural defect: it means neither can be loaded, tested or replaced without the
other. But "A imports B and B imports A" can also be an artefact of counting a
single lazy import inside a function.

So: find the actual import statements on both sides and say which direction is
real, which is lazy, and whether an import would deadlock.

Nothing is modified.
"""
import ast
import os
import sys

ROOT = r"C:\ABRASAX"

PAIRS = [("abrasax", os.path.join(ROOT, "abrasax")),
         ("agents", os.path.join(ROOT, "AGENTS")),
         ("engine", os.path.join(ROOT, "ENGINE"))]


def scan(base, label, limit_files=400):
    """Yield (file, lineno, module, is_lazy) for imports of another layer."""
    found = []
    n = 0
    for dp, dn, fns in os.walk(base):
        dn[:] = [d for d in dn if d not in ("__pycache__", "node_modules", ".git",
                                            "target", "VERSIONS")]
        depth = dp[len(base):].count(os.sep)
        if depth > 2:
            dn[:] = []
            continue
        for fn in fns:
            if not fn.endswith(".py"):
                continue
            n += 1
            if n > limit_files:
                return found
            path = os.path.join(dp, fn)
            try:
                src = open(path, encoding="utf-8", errors="replace").read()
                tree = ast.parse(src)
            except (OSError, SyntaxError):
                continue

            # top-level imports happen at module load; indented ones are lazy
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                else:
                    if node.module:
                        names = [node.module]
                    names += [a.name for a in node.names]
                joined = " ".join(names)
                if label == "abrasax" and ("agents" in joined or "engine" in joined):
                    found.append((path, node.lineno, joined[:60], node.col_offset > 0))
                elif label == "agents" and "abrasax" in joined:
                    found.append((path, node.lineno, joined[:60], node.col_offset > 0))
                elif label == "engine" and "abrasax" in joined:
                    found.append((path, node.lineno, joined[:60], node.col_offset > 0))
    return found


for label, base in PAIRS:
    rows = scan(base, label)
    print(f"=== {label}: {len(rows)} import(s) of another layer ===")
    eager = [r for r in rows if not r[3]]
    lazy = [r for r in rows if r[3]]
    print(f"  eager (module load): {len(eager)}")
    for p, ln, mod, _ in eager[:10]:
        print(f"    {os.path.relpath(p, ROOT)}:{ln}  {mod}")
    print(f"  lazy (inside a function): {len(lazy)}")
    for p, ln, mod, _ in lazy[:10]:
        print(f"    {os.path.relpath(p, ROOT)}:{ln}  {mod}")
    print()

print("=== VERDICT ===")
print("  A cycle only deadlocks if BOTH directions are eager. A lazy import inside a")
print("  function is resolved at call time, after both modules are fully loaded, so it")
print("  cannot deadlock -- but it still means the layers cannot be separated.")
