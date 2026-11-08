"""scripts/build_now.py — build every production repo from its mapped source.

This is the "new take" build. For each row of tools.abx.repos24 with a local
source it:

  1. prepares a clean staging tree (robocopy, minus VCS/build/cache dirs),
  2. drops a generated PROVENANCE.md saying where the tree came from and when,
  3. runs the secret gate (tracked secrets only are fatal),
  4. publishes to the mapped repo/branch and proves the remote SHA.

A row is only "built" when the remote SHA read back from the GitHub API equals
the local commit. Nothing is deleted here.
"""
from __future__ import annotations

import io
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from tools.abx import repo, repos24  # noqa: E402
from triage_secrets import classify  # noqa: E402

STAGE = Path(r"C:\Users\lucar\abrasax-build\stage")
EXCLUDE_DIRS = ["$RECYCLE.BIN", "System Volume Information", ".git", "__pycache__", "obj", "bin",
                "target", "node_modules", "Library", "Temp", "Logs", ".pytest_cache", ".venv"]
EXCLUDE_FILES = ["Thumbs.db", "desktop.ini"]


def _tracked_secrets(tree: Path) -> list[str]:
    """Secret-shaped files that git would actually publish from this tree."""
    found = []
    for pattern in repo.SECRET_GLOBS:
        for path in tree.rglob(pattern):
            if ".git" in path.parts:
                continue
            rel = path.relative_to(tree).as_posix()
            if classify(rel) == "IGNORE":
                continue
            found.append(rel)
    return found


def _stage(row: dict) -> Path:
    name = row["repo"]
    src = (ROOT / row["source"]).resolve()
    dest = STAGE / name
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)

    cmd = ["robocopy", str(src), str(dest), "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/R:1", "/W:1"]
    cmd += ["/XD"] + EXCLUDE_DIRS
    cmd += ["/XF"] + EXCLUDE_FILES
    if src == ROOT:
        # the canonical tree: never lift the sibling repo mirrors or releases
        cmd += ["/XD", str(ROOT / "BUILD"), str(ROOT / "dist"), str(ROOT / ".venv"),
                str(ROOT / "LOGS"), str(ROOT / "ARCHIVE")]
    res = repo.run(cmd, timeout=1800)
    if res["exit"] not in (0, 1, 2, 3, 4, 5, 6, 7):
        raise RuntimeError(f"robocopy failed ({res['exit']}): {res['stderr'][:300]}")
    return dest


def _provenance(row: dict, dest: Path) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    head = repo.run(["git", "-C", str(ROOT), "log", "-1", "--format=%H %s"], timeout=60)["stdout"].strip()
    body = f"""# Provenance - {row['repo']}

Generated production tree. Do not hand-edit the header; regenerate it.

| field | value |
|---|---|
| repo | `{row['repo']}` |
| kind | `{row['kind']}` |
| source tree | `{row['source']}` |
| built at | {ts} |
| built from ABRASAX-REBUILD | `{head}` |
| branch | `{row['branch']}` |
| note | {row['note']} |

Built by `scripts/build_now.py` (tools.abx.repos24 plan row). Every file below
this document came from the source tree above, minus VCS metadata, build
output, caches and virtualenvs.
"""
    (dest / "PROVENANCE.md").write_text(body, encoding="utf-8")


def _publish(row: dict, dest: Path) -> dict:
    name = row["repo"]
    secrets = _tracked_secrets(dest)
    if secrets:
        return {"repo": name, "state": "blocked", "secrets": secrets[:10]}

    init = repo.run(["git", "-C", str(dest), "rev-parse", "--git-dir"], timeout=60)
    if init["exit"] != 0:
        repo.run(["git", "-C", str(dest), "init", "-q"], timeout=120)
    repo.run(["git", "-C", str(dest), "checkout", "-q", "-B", row["branch"]], timeout=120)
    if not repo.run(["git", "-C", str(dest), "config", "user.email"], timeout=60)["stdout"].strip():
        repo.run(["git", "-C", str(dest), "config", "user.email", "basedgod55hjl@users.noreply.github.com"], timeout=60)
        repo.run(["git", "-C", str(dest), "config", "user.name", "basedgod55hjl"], timeout=60)

    repo.run(["git", "-C", str(dest), "remote", "remove", "origin"], timeout=60)
    url = "https://github.com/basedgod55hjl/" + name + ".git"
    repo.run(["git", "-C", str(dest), "remote", "add", "origin", url], timeout=60)

    msg = f"build: {name} from {row['source']} ({row['kind']})"
    res = repo.sync(path=str(dest), branch=row["branch"], message=msg)
    return {
        "repo": name,
        "state": "published" if res.ok else "failed",
        "local_sha": res.data.get("local_sha"),
        "remote_sha": res.data.get("remote_sha"),
        "matches": res.data.get("matches"),
        "errors": res.errors[:3],
        "files": sum(1 for p in dest.rglob("*") if p.is_file()),
        "bytes": sum(p.stat().st_size for p in dest.rglob("*") if p.is_file()),
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dry = "--dry-run" in argv
    names = [a for a in argv if not a.startswith("--")]
    only = names[0] if names else None

    STAGE.mkdir(parents=True, exist_ok=True)
    rows = [r for r in repos24.ROWS if r.get("source") and r["kind"] in ("production", "shell")]
    if only:
        rows = [r for r in rows if r["repo"] == only]
    if not rows:
        sys.stdout.write(json.dumps({"ok": False, "error": f"no buildable row matched {only!r}"}) + "\n")
        return 2

    results = []
    for row in rows:
        name = row["repo"]
        try:
            dest = _stage(row)
            _provenance(row, dest)
        except Exception as exc:  # noqa: BLE001
            results.append({"repo": name, "state": "failed", "error": f"{type(exc).__name__}: {exc}"})
            sys.stdout.write(f"{name:<28} STAGE-FAILED {exc}\n")
            sys.stdout.flush()
            continue
        if dry:
            results.append({"repo": name, "state": "staged", "path": str(dest),
                            "files": sum(1 for p in dest.rglob("*") if p.is_file())})
            sys.stdout.write(f"{name:<28} staged {dest}\n")
            continue
        out = _publish(row, dest)
        results.append(out)
        sys.stdout.write(f"{name:<28} {out['state']:<10} sha={str(out.get('remote_sha'))[:12]} "
                         f"match={out.get('matches')} files={out.get('files')}\n")
        sys.stdout.flush()

    payload = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "results": results}
    (ROOT / "LOGS" / "build_repos.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    ok = [r for r in results if r["state"] == "published"]
    bad = [r for r in results if r["state"] not in ("published", "staged")]
    sys.stdout.write(f"\nBUILD {len(ok)}/{len(results)} published  failed={[r['repo'] for r in bad]}\n")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
