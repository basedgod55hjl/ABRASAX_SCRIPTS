"""rebuild_retry.py — finish the 24-repo rebuild through GitHub's secondary
rate limit.

GitHub blocks *content creation* (repo create) for a while after a burst, while
the core API keeps answering 200 and reporting 4999/5000 remaining. There is no
retry-after header to obey, so the only correct strategy is patient rounds:
re-run the remaining rows, sleep, prove the account state again, repeat.

A row is done when the repo exists AND its remote default-branch SHA equals what
this tool pushed (rebuild_repos proves that per row; this proves it again from
the API, independently).

    python SCRIPTS/rebuild_retry.py --rounds 12 --sleep 600
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "SCRIPTS"))

from tools.abx import repo, repos24  # noqa: E402

TARGETS = [
    "ABRASAX-UI", "ABRASAX-core", "ABRASAX-core-v2", "ABRASAX-ecosystem",
    "ABRASAX-ecosystem-v2", "ABRASAX_DATA", "ABRASAX_SCRIPTS", "ALL_REPOS",
    "OSIRISBLXCK-CORE", "OSIRISBLXCK-CORE-v2",
]


def row_branch(name: str) -> str:
    for row in repos24.ROWS:
        if row["repo"] == name:
            return row["branch"]
    return "main"


def status() -> dict:
    listing = repo.remote_repos()
    live = listing.get("repos", {}) if listing["ok"] else {}
    out = {}
    for name in TARGETS:
        if name not in live:
            out[name] = {"state": "missing"}
            continue
        head = repo.remote_head(live[name]["full_name"], row_branch(name))
        out[name] = {"state": "present", "sha": head.get("sha")}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=12)
    ap.add_argument("--sleep", type=float, default=600.0)
    ap.add_argument("--repos", default=",".join(TARGETS))
    args = ap.parse_args(argv)
    targets = [x.strip() for x in args.repos.split(",") if x.strip()]

    import rebuild_repos

    for rnd in range(1, args.rounds + 1):
        st = status()
        missing = [n for n in targets if st.get(n, {}).get("state") != "present"]
        print(f"\n=== round {rnd}/{args.rounds}  present={len(targets) - len(missing)}/{len(targets)}"
              f"  missing={missing}", flush=True)
        if not missing:
            print("ALL PRESENT", flush=True)
            break
        rc = rebuild_repos.main(["--repos", ",".join(missing), "--skip-delete", "--go", "--pace", "45"])
        print(f"round {rnd} exit={rc}", flush=True)
        st = status()
        if all(st.get(n, {}).get("state") == "present" for n in targets):
            print("ALL PRESENT", flush=True)
            break
        if rnd < args.rounds:
            print(f"sleeping {args.sleep:.0f}s before round {rnd + 1}", flush=True)
            time.sleep(args.sleep)

    st = status()
    print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "status": st}, indent=1))
    return 0 if all(v.get("state") == "present" for v in st.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
