"""scripts/run_team.py — run every ABRASAX agent member and print proven reports.

    python scripts/run_team.py                 # all members, no narration
    python scripts/run_team.py --narrate       # all members, narrated by the seat
    python scripts/run_team.py --only repo-keeper stack-sentinel
    python scripts/run_team.py --json          # machine-readable bundle

Each member writes its own evidence log under LOGS/abx/agents/. The script
exits non-zero if any member's tool evidence came back not-ok, so it can gate
a build.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--narrate", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    from tools.abx.agent import Agent, roster
    from tools.abx.team import MEMBERS

    members = args.only or list(MEMBERS)
    unknown = [m for m in members if m not in MEMBERS]
    if unknown:
        sys.stderr.write(f"unknown members: {unknown}\n{roster()}\n")
        return 2

    records = []
    if not args.json:
        sys.stdout.write(roster() + "\n\n")
    for name in members:
        agent = Agent(name, narrate=args.narrate)
        rec = agent.run()
        records.append(rec)
        if not args.json:
            sys.stdout.write(agent.report() + "\n\n")

    failed = [r["member"] for r in records if not r["ok"]]
    if args.json:
        sys.stdout.write(json.dumps({"members": records, "failed": failed}, indent=2, default=str) + "\n")
    else:
        sys.stdout.write(f"TEAM RESULT: {len(records) - len(failed)}/{len(records)} ok"
                         + (f"  FAILED: {', '.join(failed)}" if failed else "") + "\n")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
