"""verify_pushed_tree.py — does GitHub hold exactly the tree that was staged?

Everything so far proves SHAs and identity. This proves CONTENT: it lists every
path in the remote commit (recursive tree API) and compares it, path for path,
against the local staged repository's HEAD. A silent truncation, a .gitignore
that swallowed a directory, or a partial push all show up here and nowhere else.

    python SCRIPTS/verify_pushed_tree.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx.repo import _api, remote_head  # noqa: E402

STAGE = Path(r"C:\Users\lucar\abrasax-build\stage")

REBUILT = [
    "abrasax-harness", "ABRASAX-7D-Crystal", "ABRASAX-AI-Engine", "ABRASAX-Agents",
    "ABRASAX-DevOps", "ABRASAX-SWARM-ABRASAX", "ABRASAX-SWARM-SYS32",
    "ABRASAX-System32-AI", "ABRASAX-UI", "ABRASAX-core", "ABRASAX-core-v2",
    "ABRASAX-ecosystem", "ABRASAX-ecosystem-v2", "ABRASAX_SCRIPTS",
    "OSIRISBLXCK-CORE-v2",
]


def local_paths(tree: Path) -> set[str]:
    r = subprocess.run(["git", "-C", str(tree), "ls-tree", "-r", "--name-only", "HEAD"],
                       capture_output=True, text=True, timeout=300)
    return {ln for ln in r.stdout.splitlines() if ln.strip()}


def remote_paths(full: str, sha: str) -> tuple[set[str], bool]:
    body = _api(f"/repos/{full}/git/trees/{sha}?recursive=1").get("body") or {}
    tree = body.get("tree") or []
    paths = {e["path"] for e in tree if e.get("type") == "blob"}
    return paths, bool(body.get("truncated"))


def main() -> int:
    rows = []
    for name in REBUILT:
        tree = STAGE / name
        if not (tree / ".git").exists():
            rows.append({"repo": name, "state": "not-staged"})
            print(f"{name:<26} (no local git tree; restored from mirror)")
            continue
        head = remote_head(f"basedgod55hjl/{name}")
        sha = head.get("sha")
        if not sha:
            rows.append({"repo": name, "state": "no-remote-head"})
            print(f"{name:<26} NO REMOTE HEAD")
            continue
        local = local_paths(tree)
        remote, truncated = remote_paths(f"basedgod55hjl/{name}", sha)
        missing = sorted(local - remote)
        extra = sorted(remote - local)
        ok = not missing and not extra and not truncated
        rows.append({"repo": name, "state": "match" if ok else "DIFF",
                     "local": len(local), "remote": len(remote),
                     "missing": missing[:10], "extra": extra[:10], "truncated": truncated})
        flag = "match" if ok else f"DIFF missing={len(missing)} extra={len(extra)}"
        print(f"{name:<26} local={len(local):<5} remote={len(remote):<5} {flag}"
              + (" TRUNCATED-API" if truncated else ""))
        for p in missing[:3]:
            print("    missing on remote: " + p)
        for p in extra[:3]:
            print("    extra on remote:   " + p)

    out = ROOT / "LOGS" / "pushed_tree.json"
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    bad = [r["repo"] for r in rows if r.get("state") not in ("match", "not-staged")]
    print(f"\ncontent mismatches: {bad or 'none'}")
    print("log:", out)
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
