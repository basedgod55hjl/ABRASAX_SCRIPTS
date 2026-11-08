"""snapshot_repo_meta.py — capture every remote repo's full API record.

Deleting and recreating repos loses settings that a git mirror cannot carry:
description, topics, homepage, default branch, fork parent, visibility. This
writes the raw API record for every repo on the account so the rebuild can
restore identity, and so a deletion is always explainable after the fact.

    python SCRIPTS/snapshot_repo_meta.py            # -> LOGS/repo_full_<ts>.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx.repo import _api, remote_repos  # noqa: E402

KEEP_FIELDS = [
    "full_name", "name", "private", "fork", "description", "homepage", "topics",
    "default_branch", "archived", "disabled", "visibility", "size", "language",
    "has_issues", "has_wiki", "has_projects", "has_discussions", "has_pages",
    "allow_squash_merge", "allow_merge_commit", "allow_rebase_merge",
    "delete_branch_on_merge", "pushed_at", "created_at", "updated_at", "html_url",
]


def main() -> int:
    listing = remote_repos()
    if not listing["ok"]:
        print(json.dumps({"ok": False, "error": listing.get("error")}))
        return 1

    records = {}
    for name in sorted(listing["repos"]):
        full = listing["repos"][name]["full_name"]
        rec = _api(f"/repos/{full}")
        if not rec.get("ok"):
            records[name] = {"ok": False, "error": rec.get("error"), "http": rec.get("http")}
            continue
        body = rec.get("body") or rec.get("json") or rec
        data = body if isinstance(body, dict) else {}
        slim = {k: data.get(k) for k in KEEP_FIELDS if k in data}
        parent = data.get("parent") or {}
        source = data.get("source") or {}
        slim["parent_full_name"] = parent.get("full_name")
        slim["source_full_name"] = source.get("full_name")
        slim["ok"] = True
        records[name] = slim

    out = ROOT / "LOGS" / ("repo_full_%s.json" % time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    payload = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "count": len(records), "repos": records}
    out.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    ok = [n for n, r in records.items() if r.get("ok")]
    forks = [n for n, r in records.items() if r.get("fork")]
    private = [n for n, r in records.items() if r.get("private")]
    print(json.dumps({"ok": True, "count": len(records), "fetched": len(ok),
                      "forks": forks, "private": len(private), "log": str(out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
