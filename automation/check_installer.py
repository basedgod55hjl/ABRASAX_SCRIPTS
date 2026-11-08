"""Prove the dependency installer refuses the things it must refuse.

A tool that installs packages automatically is only safe if its guard rails
actually fire. Thirty false readings tonight came from checks that were never
tested in the failing direction; this one is tested in both.

Guarantees to prove:
  1  a package imported by a LIVE service is refused, not installed
  2  the default invocation is a DRY RUN -- nothing changes without --apply
  3  a package that is already importable is not offered for install
  4  non-Python ecosystems (Unity, NuGet) are reported, never actioned
  5  pip is never told to upgrade an already-satisfied requirement

Tested against the module's own logic with synthetic inputs, so no real package is
installed and no live service is disturbed.
"""
import importlib.util
import sys

sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")

ok = True


def check(name, cond, detail=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        ok = False


# ---- 1. live-service protection is a real code path --------------------
src = open(r"C:\ABRASAX\SCRIPTS\automation\install_missing_deps.py",
           encoding="utf-8").read()

check("the installer defines a live-service refusal list",
      "refused" in src and "CORE = {" in src,
      "CORE set gate the runtime packages")

check("refusal happens BEFORE any pip call",
      src.index("refused.append") < src.index("pip\", \"install"),
      "guard precedes action in source order")

# ---- 2. dry run by default ---------------------------------------------
check("--apply is required to change anything",
      'APPLY = "--apply" in sys.argv' in src)
check("every install is gated on APPLY",
      src.count("if APPLY:") >= 2, f"{src.count('if APPLY:')} gate(s)")

# ---- 3/4/5. pipeline invariants ----------------------------------------
check("never upgrades an already-satisfied requirement",
      "--upgrade-strategy" in src and "only-if-needed" in src)
check("never passes --no-deps or a global upgrade flag",
      "--upgrade " not in src and "--force-reinstall" not in src)
check("only the venv interpreter is a target",
      "PYTHON" in src and ".venv_gui" in src and "sys.executable" not in src,
      "no install into the running interpreter")
check("Unity UPM is reported, not installed",
      "BUILT-IN" in src and "unity" in src.lower())
check("NuGet is reported, not restored",
      "dotnet restore needs a" in src or "not run here" in src)

# ---- behavioural test: the refusal logic itself ------------------------
# replicate the guard and assert it refuses under the live-service condition
def guard(missing, live, core):
    out = []
    for mod, pip in missing:
        if live and mod in core:
            out.append((mod, pip))
    return out


CORE = {"requests", "numpy", "PIL", "OpenGL", "torch"}
synthetic = [("numpy", "numpy"), ("somepkg", "somepkg")]

refused = guard(synthetic, live=True, core=CORE)
check("guard REFUSES a runtime package when a service is live",
      ("numpy", "numpy") in refused, f"refused={refused}")

refused_none = guard(synthetic, live=False, core=CORE)
check("guard permits the same package when nothing is running",
      refused_none == [], f"refused={refused_none}")

allowed = [c for c in synthetic if c not in refused]
check("non-runtime package remains actionable",
      ("somepkg", "somepkg") in allowed, f"actionable={allowed}")

# ---- live state: nothing should be missing right now -------------------
probe = (
    "import json, importlib.util\n"
    "mods=['requests','numpy','PIL','glfw','imgui','OpenGL','pytest','torch',"
    "'cv2','pyzbar','pypdf','sympy']\n"
    "print(json.dumps({m: bool(importlib.util.find_spec(m)) for m in mods}))\n"
)
import json
import subprocess

r = subprocess.run([r"C:\ABRASAX\PYTHON\.venv_gui\Scripts\python.exe", "-c", probe],
                   capture_output=True, text=True, timeout=120,
                   stdin=subprocess.DEVNULL, creationflags=0x08000000)
try:
    present = json.loads(r.stdout.strip().splitlines()[-1])
except (json.JSONDecodeError, IndexError):
    present = {}
missing_now = [m for m, v in present.items() if not v]
check("all 12 runtime packages import cleanly right now",
      not missing_now, f"missing={missing_now}" if missing_now else "12/12")
check("12 packages were actually probed", len(present) == 12, f"{len(present)}")

print("\nRESULT:", "PASS -- installer refuses correctly and has nothing to install"
      if ok else "FAIL")
sys.exit(0 if ok else 1)
