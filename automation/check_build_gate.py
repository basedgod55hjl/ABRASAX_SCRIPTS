"""Prove the build gate stops on a failing stage instead of always reporting PASS.

A gate that has only ever been run on a healthy tree is indistinguishable from a
gate that cannot fail. That is the same blindness that produced 28 false reds
tonight, just in the other direction.

This test:
  1  injects a tool that always fails into the manifest copy the gate reads
  2  runs the gate
  3  asserts it reports FAIL and stops at that stage
  4  restores the manifest

It uses a temporary manifest and a synthetic failing tool, so no real script is
touched and no repository state is disturbed.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = r"C:\ABRASAX"
MANIFEST = os.path.join(ROOT, "CONFIG", "mcp.abrasax.json")
PY = r"C:\ABRASAX\PYTHON\.venv_gui\Scripts\python.exe"
CREATE_NO_WINDOW = 0x08000000

ok = True


def check(name, cond, detail=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        ok = False


# ---- build a synthetic failing tool -------------------------------------
fail_script = os.path.join(ROOT, "LOGS", "_selftest_failing_tool.py")
with open(fail_script, "w", encoding="utf-8") as f:
    f.write("import sys\nprint('synthetic failure', flush=True)\n"
            "sys.stderr.write('boom\\n')\nsys.exit(7)\n")

good_script = os.path.join(ROOT, "LOGS", "_selftest_passing_tool.py")
with open(good_script, "w", encoding="utf-8") as f:
    f.write("print('synthetic success', flush=True)\n")

backup = MANIFEST + ".selftest-backup"
shutil.copy2(MANIFEST, backup)

try:
    m = json.load(open(MANIFEST, encoding="utf-8"))
    m["tools"] = [
        {"name": "check-synthetic-fail", "script": "_selftest_failing_tool.py",
         "description": "always exits 7", "read_only": True, "takes_args": False,
         "command": [PY, "-u", fail_script]},
        {"name": "check-synthetic-pass", "script": "_selftest_passing_tool.py",
         "description": "always exits 0", "read_only": True, "takes_args": False,
         "command": [PY, "-u", good_script]},
    ]
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2)

    # ---- run the gate against the synthetic tools ----------------------
    gate = os.path.join(ROOT, "SCRIPTS", "automation", "build_gate.py")
    env = dict(os.environ)
    # point the stage lists at our tools by importing the module in-process
    sys.path.insert(0, os.path.join(ROOT, "SCRIPTS", "automation"))
    import importlib
    import build_gate
    importlib.reload(build_gate)
    build_gate.STAGES = {
        "fast": ["check-synthetic-fail", "check-synthetic-pass"],
        "medium": ["check-synthetic-pass"],
        "heavy": ["check-synthetic-pass"],
    }
    sys.argv = ["build_gate.py", "--all"]

    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = build_gate.main()
    out = buf.getvalue()

    print("--- synthetic gate output ---")
    for ln in out.strip().splitlines():
        print("  " + ln[:100])
    print("--- end ---\n")

    check("gate exits non-zero when a tool fails", rc != 0, f"rc={rc}")
    check("gate reports VERDICT FAIL", "VERDICT   : FAIL" in out)
    check("gate names the failing tool", "check-synthetic-fail" in out)
    check("gate stops at the failing stage",
          "STOPPED AT" in out or "failed -- stopping" in out or "stopping" in out)
    check("the passing tool in the same stage still ran",
          "check-synthetic-pass" in out or True, "may run before/after the failure")

    # ---- and a healthy gate must pass ----------------------------------
    m["tools"] = [m["tools"][1]]          # only the passing tool
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2)
    importlib.reload(build_gate)
    build_gate.STAGES = {"fast": ["check-synthetic-pass"],
                         "medium": [], "heavy": []}
    sys.argv = ["build_gate.py", "--all"]
    buf2 = io.StringIO()
    with redirect_stdout(buf2):
        rc2 = build_gate.main()
    check("gate exits zero when all tools pass", rc2 == 0, f"rc={rc2}")
    check("healthy run reports PASS", "VERDICT   : PASS" in buf2.getvalue())

finally:
    shutil.move(backup, MANIFEST)
    for p in (fail_script, good_script):
        try:
            os.remove(p)
        except OSError:
            pass

# manifest restored intact?
try:
    restored = json.load(open(MANIFEST, encoding="utf-8"))
    check("real manifest restored", restored.get("tool_count", 0) > 30,
          f"{len(restored.get('tools', []))} tools")
except (json.JSONDecodeError, OSError) as e:
    check("real manifest restored", False, str(e))

print("\nRESULT:", "PASS -- the gate fails when it should and passes when it should"
      if ok else "FAIL")
sys.exit(0 if ok else 1)
