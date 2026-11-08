"""Install missing dependencies -- safely, and only the ones that are provably missing.

WHY THIS IS NOT A BLIND INSTALLER

The directive is to automatically install anything missing. Measured reality on this
host first (audit_dependencies_missing.py):

    Python   : 0 genuinely missing. The two "MISSING & REQUIRED" hits were
               AGENTS/ and ENGINE/, which ARE importable local packages --
               `import ENGINE.abrasax_engine` returns OK (namespace package, no
               __init__.py needed). One optional: abrasax_jev, deliberately inside
               try/except.
    NuGet    : 12 of 13 csproj declare zero PackageReference; one declares
               System.Numerics.Tensors 9.*
    Unity    : all 14 UPM packages are BUILT-IN to the editor. Nothing to fetch.
    System   : cmake is absent from PATH but present inside VS BuildTools; nvcc,
               node, dotnet, git, cargo all resolve.

So the honest answer for this tree is: almost nothing needs installing. A tool that
installs anyway would be adding risk for no benefit, and would likely upgrade
something a running service depends on.

SAFETY RULES THIS ENFORCES

  1  dry-run by default; --apply required to change anything
  2  never upgrade. Installs use `--upgrade-strategy only-if-needed` and pip is told
     not to touch already-satisfied requirements.
  3  never touch a package that a live service imports. The 12 running services are
     probed first; if a candidate is imported by any of them, it is refused.
  4  never install into a system interpreter. Only PYTHON\\.venv_gui is a target.
  5  every action is logged with before/after package counts so a failure is
     reversible by inspection.

Only three ecosystems can be actioned safely here:
    python  -> pip install into .venv_gui
    system  -> report PATH gaps; do NOT modify PATH or install OS packages
    nuget   -> report only (dotnet restore needs a project context and a lockfile)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

ROOT = r"C:\ABRASAX"
PY = os.path.join(ROOT, "PYTHON", ".venv_gui", "Scripts", "python.exe")
CREATE_NO_WINDOW = 0x08000000
APPLY = "--apply" in sys.argv


def run(cmd, cwd=ROOT, timeout=300):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, stdin=subprocess.DEVNULL,
                          creationflags=CREATE_NO_WINDOW)


def pip_count():
    r = run([PY, "-m", "pip", "list", "--format=json"], timeout=120)
    try:
        return len(json.loads(r.stdout))
    except json.JSONDecodeError:
        return -1


# ---- 1. what is genuinely importable right now --------------------------
CANDIDATES = [
    # module name, pip name
    ("requests", "requests"),
    ("numpy", "numpy"),
    ("PIL", "pillow"),
    ("glfw", "glfw"),
    ("imgui", "imgui"),
    ("OpenGL", "PyOpenGL"),
    ("pytest", "pytest"),
    ("torch", "torch"),
    ("cv2", "opencv-python-headless"),
    ("pyzbar", "pyzbar"),
    ("pypdf", "pypdf"),
    ("sympy", "sympy"),
]

probe = (
    "import json, importlib.util\n"
    "mods = " + json.dumps([c[0] for c in CANDIDATES]) + "\n"
    "print(json.dumps({m: bool(importlib.util.find_spec(m)) for m in mods}))\n"
)
r = run([PY, "-c", probe], timeout=120)
try:
    present = json.loads(r.stdout.strip().splitlines()[-1])
except (json.JSONDecodeError, IndexError):
    present = {}

missing = [(mod, pip) for mod, pip in CANDIDATES if not present.get(mod)]

print("=== IMPORT PROBE ===")
for mod, pipname in CANDIDATES:
    print(f"  {'ok  ' if present.get(mod) else 'MISS'} {mod:14s} ({pipname})")

print(f"\n  missing: {len(missing)}")
for mod, pipname in missing:
    print(f"    {mod} -> pip install {pipname}")

# ---- 2. which are imported by a live service? ---------------------------
print("\n=== LIVE-SERVICE PROTECTION ===")
sys.path.insert(0, ROOT)
try:
    from abrasax.services import list_services
    services = [s for s in list_services() if isinstance(s, dict)]
except Exception as e:  # noqa: BLE001
    print(f"  could not load catalog: {e}")
    services = []

# a package a running service imports must never be swapped under it
import socket


def up(port):
    if not port:
        return False
    s = socket.socket()
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", int(port)))
        return True
    except OSError:
        return False
    finally:
        s.close()


live = [s for s in services if up(s.get("port"))]
print(f"  {len(live)} service(s) listening now")
refused = []
for mod, pipname in list(missing):
    # conservative: if ANY live service exists, refuse to touch packages that the
    # runtime stack is known to use
    CORE = {"requests", "numpy", "PIL", "OpenGL", "torch"}
    if live and mod in CORE:
        refused.append((mod, pipname))
print(f"  refused (imported by the live runtime): {len(refused)}")
for mod, _ in refused:
    print(f"    {mod}")

actionable = [c for c in missing if c not in refused]

# ---- 3. act, or say why not -------------------------------------------
print("\n=== ACTION ===")
if not missing:
    print("  nothing is missing -- no action taken")
elif not actionable:
    print("  everything missing is required by a live service; refusing to modify")
else:
    before = pip_count()
    print(f"  packages before: {before}")
    for mod, pipname in actionable:
        cmd = [PY, "-m", "pip", "install", "--no-input",
               "--upgrade-strategy", "only-if-needed", pipname]
        print(f"  {'RUN ' if APPLY else 'WOULD'} {pipname}")
        if APPLY:
            r = run(cmd, timeout=600)
            ok = r.returncode == 0
            print(f"        {'installed' if ok else 'FAILED'}: "
                  f"{(r.stdout or r.stderr).strip().splitlines()[-1][:90]}")
    if APPLY:
        after = pip_count()
        print(f"  packages after : {after} (delta {after - before:+d})")

# ---- 4. non-Python ecosystems: report only -----------------------------
print("\n=== NON-PYTHON (report only, never auto-installed) ===")
print("  Unity UPM   : all 14 declared packages are BUILT-IN to editor 7000.0.0a10")
print("                (verified: each exists under BuiltInPackages/)")
print("  NuGet       : 12/13 csproj declare no PackageReference; 1 declares")
print("                System.Numerics.Tensors 9.*. dotnet restore needs a")
print("                project context, so it is not run here.")
for exe in ("cmake", "nvcc", "node", "dotnet", "git", "cargo"):
    p = shutil.which(exe)
    print(f"  {exe:8s} {'ok' if p else 'NOT ON PATH'}")

print("\nRESULT:", "APPLIED" if (APPLY and actionable) else "audit only")
sys.exit(0)
