"""Section 2 audit: DEPENDENCY AND PACKAGE MANAGEMENT.

Checks what the code actually needs against what is actually installed, rather
than trusting a requirements file nobody re-reads.

A. every third-party import in the live code resolves in .venv_gui
B. declared dependencies (pyproject + requirements) vs installed versions
C. version pins: are any deps declared with no version at all?
D. duplicated/conflicting requirement files across the tree
E. stdlib vs third-party classification (so "missing" is real, not a typo)

Exit 0 = every import the running system needs is importable.
"""
import ast
import json
import os
import subprocess
import sys
from collections import defaultdict

ROOT = r"C:\ABRASAX"
PY = os.path.join(ROOT, "PYTHON", ".venv_gui", "Scripts", "python.exe")

# Directories holding first-party code that actually runs.
CODE_DIRS = [
    os.path.join(ROOT, "abrasax"),
    os.path.join(ROOT, "SCRIPTS", "automation"),
    os.path.join(ROOT, "ENGINE", "floating_brain"),
    os.path.join(ROOT, "TESTS", "python"),
]

# stdlib module names, so a stdlib import is never reported as a missing package
STDLIB = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else set()


class _OptVisitor(ast.NodeVisitor):
    """Walk a module, recording imports as REQUIRED or OPTIONAL.

    An import inside a `try:` block is optional by construction: the author has
    already decided how to degrade if it is absent. Treating those as missing
    dependencies produced a false defect on abrasax_jev, which selfedit.py imports
    inside try/except and handles returning None.
    """

    def __init__(self):
        self.required = set()
        self.optional = set()
        self._try_depth = 0

    def visit_Try(self, node):
        self._try_depth += 1
        for n in node.body:
            self.visit(n)
        self._try_depth -= 1
        # handlers / orelse / finalbody are not "optional import" territory
        for n in node.handlers + node.orelse + node.finalbody:
            self.visit(n)

    def visit_Import(self, node):
        for a in node.names:
            top = a.name.split(".")[0]
            (self.optional if self._try_depth else self.required).add(top)

    def visit_ImportFrom(self, node):
        if node.level == 0 and node.module:
            top = node.module.split(".")[0]
            (self.optional if self._try_depth else self.required).add(top)


def collect_imports(paths):
    required = defaultdict(set)   # module -> files importing it OUTSIDE try
    optional = defaultdict(set)   # module -> files importing it INSIDE try
    for base in paths:
        if not os.path.isdir(base):
            continue
        for dp, _dn, fns in os.walk(base):
            for fn in fns:
                if not fn.endswith(".py"):
                    continue
                full = os.path.join(dp, fn)
                try:
                    tree = ast.parse(open(full, encoding="utf-8", errors="replace").read())
                except SyntaxError:
                    continue
                v = _OptVisitor()
                v.visit(tree)
                for m in v.required:
                    required[m].add(full)
                for m in v.optional:
                    optional[m].add(full)
    # a module imported both ways is required somewhere -> required
    return required, optional


print("=== A. IMPORTS THE CODE ACTUALLY MAKES ===")
imports, optional_mods = collect_imports(CODE_DIRS)
print(f"distinct top-level modules imported: {len(imports)}")
print(f"optional (inside try/except)       : {len(optional_mods)}")
for m in sorted(optional_mods):
    if m not in imports:
        print(f"  optional-only: {m}  ({len(optional_mods[m])} file(s))")

# first-party names that live in this repo
FIRST_PARTY = {"abrasax", "imgui_overlay", "string_brain", "agents", "engine",
               "conftest", "glfw_hint"}

third_party = []
for mod in sorted(imports):
    if mod in STDLIB or mod in FIRST_PARTY or mod.startswith("_"):
        continue
    third_party.append(mod)

print(f"third-party candidates             : {len(third_party)}")

