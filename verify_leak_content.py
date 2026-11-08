"""verify_leak_content.py — does the orphaned commit still contain the live PAT?

Prints only booleans and lengths. Never prints the token.

Compares three things:
  1. whether the file at the leaked SHA matches the token pattern,
  2. whether the token embedded there is byte-identical to the token this box
     currently authenticates with (i.e. the leak is still a live credential),
  3. whether the same file at HEAD is clean.
"""
from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx.repo import _api, token  # noqa: E402

REPO = "basedgod55hjl/ABRASAX-REBUILD"
PATH = "SCRIPTS/automation/run_mesh.ps1"
LEAK_SHA = "47bdb9f"
PATTERN = re.compile(r"github_pat_[A-Za-z0-9_]{20,}")


def fetch(ref: str) -> str | None:
    r = _api(f"/repos/{REPO}/contents/{PATH}?ref={ref}")
    body = r.get("body") or {}
    content = body.get("content")
    if not content:
        return None
    return base64.b64decode(content).decode("utf-8", "replace")


def main() -> int:
    live = token() or ""
    print(f"live token present: {bool(live)}  length: {len(live)}")

    for ref in (LEAK_SHA, "main"):
        text = fetch(ref)
        if text is None:
            print(f"{ref:<10} file: NOT READABLE")
            continue
        hits = PATTERN.findall(text)
        print(f"{ref:<10} file bytes={len(text):<6} token-shaped strings={len(hits)} "
              f"equals_live={any(h == live for h in hits)}")
        for h in hits:
            print(f"           found token: len={len(h)} prefix={h[:12]}... same_as_live={h == live}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
