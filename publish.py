"""scripts/publish.py — one command to publish the canonical tree.

    python scripts/publish.py                      # commit everything + push main, prove SHA
    python scripts/publish.py --message "..." --branch main
    python scripts/publish.py --no-commit          # push HEAD as-is

Writes LOGS/publish.json with the full envelope (local sha, remote sha, match)
so the result can be polled instead of trusted.
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
    ap.add_argument("--message", default=None)
    ap.add_argument("--branch", default="main")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--no-commit", action="store_true")
    ap.add_argument("--path", default=str(ROOT))
    ap.add_argument("--out", default="LOGS/publish.json")
    args = ap.parse_args(argv)

    from tools.abx import repo

    res = repo.sync(path=args.path, remote=args.remote, branch=args.branch,
                    message=None if args.no_commit else (args.message or "production rebuild sync"))
    env = res.to_dict()
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(env, indent=2, default=str), encoding="utf-8")
    sys.stdout.write(json.dumps({
        "ok": env["ok"],
        "local_sha": env["data"].get("local_sha"),
        "remote_sha": env["data"].get("remote_sha"),
        "matches": env["data"].get("matches"),
        "errors": env["errors"][:3],
    }, indent=2) + "\n")
    return 0 if env["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
