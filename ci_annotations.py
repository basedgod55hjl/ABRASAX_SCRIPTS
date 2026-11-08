"""ci_annotations.py — read check-run annotations instead of logs.

Logs for these runs come back as an empty ZIP (0 entries), which is what GitHub
serves when the archive is not available to the token. Annotations carry the
same failure message without needing log access.

    python SCRIPTS/ci_annotations.py ABRASAX-UI ABRASAX-Agents
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx.repo import _api  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: ci_annotations.py <repo> [repo...]")
        return 2
    for name in argv:
        full = f"basedgod55hjl/{name}"
        runs = _api(f"/repos/{full}/actions/runs?per_page=1").get("body") or {}
        items = runs.get("workflow_runs") or []
        if not items:
            print(f"{name}: no runs")
            continue
        run = items[0]
        print(f"\n=== {name}  {run.get('conclusion')}  {run.get('html_url')}")
        checks = _api(f"/repos/{full}/commits/{run['head_sha']}/check-runs").get("body") or {}
        for cr in checks.get("check_runs") or []:
            if cr.get("conclusion") in ("success", "neutral", "skipped"):
                continue
            print(f"  check: {cr.get('name')} -> {cr.get('conclusion')}")
            ann = _api(f"/repos/{full}/check-runs/{cr['id']}/annotations").get("body")
            if isinstance(ann, list):
                for a in ann[:6]:
                    print(f"    [{a.get('annotation_level')}] {a.get('path')}:{a.get('start_line')} "
                          f"{str(a.get('message'))[:300]}")
            out = cr.get("output") or {}
            if out.get("summary"):
                print("    summary: " + str(out["summary"])[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