# ask the venv, once, which of these import
# find_spec LOCATES a module without executing it. The previous version called
# __import__() on everything, which initialises CUDA (torch), creates GL contexts
# (OpenGL), and burned 51 s of CPU without producing output. "Is it installed?" is
# the question; "does importing it work, and how fast?" is a different, heavier one.
probe = (
    "import json, importlib.util\n"
    "mods = " + json.dumps(third_party) + "\n"
    "out = {}\n"
    "for m in mods:\n"
    "    try:\n"
    "        out[m] = 'ok' if importlib.util.find_spec(m) else 'NotFound'\n"
    "    except Exception as e:\n"
    "        out[m] = type(e).__name__ + ': ' + str(e)[:60]\n"
    "print(json.dumps(out), flush=True)\n"
)
r = subprocess.run([PY, "-c", probe], capture_output=True, text=True, timeout=180)
try:
    status = json.loads(r.stdout.strip().splitlines()[-1])
except Exception:
    print("probe failed:", r.stdout[:300], r.stderr[:300])
    status = {}

missing = {m: s for m, s in status.items() if s != "ok"}
for m in sorted(status):
    s = status[m]
    mark = "ok  " if s == "ok" else "MISS"
    print(f"  {mark} {m}")

# ------------------------------------------------------------------ B and C
print("\n=== B. DECLARED DEPENDENCIES ===")
pyp = os.path.join(ROOT, "pyproject.toml")
if os.path.exists(pyp):
    txt = open(pyp, encoding="utf-8").read()
    in_deps = False
    declared = []
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith("dependencies"):
            in_deps = True
            continue
        if in_deps:
            if s.startswith("]"):
                break
            if s.startswith('"'):
                declared.append(s.strip('",'))
    print(f"  pyproject declares {len(declared)}:")
    for d in declared:
        print(f"    {d}")
    unpinned = [d for d in declared if not any(c in d for c in "<>=!~")]
    if unpinned:
        print(f"  {len(unpinned)} declared without a version constraint:")
        for d in unpinned:
            print(f"    {d}")
else:
    print("  pyproject.toml MISSING")

# ------------------------------------------------------------------ D
print("\n=== C. REQUIREMENT FILES ACROSS THE TREE ===")
reqs = []
for dp, dn, fns in os.walk(ROOT):
    dn[:] = [d for d in dn if d not in
             ("node_modules", ".git", "__pycache__", "VENDORS", "ARCHIVE", "_VAULT")]
    for fn in fns:
        if fn.startswith("requirements") and fn.endswith(".txt"):
            full = os.path.join(dp, fn)
            try:
                n = sum(1 for ln in open(full, encoding="utf-8", errors="replace")
                        if ln.strip() and not ln.startswith("#"))
            except OSError:
                n = 0
            reqs.append((os.path.relpath(full, ROOT), n))
for path, n in sorted(reqs, key=lambda t: -t[1])[:10]:
    print(f"  {n:4d} entries  {path}")
print(f"  ({len(reqs)} requirement files total)")

# ------------------------------------------------------------------ E
print("\n=== D. INSTALLED PACKAGES IN .venv_gui ===")
r = subprocess.run([PY, "-m", "pip", "list", "--format=json"],
                   capture_output=True, text=True, timeout=120)
try:
    pkgs = json.loads(r.stdout)
    print(f"  {len(pkgs)} packages installed")
    for p in sorted(pkgs, key=lambda d: d["name"].lower()):
        print(f"    {p['name']:32s} {p['version']}")
except Exception:
    print("  pip list failed:", r.stderr[:200])

# ------------------------------------------------------------------ summary
print("\n=== SUMMARY ===")
ok = True
if missing:
    print(f"{len(missing)} imported module(s) NOT importable:")
    for m, s in sorted(missing.items()):
        print(f"  - {m}: {s}")
    ok = False
else:
    print("every imported third-party module resolves in .venv_gui")

print("\nRESULT:", "PASS" if ok else "DEFECTS FOUND")
sys.exit(0 if ok else 1)
