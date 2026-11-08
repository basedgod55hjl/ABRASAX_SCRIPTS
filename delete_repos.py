"""scripts/delete_repos.py — delete repos that pass the mirror gate.

Every target must (a) not be on the keep list, (b) be named in --confirm,
(c) have a mirror whose HEAD equals the live remote HEAD with a clean fsck.
The tool refuses otherwise, per repo, and reports what it actually deleted.

    python scripts/delete_repos.py --repos A,B --confirm A,B --dry-run
    python scripts/delete_repos.py --repos A,B --confirm A,B --go
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos", required=True, help="comma list")
    ap.add_argument("--confirm", required=True, help="must name every repo above")
    ap.add_argument("--go", action="store_true", help="actually delete (default: dry run)")
    args = ap.parse_args(argv)

    from tools.abx import repo_delete

    res = repo_delete.delete(repos=args.repos, confirm=args.confirm, dry_run=not args.go)
    env = res.to_dict()
    out = ROOT / "LOGS" / ("delete_%s.json" % time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    out.write_text(json.dumps(env, indent=2, default=str), encoding="utf-8")
    sys.stdout.write(json.dumps({
        "ok": env["ok"],
        "dry_run": env["data"].get("dry_run"),
        "would_delete": env["data"].get("would_delete"),
        "deleted": env["data"].get("deleted"),
        "failed": env["data"].get("failed"),
        "blocked": env["data"].get("blocked"),
        "log": str(out),
    }, indent=2) + "\n")
    return 0 if env["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
