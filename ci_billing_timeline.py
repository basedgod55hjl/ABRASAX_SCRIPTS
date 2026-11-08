"""ci_billing_timeline.py — when did Actions stop working on this account?

Walks every repo's recent workflow runs and reports the newest SUCCESS per repo
alongside the newest run overall. If successes stop at a single timestamp and
everything after is startup_failure / billing-locked, that timestamp is when the
account lock began.

    python SCRIPTS/ci_billing_timeline.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx.repo import _api, remote_repos  # noqa: E402


def main() -> int:
    listing = remote_repos()
    live = listing.get("repos", {}) if listing["ok"] else {}
    rows = []
    for name in sorted(live):
        full = live[name]["full_name"]
        body = _api(f"/repos/{full}/actions/runs?per_page=20").get("body") or {}
        runs = body.get("workflow_runs") or []
        if not runs:
            rows.append({"repo": name, "runs": 0})
            continue
        last_ok = next((r for r in runs if r.get("conclusion") == "success"), None)
        rows.append({
            "repo": name,
            "runs": len(runs),
            "newest": runs[0].get("created_at"),
            "newest_conclusion": runs[0].get("conclusion"),
            "newest_success": last_ok.get("created_at") if last_ok else None,
        })

    rows.sort(key=lambda r: (r.get("newest_success") or "", r.get("newest") or ""), reverse=True)
    print(f"{'repo':<24} {'runs':>4}  {'newest run':<21} {'conclusion':<16} newest success")
    for r in rows:
        if r["runs"] == 0:
            print(f"{r['repo']:<24} {0:>4}  (no runs)")
            continue
        print(f"{r['repo']:<24} {r['runs']:>4}  {str(r['newest']):<21} "
              f"{str(r['newest_conclusion']):<16} {r['newest_success']}")

    concl = Counter(r.get("newest_conclusion") for r in rows if r["runs"])
    print("\nnewest-run conclusions:", dict(concl))
    succ = [r["newest_success"] for r in rows if r.get("newest_success")]
    print("latest successful run anywhere:", max(succ) if succ else "none")
    out = ROOT / "LOGS" / "ci_timeline.json"
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print("log:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
