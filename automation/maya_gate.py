"""Run Laya's plain-script suites as AGENTS.md specifies, collecting timings.

AGENTS.md: "plain script suites: python tests/test_router.py, tests/test_criteria.py,
tests/test_hooks.py, tests/test_hooks_api.py". These are NOT pytest modules --
they are assert-based scripts. Running them under pytest can silently collect
nothing, which is how a "passing" suite hides a broken contract.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\ABRASAX\TYPESCRIPT\maya")
PY = Path(r"C:\ABRASAX\PYTHON\.venv_gui\Scripts\python.exe")

SUITES = [
    "tests/test_router.py",
    "tests/test_criteria.py",
    "tests/test_hooks.py",
    "tests/test_hooks_api.py",
    "tests/test_agent_api.py",
    "tests/test_structured.py",
]

rows = []
for rel in SUITES:
    p = ROOT / rel
    if not p.exists():
        rows.append({"suite": rel, "status": "MISSING"})
        print(f"MISSING  {rel}")
        continue
    t0 = time.time()
    try:
        r = subprocess.run([str(PY), rel], cwd=str(ROOT), capture_output=True,
                           text=True, timeout=900)
        dt = time.time() - t0
        tail = (r.stdout or "").strip().splitlines()[-3:]
        rows.append({"suite": rel, "rc": r.returncode, "seconds": round(dt, 1),
                     "tail": tail, "err": (r.stderr or "").strip()[-400:]})
        mark = "PASS" if r.returncode == 0 else "FAIL"
        print(f"{mark}  {rel:32} rc={r.returncode} {dt:6.1f}s  {tail[-1] if tail else ''}")
        if r.returncode != 0 and r.stderr:
            print("      stderr:", r.stderr.strip()[:300])
    except subprocess.TimeoutExpired:
        rows.append({"suite": rel, "status": "TIMEOUT"})
        print(f"TIMEOUT {rel}")

out = Path(r"C:\ABRASAX\LOGS\maya-suites.json")
out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
ok = sum(1 for r in rows if r.get("rc") == 0)
print(f"\n{ok}/{len(rows)} suites passed -> {out}")
sys.exit(0 if ok == len(rows) else 1)
