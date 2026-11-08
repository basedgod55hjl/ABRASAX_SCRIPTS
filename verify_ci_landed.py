"""verify_ci_landed.py — did the repaired workflow actually reach GitHub?

Compares each repo's `.github/workflows/ci.yml` on the default branch against
DOC/templates/ci.yml, normalising line endings. Reports the SHA-256 prefix of
what the remote holds so a stale push is obvious.

    python SCRIPTS/verify_ci_landed.py
"""
from __future__ import annotations

import base64
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx.repo import _api  # noqa: E402

TEMPLATE = (ROOT / "DOC" / "templates" / "ci.yml").read_text(encoding="utf-8")
WANT_JOBS = ("byte-compile every .py (gate)", "ruff (advisory)")

REPOS = [
    "ABRASAX-UI", "ABRASAX-7D-Crystal", "ABRASAX-Agents",
    "ABRASAX-DevOps", "ABRASAX-System32-AI", "ABRASAX-SWARM-AI",
]


def norm(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n")).strip()


def main() -> int:
    want = norm(TEMPLATE)
    ok_all = True
    print(f"{'repo':<24} {'remote ci.yml':<14} {'has gate':<9} sha256[:12]")
    for name in REPOS:
        r = _api(f"/repos/basedgod55hjl/{name}/contents/.github/workflows/ci.yml")
        body = r.get("body") or {}
        content = body.get("content")
        if not content:
            print(f"{name:<24} {'ABSENT':<14} {'-':<9} http={r.get('http')}")
            ok_all = False
            continue
        text = base64.b64decode(content).decode("utf-8", "replace")
        same = norm(text) == want
        gate = all(j in text for j in WANT_JOBS)
        digest = hashlib.sha256(norm(text).encode()).hexdigest()[:12]
        print(f"{name:<24} {'matches' if same else 'DIFFERS':<14} {str(gate):<9} {digest}")
        if not gate:
            ok_all = False
    print("\nOK" if ok_all else "\nPROBLEMS FOUND")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
