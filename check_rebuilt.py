"""check_rebuilt.py — read back what actually landed on GitHub.

Prints, per repo: default branch, remote SHA, root file count, whether
PROVENANCE.md is present, and the size GitHub reports. This is deliberately a
separate read path from the build tool: if the build lied, this shows it.

    python SCRIPTS/check_rebuilt.py
    python SCRIPTS/check_rebuilt.py --all
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx.repo import _api, remote_head, remote_repos  # noqa: E402

REBUILT = [
    "abrasax-harness", "ABRASAX-7D-Crystal", "ABRASAX-AI-Engine", "ABRASAX-Agents",
    "ABRASAX-DevOps", "ABRASAX-DATA", "ABRASAX-SWARM-AI", "ABRASAX-SWARM-SYS32",
    "ABRASAX-System32-AI", "ABRASAX-SWARM-ABRASAX",
]


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    listing = remote_repos()
    if not listing["ok"]:
        print("cannot list repos:", listing.get("error"))
        return 1
    repos = listing["repos"]
    names = sorted(repos) if "--all" in argv else REBUILT

    print(f"{'repo':<26} {'br':<7} {'sha':<9} {'root':>5} {'MB':>6}  prov")
    missing = []
    for name in names:
        if name not in repos:
            print(f"{name:<26} MISSING")
            missing.append(name)
            continue
        full = repos[name]["full_name"]
        head = remote_head(full)
        root = _api(f"/repos/{full}/contents/")
        body = root.get("body")
        entries = body if isinstance(body, list) else []
        names_in = {e.get("name") for e in entries}
        print(f"{name:<26} {repos[name]['branch']:<7} {str(head.get('sha'))[:8]:<9} "
              f"{len(entries):>5} {repos[name]['size_kb'] / 1024:>6.1f}  "
              f"{'yes' if 'PROVENANCE.md' in names_in else '-'}")
    if missing:
        print(f"\nmissing: {missing}")
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
