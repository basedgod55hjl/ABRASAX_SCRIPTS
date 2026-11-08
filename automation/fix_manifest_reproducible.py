"""Make the tool manifest reproducible for anyone who clones this repo.

MEASURED PROBLEM: CONFIG/mcp.abrasax.json was committed-to but ignored.

    git check-ignore -v CONFIG/mcp.abrasax.json
    .gitignore:94:/CONFIG/	CONFIG/mcp.abrasax.json
    git ls-files CONFIG/mcp.abrasax.json  -> 0

The generator (register_mcp_tools.py) is tracked; its output is not. So a fresh
clone has the recipe but not the manifest, and build_gate.py would fail with
"manifest missing".

Two legitimate options:
  a  commit the manifest anyway with `git add -f` -- simple, but /CONFIG/ is
     ignored for a reason (it holds tool config that may carry secrets)
  b  treat the manifest as a BUILD ARTIFACT: generate it on demand, and make every
     consumer generate it if absent

(b) is correct. The manifest contains no secrets -- it is a list of script names and
paths -- but keeping generated artifacts out of git is the stronger default, and it
means the manifest can never drift from the scripts it describes.

This adds the generation step to the runner and gate so neither can be caught
without it.
"""
import sys

# ---- 1. mcp_runner: generate on demand ----------------------------------
RUNNER = r"C:\ABRASAX\SCRIPTS\automation\mcp_runner.py"
src = open(RUNNER, encoding="utf-8").read()

if "_ensure_manifest" in src:
    print("runner ALREADY-PATCHED")
else:
    OLD = '''def load():
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)'''
    NEW = '''def _ensure_manifest():
    """Generate the manifest if it is absent.

    CONFIG/ is gitignored, so the manifest is a build artifact, not source. Every
    consumer regenerates it rather than assuming a previous run left it behind.
    """
    if os.path.exists(MANIFEST):
        return
    gen = r"C:\\ABRASAX\\SCRIPTS\\automation\\register_mcp_tools.py"
    subprocess.run([sys.executable, "-u", gen], cwd=ROOT,
                   capture_output=True, text=True, timeout=120,
                   stdin=subprocess.DEVNULL,
                   creationflags=CREATE_NO_WINDOW)


def load():
    _ensure_manifest()
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)'''
    if OLD not in src:
        print("runner ANCHOR-NOT-FOUND")
        sys.exit(1)
    src = src.replace(OLD, NEW, 1)
    open(RUNNER, "w", encoding="utf-8", newline="").write(src)
    print("runner: generates the manifest when absent")

# ---- 2. build_gate already calls R.load(), which now ensures it ---------
GATE = r"C:\ABRASAX\SCRIPTS\automation\build_gate.py"
gsrc = open(GATE, encoding="utf-8").read()
if "R.load()" in gsrc:
    print("gate: already goes through R.load(), so it inherits the fix")
else:
    print("gate: WARNING -- does not use R.load(); check manually")

# ---- 3. prove it: delete the manifest, call load(), expect regeneration -
import json
import os
import subprocess
import time

MANIFEST = r"C:\ABRASAX\CONFIG\mcp.abrasax.json"
if os.path.exists(MANIFEST):
    backup = MANIFEST + ".verify-backup"
    os.replace(MANIFEST, backup)
    try:
        sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")
        import importlib
        import mcp_runner
        importlib.reload(mcp_runner)
        t0 = time.time()
        m = mcp_runner.load()
        dt = time.time() - t0
        n = len(m.get("tools", []))
        print(f"\nregenerated on demand: {n} tool(s) in {dt:.1f}s")
        print("RESULT:", "PASS -- manifest is reproducible without git"
              if n > 30 else "FAIL")
    finally:
        if os.path.exists(MANIFEST):
            os.remove(MANIFEST)
        os.replace(backup, MANIFEST)
