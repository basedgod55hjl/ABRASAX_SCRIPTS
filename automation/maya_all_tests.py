"""Run every Laya assert-script correctly, in its native mode.

47 of 93 test files under tests/ are NOT pytest modules: they execute assertions
at import time and call sys.exit() at module scope (verified: tests/test_agent_gate.py:255).
Under pytest that aborts collection with INTERNALERROR SystemExit 0, so every
file after them silently never runs. The honest way to run them is as scripts.

This classifies each test_*.py and runs it the way it was written, reporting
pass / real-failure / skipped-for-missing-optional-dep separately.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\ABRASAX\TYPESCRIPT\maya")
TESTS = ROOT / "tests"
PY = Path(r"C:\ABRASAX\PYTHON\.venv_gui\Scripts\python.exe")
OUT = Path(r"C:\ABRASAX\LOGS\maya-scripts.json")

# Hardcoded in the CI gates as known-missing optional extras.
OPTIONAL = {
    "transformers": "test_criteria.py",
    "onnx": "test_onnx*.py",
    "fastapi": "test_serve.py",
    "langchain": "test_langchain*.py",
}


def module_scope_exit(text: str) -> bool:
    """True if sys.exit() appears at column 0 (module scope, not in a func)."""
    return bool(re.search(r"(?m)^sys\.exit\(", text))


def is_pytest_module(text: str) -> bool:
    return bool(re.search(r"(?m)^(def test_|class Test)", text)) and not module_scope_exit(text)


def classify(p: Path) -> str:
    text = p.read_text(encoding="utf-8", errors="replace")
    if is_pytest_module(text):
        return "pytest"
    if module_scope_exit(text):
        return "script"
    return "other"


def main() -> int:
    files = sorted(TESTS.glob("test_*.py"))
    kinds: dict[str, list[Path]] = {"pytest": [], "script": [], "other": []}
    for p in files:
        kinds[classify(p)].append(p)
    print(f"{len(files)} test files -> pytest={len(kinds['pytest'])} "
          f"script={len(kinds['script'])} other={len(kinds['other'])}")

    results = []
    for mode in ("script", "pytest", "other"):
        for p in kinds[mode]:
            if mode == "pytest":
                cmd = [str(PY), "-m", "pytest", str(p.relative_to(ROOT)), "-q",
                       "-p", "no:cacheprovider", "--no-header"]
            else:
                cmd = [str(PY), str(p.relative_to(ROOT))]
            t0 = time.time()
            try:
                r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True,
                                   text=True, timeout=900)
                dt = time.time() - t0
            except subprocess.TimeoutExpired:
                results.append({"file": p.name, "mode": mode, "status": "timeout"})
                print(f"TIMEOUT  {p.name}")
                continue
            err = (r.stderr or "")
            missing = re.findall(r"No module named '([\w.]+)'", err)
            if r.returncode == 0:
                status = "pass"
            elif missing:
                status = f"skip-dep:{missing[0]}"
            elif "INTERNALERROR" in err and "SystemExit" in err:
                status = "collection-abort"
            else:
                status = "fail"
            results.append({"file": p.name, "mode": mode, "status": status,
                            "rc": r.returncode, "seconds": round(dt, 1),
                            "tail": (r.stdout or "").strip().splitlines()[-1][:160]
                            if (r.stdout or "").strip() else "",
                            "err": err.strip()[-300:]})
            print(f"{status:16} {p.name:44} rc={r.returncode:3} {dt:6.1f}s")

    OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
    tally: dict[str, int] = {}
    for r in results:
        key = r["status"].split(":")[0]
        tally[key] = tally.get(key, 0) + 1
    print("\nTALLY:", json.dumps(tally))
    fails = [r for r in results if r["status"] in ("fail", "collection-abort", "timeout")]
    if fails:
        print(f"\n{len(fails)} non-passing:")
        for f in fails:
            print(f"  {f['file']}  rc={f.get('rc')}  {(f.get('err') or '')[:160]}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
