"""check_attribution.py — are the rebuilt commits attributed to the account?

`.gitconfig [user]` sets name/email; whether GitHub links a commit to an account
depends on that email matching a verified address on the account. The commits API
returns both the raw git author and a resolved `author` object with a login, so
this compares them and reports signature verification too.

    python SCRIPTS/check_attribution.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx.repo import _api, remote_head  # noqa: E402

REPOS = [
    "abrasax-harness", "ABRASAX-7D-Crystal", "ABRASAX-AI-Engine", "ABRASAX-Agents",
    "ABRASAX-DevOps", "ABRASAX-SWARM-ABRASAX", "ABRASAX-SWARM-SYS32",
    "ABRASAX-System32-AI", "ABRASAX-UI", "ABRASAX-core", "ABRASAX-core-v2",
    "ABRASAX-ecosystem", "ABRASAX-ecosystem-v2", "ABRASAX_SCRIPTS",
    "OSIRISBLXCK-CORE-v2",
]


def main() -> int:
    print(f"{'repo':<24} {'git author':<16} {'login':<16} {'signed':<7} email")
    unlinked = []
    for name in REPOS:
        sha = remote_head(f"basedgod55hjl/{name}").get("sha")
        if not sha:
            print(f"{name:<24} NO HEAD")
            unlinked.append(name)
            continue
        body = _api(f"/repos/basedgod55hjl/{name}/commits/{sha}").get("body") or {}
        git_author = (body.get("commit") or {}).get("author") or {}
        gh = body.get("author") or {}
        verified = ((body.get("commit") or {}).get("verification") or {}).get("verified")
        login = gh.get("login") or "-"
        print(f"{name:<24} {str(git_author.get('name'))[:15]:<16} {login:<16} "
              f"{str(verified):<7} {git_author.get('email')}")
        if login == "-":
            unlinked.append(name)
    print(f"\ncommits NOT linked to an account: {unlinked or 'none'}")
    return 0 if not unlinked else 1


if __name__ == "__main__":
    raise SystemExit(main())
