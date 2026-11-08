"""scripts/release.py — build + prove the distributable.

    python scripts/release.py [--out LOGS/release_tool.json]

Builds the sdist and wheel, installs the wheel into a scratch target, imports
it from that target and records the artifact hashes. Nothing is committed.
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
    ap.add_argument("--out", default="LOGS/release_tool.json")
    ap.add_argument("--no-clean", action="store_true")
    args = ap.parse_args(argv)

    from tools.abx import release

    env = release.release(clean=not args.no_clean).to_dict()
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(env, indent=2, default=str), encoding="utf-8")
    sys.stdout.write(json.dumps({
        "ok": env["ok"],
        "artifacts": env["data"].get("artifacts"),
        "imported_from": env["data"].get("imported_from"),
        "version": env["data"].get("version"),
        "errors": env["errors"][:3],
    }, indent=2) + "\n")
    return 0 if env["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
