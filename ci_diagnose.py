"""ci_diagnose.py — why did the rebuilt repos' CI fail?

Fetches the latest failed run, its jobs, the failing step names and the tail of
that step's log. Read-only.

    python SCRIPTS/ci_diagnose.py ABRASAX-UI
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx.repo import _api


def get(url: str) -> dict:
    return _api(url)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: ci_diagnose.py <repo> [repo...]")
        return 2
    for name in argv:
        full = f"basedgod55hjl/{name}"
        runs = get(f"/repos/{full}/actions/runs?per_page=3").get("body") or {}
        items = runs.get("workflow_runs") or []
        if not items:
            print(f"{name}: no runs")
            continue
        run = items[0]
        print(f"\n=== {name}  run {run.get('id')}  {run.get('status')}/{run.get('conclusion')}")
        jobs = get(f"/repos/{full}/actions/runs/{run['id']}/jobs").get("body") or {}
        for job in jobs.get("jobs") or []:
            print(f"  job: {job.get('name')} -> {job.get('conclusion')}")
            for step in job.get("steps") or []:
                if step.get("conclusion") not in ("success", "skipped", None):
                    print(f"    FAILED STEP: {step.get('number')}. {step.get('name')} ({step.get('conclusion')})")
        print(f"  url: {run.get('html_url')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
