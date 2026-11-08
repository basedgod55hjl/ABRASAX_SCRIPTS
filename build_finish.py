"""scripts/build_finish.py — finish the production build correctly.

The first build pass created fresh local histories and was rejected by GitHub
because the remotes already contain history (`fetch first`). The right way to
refresh a production repo from a local tree is:

    clone the remote  ->  replace the worktree  ->  commit  ->  push (fast-forward)

This rewrites the failed rows that way. Rows already published (empty shells)
are skipped. The canonical tree (ABRASAX-REBUILD) keeps its own repo and is
pushed through scripts/publish_now.py, not rebuilt.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from tools.abx import repo, repos24  # noqa: E402
from build_now import EXCLUDE_DIRS, EXCLUDE_FILES, _provenance, _tracked_secrets  # noqa: E402

WORK = Path(r"C:\Users\lucar\abrasax-build\work")
PUBLISHED_SKIP = {"ABRASAX-REBUILD", "ABRASAX-ecosystem-v2", "ABRASAX-core-v2",
                  "OSIRISBLXCK-CORE-v2", "ABRASAX-SWARM-ABRASAX"}


def _sync_into(repo_dir: Path, src: Path) -> None:
    """Replace everything in the clone except .git with the source tree."""
    for child in repo_dir.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)
    cmd = ["robocopy", str(src), str(repo_dir), "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/R:1", "/W:1"]
    cmd += ["/XD"] + EXCLUDE_DIRS + ["/XF"] + EXCLUDE_FILES
    if src == ROOT:
        cmd += ["/XD", str(ROOT / "BUILD"), str(ROOT / "dist"), str(ROOT / ".venv"),
                str(ROOT / "LOGS"), str(ROOT / "ARCHIVE")]
    res = repo.run(cmd, timeout=3600)
    if res["exit"] not in (0, 1, 2, 3, 4, 5, 6, 7):
        raise RuntimeError(f"robocopy {res['exit']}: {res['stderr'][:200]}")


def main(argv: list[str] | None = None) -> int:
    names = [a for a in (sys.argv[1:] if argv is None else argv) if not a.startswith("--")]
    rows = [r for r in repos24.ROWS
            if r.get("source") and r["kind"] in ("production", "shell")
            and r["repo"] not in PUBLISHED_SKIP and (not names or r["repo"] in names)]
    WORK.mkdir(parents=True, exist_ok=True)

    results = []
    for row in rows:
        name = row["repo"]
        src = (ROOT / row["source"]).resolve()
        dest = WORK / name
        try:
            if (dest / ".git").exists():
                shutil.rmtree(dest, ignore_errors=True)
            clone = repo.run(["git", "clone", "--quiet",
                              "--branch", row["branch"],
                              f"https://github.com/basedgod55hjl/{name}.git", str(dest)], timeout=1800)
            if clone["exit"] != 0:
                results.append({"repo": name, "state": "failed", "error": f"clone: {clone['stderr'][:200]}"})
                sys.stdout.write(f"{name:<26} CLONE-FAILED\n")
                continue
            _sync_into(dest, src)
            _provenance(row, dest)
            secrets = _tracked_secrets(dest)
            if secrets:
                results.append({"repo": name, "state": "blocked", "secrets": secrets[:10]})
                sys.stdout.write(f"{name:<26} BLOCKED secrets={secrets[:3]}\n")
                continue
            out = repo.sync(path=str(dest), branch=row["branch"],
                            message=f"build: {name} from {row['source']} ({row['kind']})")
            row_out = {"repo": name, "state": "published" if out.ok else "failed",
                       "local_sha": out.data.get("local_sha"),
                       "remote_sha": out.data.get("remote_sha"),
                       "matches": out.data.get("matches"),
                       "errors": out.errors[:2]}
            results.append(row_out)
            sys.stdout.write(f"{name:<26} {row_out['state']:<10} "
                             f"sha={str(row_out.get('remote_sha'))[:12]} match={row_out.get('matches')}\n")
            sys.stdout.flush()
        except Exception as exc:  # noqa: BLE001
            results.append({"repo": name, "state": "failed", "error": f"{type(exc).__name__}: {exc}"})
            sys.stdout.write(f"{name:<26} EXCEPTION {exc}\n")

    payload = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "results": results}
    (ROOT / "LOGS" / "build_finish.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    bad = [r["repo"] for r in results if r["state"] != "published"]
    sys.stdout.write(f"\nFINISH {len(results) - len(bad)}/{len(results)} published failed={bad}\n")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
