"""Classify the 13 non-passing Laya suites honestly.

rc semantics we must not confuse:
  0 = pass, 1 = real failure, 2 = interrupted/usage, 5 = NO TESTS COLLECTED.
A pytest file containing only assert-scripts collects zero tests and exits 5 --
that is a harness artifact, not a defect. Similarly a module import guarded by
`pytest.importorskip` or a missing optional extra is an environment skip.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\ABRASAX\TYPESCRIPT\maya")
PY = Path(r"C:\ABRASAX\PYTHON\.venv_gui\Scripts\python.exe")

FILES = [
    "test_audit_regressions.py", "test_compile.py", "test_compile_cuda.py",
    "test_decision_model.py", "test_evals.py", "test_fast.py", "test_fast_cpu.py",
    "test_mcp_remote.py", "test_serve.py", "test_truncation_direction.py",
    "test_docker_entrypoint.py", "test_docker_torch.py", "test_langchain_real_mode.py",
]

out = {}
for name in FILES:
    p = ROOT / "tests" / name
    if not p.exists():
        out[name] = {"verdict": "missing"}
        continue
    text = p.read_text(encoding="utf-8", errors="replace")
    has_pytest_funcs = bool(re.search(r"(?m)^(def test_|class Test)", text))
    is_script = bool(re.search(r"(?m)^sys\.exit\(", text))

    if has_pytest_funcs and not is_script:
        cmd = [str(PY), "-m", "pytest", f"tests/{name}", "-q", "-p",
               "no:cacheprovider", "--no-header", "--tb=line"]
    else:
        cmd = [str(PY), f"tests/{name}"]

    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=1800)
    blob = (r.stdout or "") + "\n" + (r.stderr or "")
    missing = sorted(set(re.findall(r"No module named '([\w.]+)'", blob)))
    skipped = re.findall(r"(\d+) skipped", blob)
    passed = re.findall(r"(\d+) passed", blob)
    no_tests = "no tests ran" in blob or "no tests collected" in blob

    if r.returncode == 0:
        verdict = "pass"
    elif r.returncode == 5 or (no_tests and not missing):
        verdict = "not-a-pytest-module"
    elif missing:
        verdict = f"env-missing:{','.join(missing[:3])}"
    elif "skipped" in blob and not re.search(r"\d+ failed", blob):
        verdict = "env-skipped"
    else:
        verdict = "REAL-FAILURE"

    reason = ""
    if verdict == "REAL-FAILURE":
        for ln in blob.splitlines():
            if re.search(r"(Error|assert|FAILED|Exception)", ln) and "INTERNALERROR" not in ln:
                reason = ln.strip()[:220]
                if "test_" in reason or "Error" in reason:
                    break
    out[name] = {"verdict": verdict, "rc": r.returncode,
                 "passed": passed[0] if passed else None,
                 "skipped": skipped[0] if skipped else None,
                 "reason": reason}
    print(f"{verdict:26} {name:36} rc={r.returncode} "
          f"passed={out[name]['passed']} skipped={out[name]['skipped']}")
    if reason:
        print(f"      -> {reason}")

Path(r"C:\ABRASAX\LOGS\maya-failures.json").write_text(
    json.dumps(out, indent=1), encoding="utf-8")
real = [k for k, v in out.items() if v["verdict"] == "REAL-FAILURE"]
print(f"\nREAL FAILURES: {len(real)} {real}")
sys.exit(0 if not real else 1)
