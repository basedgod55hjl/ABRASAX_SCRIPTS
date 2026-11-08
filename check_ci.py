"""check_ci.py — what did GitHub Actions do with the freshly rebuilt repos?

A rebuild pushes a new root commit; any workflow in that tree runs immediately.
Nobody looked at the results, so this reports, per repo: whether workflows exist,
and the latest run's status/conclusion. Read-only.

    python SCRIPTS/check_ci.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx.repo import _api, remote_repos  # noqa: E402

# the 20 rebuilt on 2026-11-01 (the 4 held repos keep their old history)
REBUILT = [
    "abrasax-harness", "ABRASAX-7D-Crystal", "ABRASAX-AI-Engine", "ABRASAX-Agents",
    "ABRASAX-DevOps", "ABRASAX-DATA", "ABRASAX-SWARM-ABRASAX", "ABRASAX-SWARM-AI",
    "ABRASAX-SWARM-SYS32", "ABRASAX-System32-AI", "ABRASAX-UI", "ABRASAX-core",
    "ABRASAX-core-v2", "ABRASAX-ecosystem", "ABRASAX-ecosystem-v2", "ABRASAX_DATA",
    "ABRASAX_SCRIPTS", "ALL_REPOS", "OSIRISBLXCK-CORE", "OSIRISBLXCK-CORE-v2",
]


def main() -> int:
    listing = remote_repos()
    live = listing.get("repos", {}) if listing["ok"] else {}
    rows = []
    for name in REBUILT:
        if name not in live:
            rows.append({"repo": name, "state": "MISSING"})
            continue
        full = live[name]["full_name"]
        wf = _api(f"/repos/{full}/actions/workflows")
        wf_body = wf.get("body") or {}
        workflows = wf_body.get("workflows") if isinstance(wf_body, dict) else None
        n_wf = wf_body.get("total_count") if isinstance(wf_body, dict) else None
        runs = _api(f"/repos/{full}/actions/runs?per_page=1")
        runs_body = runs.get("body") or {}
        run_items = (runs_body.get("workflow_runs") or []) if isinstance(runs_body, dict) else []
        latest = run_items[0] if run_items else None
        rows.append({
            "repo": name,
            "workflows": n_wf,
            "wf_http": wf.get("http"),
            "latest": None if not latest else {
                "name": latest.get("name"),
                "event": latest.get("event"),
                "status": latest.get("status"),
                "conclusion": latest.get("conclusion"),
                "head": (latest.get("head_sha") or "")[:8],
                "url": latest.get("html_url"),
            },
        })

    print(f"{'repo':<24} {'wf':>3}  {'status':<10} {'conclusion':<14} {'head':<9} name")
    for r in rows:
        if r.get("state") == "MISSING":
            print(f"{r['repo']:<24} MISSING")
            continue
        l = r["latest"]
        if not l:
            print(f"{r['repo']:<24} {str(r['workflows']):>3}  {'-':<10} {'no runs':<14}")
            continue
        print(f"{r['repo']:<24} {str(r['workflows']):>3}  {str(l['status']):<10} "
              f"{str(l['conclusion']):<14} {l['head']:<9} {l['name']} ({l['event']})")

    out = ROOT / "LOGS" / "ci_status.json"
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    failing = [r["repo"] for r in rows if (r.get("latest") or {}).get("conclusion") == "failure"]
    print(f"\nfailing: {failing or 'none'}   log: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
