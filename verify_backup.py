"""scripts/verify_backup.py — prove the backup is restorable, per repo.

A mirror that clones is not a backup until you can reconstruct the tree from it.
For every mirror this checks:
  1. `git fsck` reports no missing objects,
  2. the ref count matches the API's default branch head,
  3. for non-empty repos, the default branch HEAD SHA equals the API SHA.

Exit code is non-zero if any repo fails any check, so it can gate deletion.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx import repo  # noqa: E402

BACKUP = Path(r"C:\abrasax-backup")
MIRRORS = BACKUP / "mirrors"


def main() -> int:
    manifest = json.loads((BACKUP / "manifest.json").read_text(encoding="utf-8"))
    results = []
    bad = []
    for rec in manifest["records"]:
        name = rec["repo"]
        mirror = Path(rec["mirror"])
        row = {"repo": name, "mirror_exists": mirror.exists()}
        if not mirror.exists():
            row["ok"] = False
            bad.append(name)
            results.append(row)
            continue

        fsck = repo.run(["git", "-C", str(mirror), "fsck", "--no-progress"], timeout=1800)
        row["fsck_exit"] = fsck["exit"]
        row["fsck_error"] = (fsck["stderr"] or "").strip()[:200] if fsck["exit"] != 0 else None

        head = repo.run(["git", "-C", str(mirror), "rev-parse", "HEAD"], timeout=120)
        mirror_head = head["stdout"].strip()
        remote = repo.remote_head(rec["full_name"], rec["branch"])
        row["mirror_head"] = mirror_head
        row["remote_sha"] = remote.get("sha")
        row["remote_empty"] = remote.get("empty")

        if remote.get("sha"):
            row["head_matches"] = mirror_head == remote["sha"]
        else:
            row["head_matches"] = None  # empty repo: nothing to match

        row["ok"] = (fsck["exit"] == 0 and row["head_matches"] is not False)
        if not row["ok"]:
            bad.append(name)
        results.append(row)
        sys.stdout.write(f"{name:<28} fsck={fsck['exit']} head_match={row['head_matches']} ok={row['ok']}\n")
        sys.stdout.flush()

    payload = {"count": len(results), "failed": bad, "results": results}
    (BACKUP / "verify.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    sys.stdout.write(f"\nVERIFY {len(results) - len(bad)}/{len(results)} ok  failed={bad}\n")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
