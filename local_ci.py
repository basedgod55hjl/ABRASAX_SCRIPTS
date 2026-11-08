"""local_ci.py — run the CI's meaningful step locally, per rebuilt repo.

Actions is locked for billing, so no runner will ever tell us whether these trees
are sound. The workflow's lint step is `ruff check . || true`, which cannot fail a
job even on a runner; the step with teeth is the `test` job:

    for f in *.py; do python -m py_compile "$f"; done

This reproduces exactly that against the staged tree that was pushed, plus a
syntax sweep of every subdirectory .py (broader than CI, and honest about it).

    python SCRIPTS/local_ci.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path(r"C:\Users\lucar\abrasax-build\stage")
PY = sys.executable

REBUILT = [
    "abrasax-harness", "ABRASAX-7D-Crystal", "ABRASAX-AI-Engine", "ABRASAX-Agents",
    "ABRASAX-DevOps", "ABRASAX-SWARM-ABRASAX", "ABRASAX-SWARM-SYS32",
    "ABRASAX-System32-AI", "ABRASAX-UI", "ABRASAX-core", "ABRASAX-core-v2",
    "ABRASAX-ecosystem", "ABRASAX-ecosystem-v2", "ABRASAX_SCRIPTS",
    "OSIRISBLXCK-CORE-v2",
]


def compile_file(path: Path) -> tuple[bool, str]:
    r = subprocess.run([PY, "-m", "py_compile", str(path)],
                       capture_output=True, text=True, timeout=120)
    return r.returncode == 0, (r.stderr or "").strip().splitlines()[-1] if r.returncode else ""


def main() -> int:
    rows = []
    for name in REBUILT:
        tree = STAGE / name
        if not tree.exists():
            rows.append({"repo": name, "state": "NOT STAGED"})
            continue
        t0 = time.time()
        top = sorted(tree.glob("*.py"))              # exactly what CI compiles
        deep = sorted(tree.rglob("*.py"))            # broader sweep
        bad_top, bad_deep = [], []
        for f in top:
            ok, err = compile_file(f)
            if not ok:
                bad_top.append({"file": f.name, "error": err})
        for f in deep:
            if f in top:
                continue
            ok, err = compile_file(f)
            if not ok:
                bad_deep.append({"file": str(f.relative_to(tree)), "error": err})
        rows.append({
            "repo": name,
            "state": "ok" if not bad_top else "CI-WOULD-FAIL",
            "ci_files": len(top), "ci_fail": bad_top,
            "deep_files": len(deep), "deep_fail": bad_deep,
            "seconds": round(time.time() - t0, 1),
        })
        print(f"{name:<26} ci_files={len(top):<4} ci_fail={len(bad_top):<3} "
              f"deep={len(deep):<5} deep_fail={len(bad_deep):<3} {rows[-1]['seconds']}s", flush=True)

    out = ROOT / "LOGS" / "local_ci.json"
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    failing = [r["repo"] for r in rows if r.get("state") == "CI-WOULD-FAIL"]
    not_staged = [r["repo"] for r in rows if r.get("state") == "NOT STAGED"]
    print(f"\nCI-equivalent failures: {failing or 'none'}")
    print(f"not staged (restored from mirror, nothing to compile): {not_staged or 'none'}")
    print(f"log: {out}")
    return 0 if not failing else 1


if __name__ == "__main__":
    raise SystemExit(main())
