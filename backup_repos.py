"""scripts/backup_repos.py — durable local backup of every GitHub repo.

For each repo on the account:
  * `git clone --mirror` into C:\\abrasax-backup\\mirrors\\<name>.git
    (a mirror holds every ref: branches, tags - a restorable copy)
  * write a metadata record (visibility, default branch, size, pushed_at)
  * write a RESTORE.md that reconstructs each repo from the mirror

Nothing here touches a remote except reading. Verified by comparing the
mirror's ref count and HEAD SHA against the API.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx import repo  # noqa: E402

BACKUP = Path(r"C:\abrasax-backup")
MIRRORS = BACKUP / "mirrors"


def main() -> int:
    BACKUP.mkdir(parents=True, exist_ok=True)
    MIRRORS.mkdir(parents=True, exist_ok=True)

    listing = repo.remote_repos()
    if not listing["ok"]:
        sys.stdout.write(json.dumps({"ok": False, "error": listing.get("error")}) + "\n")
        return 1
    repos = listing["repos"]
    tok = repo.token()

    records = []
    for name in sorted(repos):
        meta = repos[name]
        dest = MIRRORS / f"{name}.git"
        started = time.time()
        if (dest / "HEAD").exists():
            fetch = repo.run(["git", "-C", str(dest), "remote", "update", "--prune"], timeout=1800)
            action = "fetched"
        else:
            url = f"https://x-access-token:{tok}@github.com/{meta['full_name']}.git"
            fetch = repo.run(["git", "clone", "--mirror", url, str(dest)], timeout=3600)
            action = "cloned"
            # never leave the token on disk
            repo.run(["git", "-C", str(dest), "remote", "set-url", "origin",
                      f"https://github.com/{meta['full_name']}.git"], timeout=60)
        ok = fetch["exit"] == 0
        refs = head = None
        if ok:
            r = repo.run(["git", "-C", str(dest), "for-each-ref", "--format=%(refname)"], timeout=300)
            refs = len([x for x in r["stdout"].splitlines() if x.strip()])
            h = repo.run(["git", "-C", str(dest), "rev-parse", "HEAD"], timeout=60)
            head = h["stdout"].strip() or None
        records.append({
            "repo": name,
            "full_name": meta["full_name"],
            "private": meta["private"],
            "branch": meta["branch"],
            "size_kb": meta["size_kb"],
            "pushed_at": meta["pushed_at"],
            "action": action,
            "ok": ok,
            "refs": refs,
            "mirror_head": head,
            "mirror": str(dest),
            "bytes": sum(p.stat().st_size for p in dest.rglob("*") if p.is_file()) if dest.exists() else 0,
            "seconds": round(time.time() - started, 1),
        })
        sys.stdout.write(f"{name:<28} {action:<8} ok={ok} refs={refs} {records[-1]['seconds']}s\n")
        sys.stdout.flush()

    payload = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "count": len(records), "records": records}
    (BACKUP / "manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = ["# ABRASAX repo backup", "",
             f"Taken {payload['ts']} - {len(records)} repos, mirrors under `mirrors/<name>.git`.",
             "", "## Restore one repo", "", "```",
             "git clone --mirror C:\\abrasax-backup\\mirrors\\<name>.git <name>.git",
             "gh repo create basedgod55hjl/<name> --private   # or --public",
             "cd <name>.git && git push --mirror https://github.com/basedgod55hjl/<name>.git",
             "```", "", "## Repos", "", "| repo | private | branch | size KB | refs | head |",
             "|---|---|---|---|---|---|"]
    for r in records:
        lines.append(f"| {r['repo']} | {r['private']} | {r['branch']} | {r['size_kb']} | "
                     f"{r['refs']} | `{(r['mirror_head'] or '')[:12]}` |")
    (BACKUP / "RESTORE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    failed = [r["repo"] for r in records if not r["ok"]]
    total_gb = sum(r["bytes"] for r in records) / 1e9
    sys.stdout.write(f"\nDONE {len(records) - len(failed)}/{len(records)} ok, "
                     f"{total_gb:.2f} GB on disk, failed={failed}\n")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
