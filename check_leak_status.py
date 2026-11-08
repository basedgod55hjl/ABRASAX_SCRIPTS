"""check_leak_status.py — authoritative read of the old leaked commit.

Uses the authenticated API (the unauthenticated `/commits/<sha>` request in a
redirect-following client is not a reliable answer: it can 404 on a commit the
repo API itself reports as HEAD). Prints the HTTP status per probe.

    python SCRIPTS/check_leak_status.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx.repo import _api, remote_head  # noqa: E402

REPO = "basedgod55hjl/ABRASAX-REBUILD"
HEAD = "18e66cf227b8acc31b60d9e4fa51521f16bf39af"
LEAK = "47bdb9f"


def probe(sha: str) -> None:
    r = _api(f"/repos/{REPO}/commits/{sha}")
    body = r.get("body") or {}
    print(f"commit {sha[:12]:<12} http={r.get('http')} "
          f"sha={(body.get('sha') or '')[:12] or '-'} "
          f"msg={((body.get('commit') or {}).get('message') or '')[:40]}")


def main() -> int:
    head = remote_head(REPO)
    print(f"live HEAD: {head.get('sha')}")
    probe(HEAD)
    probe(LEAK)
    r = _api(f"/repos/{REPO}/contents/SCRIPTS/automation/run_mesh.ps1?ref={LEAK}")
    print(f"contents@ {LEAK}: http={r.get('http')} error={r.get('error')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
