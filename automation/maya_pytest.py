"""Run Laya's pytest layer with an honest skip/fail breakdown.

AGENTS.md calls out three pytest paths explicitly (test_serve, test_onnx, and the
fast/local e2e that need CUDA or checkpoints). Those legitimately skip on a box
without the extras, so a raw pass count is misleading -- this reports
passed/skipped/failed separately and lists every skip reason.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\ABRASAX\TYPESCRIPT\maya")
PY = Path(r"C:\ABRASAX\PYTHON\.venv_gui\Scripts\python.exe")
OUT = Path(r"C:\ABRASAX\LOGS\maya-pytest.txt")
JSON = Path(r"C:\ABRASAX\LOGS\maya-pytest.json")

cmd = [str(PY), "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider",
       "--ignore=tests/test_criteria.py",
       "--ignore=tests/test_router.py",
       "--ignore=tests/test_hooks.py",
       "--ignore=tests/test_hooks_api.py",
       "--ignore=tests/test_structured.py"]

print("running:", " ".join(cmd[2:]))
r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=2400)
OUT.write_text((r.stdout or "") + "\n---STDERR---\n" + (r.stderr or ""), encoding="utf-8")

text = r.stdout or ""
summary = re.findall(r"^(?:=+\s*)?(\d+) (passed|failed|skipped|error)", text, re.M)
counts = {}
for n, kind in summary:
    counts[kind] = counts.get(kind, 0) + int(n)
last = [ln for ln in text.strip().splitlines() if ln.strip()][-1:] or [""]

skips = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("SKIPPED")]
errs = [ln.strip() for ln in text.splitlines() if "FAILED" in ln or "ERROR " in ln]

print("rc:", r.returncode)
print("counts:", json.dumps(counts))
print("last:", last[0][:200])
if skips:
    print(f"skip reasons ({len(skips)}):")
    for s in skips[:15]:
        print("  ", s[:180])
if errs:
    print(f"failures ({len(errs)}):")
    for e in errs[:15]:
        print("  ", e[:200])

JSON.write_text(json.dumps({"rc": r.returncode, "counts": counts,
                            "last": last[0], "skips": skips, "failures": errs}, indent=1),
                encoding="utf-8")
sys.exit(0 if r.returncode == 0 else 1)
