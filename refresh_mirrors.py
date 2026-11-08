"""scripts/refresh_mirrors.py — bring mirrors up to the live remote SHA.

Run this after any build/publish and *before* any delete: the delete gate
refuses a repo whose mirror HEAD is not the live remote HEAD, which is exactly
the guarantee that makes deletion safe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx import repo  # noqa: E402

MIRRORS = Path(r"C:\abrasax-backup\mirrors")


def main(argv: list[str] | None = None) -> int:
    names = [a for a in (sys.argv[1:] if argv is None else argv) if not a.startswith("--")]
    listing = repo.remote_repos()
    if not listing["ok"]:
        sys.stdout.write(json.dumps({"ok": False, "error": listing.get("error")}) + "\n")
        return 1
    rows = []
    bad = []
    for name in sorted(listing["repos"]):
        if names and name not in names:
            continue
        meta = listing["repos"][name]
        mirror = MIRRORS / f"{name}.git"
        if not mirror.exists():
            clone = repo.run(["git", "clone", "--mirror",
                              f"https://github.com/{meta['full_name']}.git", str(mirror)], timeout=7200)
            action = "cloned"
        else:
            clone = repo.run(["git", "-C", str(mirror), "remote", "update", "--prune"], timeout=7200)
            action = "updated"
        ok = clone["exit"] == 0
        head = repo.run(["git", "-C", str(mirror), "rev-parse", "HEAD"], timeout=120)["stdout"].strip()
        live = repo.remote_head(meta["full_name"], meta["branch"]).get("sha")
        match = (head == live) if live else None
        rows.append({"repo": name, "action": action, "git_ok": ok, "mirror_head": head,
                     "remote_sha": live, "match": match})
        if not ok or match is False:
            bad.append(name)
        sys.stdout.write(f"{name:<26} {action:<8} match={match}\n")
        sys.stdout.flush()

    payload = {"count": len(rows), "failed": bad, "rows": rows}
    (ROOT / "LOGS" / "refresh_mirrors.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    sys.stdout.write(f"\nREFRESH {len(rows) - len(bad)}/{len(rows)} match  failed={bad}\n")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
