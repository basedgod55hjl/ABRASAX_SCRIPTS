"""Reproduce test_docker_entrypoint.py's failing assertion directly.

The test asserts the entrypoint prints exactly ONE newline for the child's
single-line JSON. It saw 0 instead of 1. Rather than guess, run the same
invocation and show stdout/stderr as repr (so blank lines and \\r are visible).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\ABRASAX\TYPESCRIPT\maya")
ENTRY = ROOT / "docker" / "entrypoint.py"
PY = sys.executable

print("entrypoint exists:", ENTRY.exists())
print("entrypoint size:", ENTRY.stat().st_size if ENTRY.exists() else 0)

env = dict(os.environ)
env.pop("HF_TOKEN", None)
env.pop("HF_TOKEN_FILE", None)
env["HF_TOKEN"] = "direct"

child = ("import json, os, sys;"
         "print(json.dumps({'name': 'HF_TOKEN',"
         " 'matched': os.environ.get('HF_TOKEN') == 'direct',"
         " 'file_var': 'HF_TOKEN_FILE' in os.environ}))")

r = subprocess.run([PY, str(ENTRY), PY, "-c", child],
                   env=env, capture_output=True, text=True, check=False)
print("rc:", r.returncode)
print("stdout repr:", repr(r.stdout))
print("stderr repr:", repr(r.stderr[:500]))
print("stdout newline count:", r.stdout.count("\n"))

# also try with an empty-ish env like the failing subtest
env2 = {"HF_TOKEN": "direct"}
r2 = subprocess.run([PY, str(ENTRY), PY, "-c", child],
                    env=env2, capture_output=True, text=True, check=False)
print("\n[minimal env] rc:", r2.returncode)
print("[minimal env] stdout repr:", repr(r2.stdout))
print("[minimal env] stderr repr:", repr(r2.stderr[:300]))
print("[minimal env] newline count:", r2.stdout.count("\n"))
