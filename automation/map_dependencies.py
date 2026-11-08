"""Map every layer, dependency and connection by MEASUREMENT, not by reading docs.

DOC/ARCHITECTURE.md already contains an unusually honest verdict:

    "ABRASAX is three systems that share a directory tree and do not call each
     other... a local LLM gateway with an unusually elaborate set of unused
     generators and a JSON-based identity ledger."

That was written 2026-10-17. Tonight added a GPU renderer, an ImGui overlay, a
string-brain daemon, a Unity build and a memory governor -- so the map must be
re-derived, not re-quoted.

This builds the real dependency graph:
  1  every module in abrasax/ and its intra-package imports
  2  which layers actually CALL each other (an edge exists only if an import does)
  3  which services are running and what each depends on at runtime
  4  the call edges that DO NOT exist -- the honest gaps

Output is a machine-readable graph plus a human summary.

Read-only, bounded, no network.
"""
from __future__ import annotations

import ast
import json
import os
import socket
import subprocess
import sys
from collections import defaultdict

ROOT = r"C:\ABRASAX"
PKG = os.path.join(ROOT, "abrasax")
OUT = os.path.join(ROOT, "LOGS", "dependency-graph.json")

LAYERS = {
    "abrasax": os.path.join(ROOT, "abrasax"),
    "agents": os.path.join(ROOT, "AGENTS"),
    "engine": os.path.join(ROOT, "ENGINE"),
    "scripts": os.path.join(ROOT, "SCRIPTS", "automation"),
}


def module_imports(path: str) -> set[str]:
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
    return out


print("=== 1. PACKAGE INTERNALS: abrasax/ ===")
graph = {}
mods = sorted(f[:-3] for f in os.listdir(PKG)
              if f.endswith(".py") and not f.startswith("__"))
inbound = defaultdict(set)

for m in mods:
    imports = module_imports(os.path.join(PKG, m + ".py"))
    intra = {i for i in imports if i.startswith("abrasax.")}
    deps = sorted(x.split(".", 1)[1] for x in intra if "." in x)
    graph[m] = {"imports": deps}
    for d in deps:
        inbound[d].add(m)

print(f"  {len(mods)} modules")
print(f"\n  {'module':22s} {'imports':40s} imported-by")
for m in mods:
    deps = graph[m]["imports"]
    who = sorted(inbound.get(m, []))
    print(f"  {m:22s} {','.join(deps)[:40]:40s} {len(who)}")

leaf = [m for m in mods if not graph[m]["imports"]]
orphan = [m for m in mods if not inbound.get(m)]
print(f"\n  leaf modules (import nothing in-package): {len(leaf)}")
print(f"    {', '.join(leaf)}")
print(f"  modules imported by NOTHING: {len(orphan)}")
print(f"    {', '.join(orphan)}")

# ---- 2. cross-layer edges ----------------------------------------------
print("\n=== 2. CROSS-LAYER EDGES (does layer A import layer B?) ===")
edges = defaultdict(int)
layer_files = defaultdict(list)
for layer, base in LAYERS.items():
    if not os.path.isdir(base):
        continue
    for dp, dn, fns in os.walk(base):
        dn[:] = [d for d in dn if d not in ("__pycache__", "node_modules", ".git",
                                            "VERSIONS", "target")]
        depth = dp[len(base):].count(os.sep)
        if depth > 3:
            dn[:] = []
            continue
        for fn in fns:
            if fn.endswith(".py"):
                layer_files[layer].append(os.path.join(dp, fn))

for layer, files in layer_files.items():
    for f in files:
        imps = module_imports(f)
        for other in LAYERS:
            if other == layer:
                continue
            token = other if other != "scripts" else "automation"
            if any(token in i or i in ("abrasax", "agents", "engine") and
                   other == i for i in imps):
                edges[(layer, other)] += 1

print(f"  {'from':10s} {'to':10s} edges")
for (a, b), n in sorted(edges.items()):
    print(f"  {a:10s} {b:10s} {n}")

print("\n  reciprocal? (A->B and B->A)")
for (a, b) in list(edges):
    if (b, a) in edges:
        print(f"    {a} <-> {b}")

# ---- 3. runtime services and their dependencies -------------------------
print("\n=== 3. RUNTIME: what is listening, and what does it need? ===")


def tcp(port):
    s = socket.socket()
    s.settimeout(0.6)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


sys.path.insert(0, ROOT)
try:
    from abrasax.services import list_services
    svc = list_services()
except Exception as e:  # noqa: BLE001
    print(f"  catalog load failed: {e}")
    svc = []

for s in svc:
    if not isinstance(s, dict):
        continue
    port = s.get("port")
    up = tcp(port) if port else None
    state = "UP" if up else ("DOWN" if port else "n/a")
    print(f"  {s.get('id', '?'):22s} :{str(port or '-'):6s} {state:5s} "
          f"{(s.get('entry') or '')[:44]}")

# ---- 4. the honest gaps ------------------------------------------------
print("\n=== 4. THE GAPS (edges that do not exist) ===")
print(f"  modules nobody imports: {len(orphan)} of {len(mods)}")
if orphan:
    for m in orphan:
        print(f"    {m}  -- reachable only from the CLI or by hand")

payload = {
    "modules": graph,
    "inbound": {k: sorted(v) for k, v in inbound.items()},
    "leaf": leaf,
    "orphan": orphan,
    "cross_layer": {f"{a}->{b}": n for (a, b), n in edges.items()},
    "layer_file_counts": {k: len(v) for k, v in layer_files.items()},
}
try:
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"\nwrote {OUT} ({os.path.getsize(OUT):,} bytes)")
except OSError as e:
    print(f"could not write graph: {e}")

sys.exit(0)
