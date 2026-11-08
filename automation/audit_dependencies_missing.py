"""Audit what is actually missing before installing anything.

"Automatically install any missing packages" is the most dangerous instruction in
this sequence. An installer that runs unbidden can replace a working interpreter,
upgrade a dependency out from under a running service, or pull a package that
shadows a local module.

So: measure first, install nothing yet, and separate three very different cases:

  A  MISSING AND REQUIRED    code imports it, it is not installed
  B  MISSING AND OPTIONAL    code imports it inside try/except -- by design
  C  DECLARED BUT WRONG      a manifest names something that does not exist

Only A is a defect. B is intentional. C needs a human decision, not an installer.

Covers four ecosystems measured on this host:
    python  .venv_gui (34 packages)
    dotnet  csproj files
    unity   J:/UnityProjects/ABRASAX-Brain/Packages/manifest.json
    system  executables the scripts call
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = r"C:\ABRASAX"
PY = os.path.join(ROOT, "PYTHON", ".venv_gui", "Scripts", "python.exe")
CREATE_NO_WINDOW = 0x08000000

STDLIB = set(sys.stdlib_module_names)

CODE_DIRS = [os.path.join(ROOT, "abrasax"),
             os.path.join(ROOT, "SCRIPTS", "automation"),
             os.path.join(ROOT, "ENGINE", "floating_brain"),
             os.path.join(ROOT, "TESTS", "python")]

print("=== A. PYTHON IMPORTS: required vs optional ===")


def scan_imports():
    required, optional = {}, {}
    for base in CODE_DIRS:
        if not os.path.isdir(base):
            continue
        for dp, dn, fns in os.walk(base):
            dn[:] = [d for d in dn if d != "__pycache__"]
            for fn in fns:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(dp, fn)
                try:
                    tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    mods = []
                    if isinstance(node, ast.Import):
                        mods = [a.name.split(".")[0] for a in node.names]
                    elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                        mods = [node.module.split(".")[0]]
                    for m in mods:
                        if m in STDLIB or m.startswith("_"):
                            continue
                        # try/except detection: walk ancestors is not available here,
                        # so use line-based heuristic on the enclosing block
                        try:
                            line = open(path, encoding="utf-8",
                                        errors="replace").read().splitlines()
                            ctx = "\n".join(line[max(0, node.lineno - 6):node.lineno])
                            lazy = "try:" in ctx
                        except OSError:
                            lazy = False
                        (optional if lazy else required).setdefault(m, set()).add(fn)
    return required, optional


required, optional = scan_imports()
r = subprocess.run([PY, "-m", "pip", "list", "--format=json"],
                   capture_output=True, text=True, timeout=120,
                   stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
installed = set()
try:
    for p in json.loads(r.stdout):
        installed.add(p["name"].lower().replace("-", "_"))
except json.JSONDecodeError:
    pass

# map module name -> pip name where they differ
ALIAS = {"pil": "pillow", "cv2": "opencv_python_headless", "yaml": "pyyaml",
         "opengl": "pyopengl", "dateutil": "python_dateutil",
         "bs4": "beautifulsoup4", "sklearn": "scikit_learn"}

first_party = {"abrasax", "agents", "engine", "imgui_overlay", "string_brain",
               "conftest", "glfw_hint", "mcp_runner", "build_gate", "winproc",
               "unity_proc", "mem_governor", "abra_paths", "secret_rules",
               "mem_monitor"}

missing_required, missing_optional = [], []
for mod, files in sorted(required.items()):
    if mod in first_party:
        continue
    pipname = ALIAS.get(mod, mod)
    if pipname in installed or mod in installed:
        continue
    try:
        import importlib.util
        if importlib.util.find_spec(mod):
            continue
    except (ImportError, ValueError, ModuleNotFoundError):
        pass
    missing_required.append((mod, sorted(files)[:2]))

for mod, files in sorted(optional.items()):
    if mod in required or mod in first_party:
        continue
    pipname = ALIAS.get(mod, mod)
    if pipname in installed:
        continue
    try:
        import importlib.util
        if importlib.util.find_spec(mod):
            continue
    except (ImportError, ValueError, ModuleNotFoundError):
        pass
    missing_optional.append((mod, sorted(files)[:2]))

print(f"  required imports    : {len(required)}")
print(f"  optional imports    : {len(optional)}")
print(f"  MISSING & REQUIRED  : {len(missing_required)}")
for m, f in missing_required:
    print(f"      {m:22s} used by {f[0] if f else '?'}")
print(f"  MISSING & OPTIONAL  : {len(missing_optional)}")
for m, f in missing_optional:
    print(f"      {m:22s} (try/except) {f[0] if f else '?'}")

print("\n=== B. DECLARED PYTHON DEPS ===")
pyp = open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8").read()
declared = re.findall(r'"([a-zA-Z0-9_.-]+)\s*([<>=!~].*)?"', pyp)
for name, spec in declared[:10]:
    ok = name.lower().replace("-", "_") in installed
    print(f"  {name:28s} {spec or '(any)':14s} {'installed' if ok else 'MISSING'}")

print("\n=== C. NUGET (csproj files) ===")
csprojs = []
for base in (os.path.join(ROOT, "SOURCE"), os.path.join(ROOT, "PROJECTS"),
             os.path.join(ROOT, "TOOLS"), os.path.join(ROOT, "AGENTS")):
    if not os.path.isdir(base):
        continue
    for dp, dn, fns in os.walk(base):
        dn[:] = [d for d in dn if d not in ("node_modules", "bin", "obj", "__pycache__")]
        depth = dp[len(base):].count(os.sep)
        if depth > 4:
            dn[:] = []
            continue
        for fn in fns:
            if fn.endswith(".csproj"):
                csprojs.append(os.path.join(dp, fn))

print(f"  {len(csprojs)} .csproj found")
for p in csprojs[:6]:
    txt = open(p, encoding="utf-8", errors="replace").read()
    pkgs = re.findall(r'PackageReference\s+Include="([^"]+)"(?:\s+Version="([^"]+)")?', txt)
    print(f"    {os.path.relpath(p, ROOT)}: {len(pkgs)} package(s)")
    for name, ver in pkgs[:4]:
        print(f"        {name} {ver or '(no version)'}")

print("\n=== D. UNITY UPM ===")
mf = r"J:\UnityProjects\ABRASAX-Brain\Packages\manifest.json"
if os.path.exists(mf):
    m = json.load(open(mf, encoding="utf-8"))
    deps = m.get("dependencies", {})
    builtin = r"J:\Unity\7000.0.0a10\Editor\Data\Resources\PackageManager\BuiltInPackages"
    print(f"  {len(deps)} declared")
    for name, ver in deps.items():
        d = os.path.join(builtin, name)
        local = os.path.isdir(d)
        print(f"    {name:44s} {ver:10s} {'builtin' if local else 'REGISTRY'}")
else:
    print("  manifest not found")

print("\n=== E. SYSTEM EXECUTABLES ===")
for exe in ("node", "npx", "dotnet", "git", "cmake", "nvcc", "cargo"):
    p = shutil.which(exe)
    print(f"  {exe:8s} {'-> ' + p if p else 'NOT ON PATH'}")

print("\nRESULT: audit only, nothing installed")
sys.exit(0)
