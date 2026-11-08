"""scripts/prune_work.py — delete build scratch, prove the mirrors survive.

The build left ~2 staging trees under C:\\Users\\lucar\\abrasax-build\\. This
removes them and then re-verifies that every backup mirror still passes fsck,
so the cleanup can never quietly take the backup with it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx.repo_delete import prune_local_work  # noqa: E402
from tools.abx import repo  # noqa: E402

BACKUP = Path(r"C:\abrasax-backup")


def main() -> int:
    before = sum(p.stat().st_size for p in BACKUP.rglob("*") if p.is_file())
    result = prune_local_work()
    after = sum(p.stat().st_size for p in BACKUP.rglob("*") if p.is_file())

    bad = []
    mirrors = sorted(BACKUP.glob("mirrors/*.git"))
    for m in mirrors:
        fsck = repo.run(["git", "-C", str(m), "fsck", "--no-progress"], timeout=900)
        if fsck["exit"] != 0:
            bad.append(m.name)

    payload = {
        "removed": result["removed"],
        "mirrors": len(mirrors),
        "mirrors_fsck_failed": bad,
        "backup_bytes": after,
        "backup_unchanged": before == after,
        "ok": not bad and before == after,
    }
    (ROOT / "LOGS" / "prune_work.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
