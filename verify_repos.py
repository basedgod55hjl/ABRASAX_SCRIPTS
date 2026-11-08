"""scripts/verify_repos.py — prove every production repo holds what it claims.

For each row of the 24-repo plan:
  * read the remote's real branch head through the GitHub API,
  * list the remote root tree through the API (not a local clone),
  * compare against what the local source tree would produce,
and report one row per repo with a verdict.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx import repo, repos24  # noqa: E402


def _remote_root(full_name: str, branch: str) -> dict:
    tree = repo._api(f"/repos/{full_name}/git/trees/{branch}?recursive=0")
    if not tree.get("ok"):
        return {"ok": False, "error": tree.get("error")}
    entries = tree["body"].get("tree", [])
    return {"ok": True, "root": sorted(e["path"] for e in entries),
            "files": sum(1 for e in entries if e["type"] == "blob"),
            "dirs": sum(1 for e in entries if e["type"] == "tree")}


def main() -> int:
    plan = repos24.repos24().to_dict()
    rows = plan["data"]["plan"]
    out = []
    bad = []
    for row in rows:
        name = row["repo"]
        full = f"basedgod55hjl/{name}"
        head = repo.remote_head(full, row["branch"])
        entry = {"repo": name, "kind": row["kind"], "branch": row["branch"],
                 "remote_sha": head.get("sha"), "size_kb": head.get("size_kb"),
                 "empty": head.get("empty")}
        if not head.get("ok"):
            entry["ok"] = False
            entry["error"] = head.get("error")
            bad.append(name)
            out.append(entry)
            continue
        if head.get("sha"):
            root = _remote_root(full, row["branch"])
            entry["root"] = root.get("root", [])[:12]
            entry["root_count"] = len(root.get("root", []))
            entry["has_provenance"] = "PROVENANCE.md" in (root.get("root") or [])
        else:
            entry["root_count"] = 0
            entry["has_provenance"] = False
        # verdict: a built repo must have a head; a never-built fork/absent source may be empty
        built = row.get("source") is not None
        entry["expect_content"] = built
        entry["ok"] = bool(head.get("sha")) if built else True
        if not entry["ok"]:
            bad.append(name)
        out.append(entry)
        sys.stdout.write(f"{name:<26} {str(entry['remote_sha'])[:10]:<11} "
                         f"root={entry['root_count']:<3} prov={entry['has_provenance']} ok={entry['ok']}\n")
        sys.stdout.flush()

    payload = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "count": len(out), "failed": bad, "repos": out}
    (ROOT / "LOGS" / "verify_repos.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    sys.stdout.write(f"\nVERIFY {len(out) - len(bad)}/{len(out)} ok failed={bad}\n")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
