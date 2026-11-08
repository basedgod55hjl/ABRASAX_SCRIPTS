"""verify_rebuild_identity.py — prove the 24 repos kept their identity.

Deleting and recreating repos must not silently change visibility, description
or default branch: those are the settings a git mirror cannot carry. This diffs
the live account against the pre-delete snapshot (LOGS/repo_full_*.json).

    python SCRIPTS/verify_rebuild_identity.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx import repo  # noqa: E402

LOGS = ROOT / "LOGS"


def latest_snapshot() -> dict:
    files = sorted(LOGS.glob("repo_full_*.json"))
    if not files:
        return {}
    return json.loads(files[-1].read_text(encoding="utf-8")).get("repos", {})


def main() -> int:
    snap = latest_snapshot()
    listing = repo.remote_repos()
    live = listing.get("repos", {}) if listing["ok"] else {}
    if not snap:
        print("no snapshot found")
        return 2

    print(f"{'repo':<26} {'private':>7} {'was':>5}  {'branch':<7} {'was':<7}  desc")
    problems = []
    for name in sorted(snap):
        was = snap[name]
        if name not in live:
            print(f"{name:<26} MISSING")
            problems.append((name, "missing"))
            continue
        now = live[name]
        priv_now, priv_was = bool(now.get("private")), bool(was.get("private"))
        br_now, br_was = now.get("branch"), was.get("default_branch")
        desc_now = (repo._api(f"/repos/{now['full_name']}").get("body") or {}).get("description") or ""
        desc_was = was.get("description") or ""
        flags = []
        if priv_now != priv_was:
            flags.append("visibility")
        if br_now != br_was and br_was:
            flags.append("branch")
        if desc_was and desc_now != desc_was:
            flags.append("description")
        if flags:
            problems.append((name, ",".join(flags)))
        print(f"{name:<26} {str(priv_now):>7} {str(priv_was):>5}  {str(br_now):<7} {str(br_was):<7}  "
              f"{'DRIFT:' + ','.join(flags) if flags else 'ok'}")

    print(json.dumps({"ok": not problems, "problems": problems}))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
