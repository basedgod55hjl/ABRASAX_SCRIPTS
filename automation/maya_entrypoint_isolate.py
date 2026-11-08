"""Isolate where the child's stdout goes.

Runs the exact child command three ways:
  A. directly                    -> does the child print at all?
  B. through entrypoint.py       -> is the entrypoint responsible?
  C. through a 1-line wrapper    -> is it the nested python-inside-python?
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\ABRASAX\TYPESCRIPT\maya")
ENTRY = ROOT / "docker" / "entrypoint.py"
PY = sys.executable

child = ("import json, os, sys;"
         "print(json.dumps({'name': 'HF_TOKEN',"
         " 'matched': os.environ.get('HF_TOKEN') == 'direct',"
         " 'file_var': 'HF_TOKEN_FILE' in os.environ}))")

env = {"HF_TOKEN": "direct", "PATH": os.environ.get("PATH", ""),
       "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}

cases = {
    "A direct":            [PY, "-c", child],
    "B via entrypoint":    [PY, str(ENTRY), PY, "-c", child],
}
for label, cmd in cases.items():
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
    print(f"{label:22} rc={r.returncode} stdout={r.stdout!r} stderr={r.stderr[:160]!r}")

# C: does this interpreter honour -c at all under capture?
r = subprocess.run([PY, "-c", "import sys;print('HELLO')"],
                   capture_output=True, text=True)
print("C direct -c            rc=", r.returncode, "stdout=", repr(r.stdout))

# D: full env, not minimal
r = subprocess.run([PY, str(ENTRY), PY, "-c", child],
                   env={**os.environ, "HF_TOKEN": "direct"},
                   capture_output=True, text=True, check=False)
print("D full env             rc=", r.returncode, "stdout=", repr(r.stdout[:200]))

# E: what does the child see as its argv when run through the entrypoint?
probe = "import sys;print('ARGV', sys.argv)"
r = subprocess.run([PY, str(ENTRY), PY, "-c", probe],
                   env={**os.environ, "HF_TOKEN": "direct"},
                   capture_output=True, text=True, check=False)
print("E argv probe           rc=", r.returncode, "stdout=", repr(r.stdout[:300]))
