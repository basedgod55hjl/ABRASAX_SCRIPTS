"""scan_mirrors_for_pat.py — does the live PAT exist in ANY repo history on this box?

A mirror holds every ref and every object of its repo, so this answers the
question GitHub's API cannot answer cheaply: which histories carry the token.

Method: enumerate every object of every mirror with `git cat-file
--batch-all-objects`, read the blobs, search the raw bytes for `github_pat_`.
Nothing is printed except repo name, hit count and the blob SHAs - never the
token itself.

    python SCRIPTS/scan_mirrors_for_pat.py                # all mirrors
    python SCRIPTS/scan_mirrors_for_pat.py ABRASAX-REBUILD
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MIRRORS = Path(r"C:\abrasax-backup\mirrors")
NEEDLE = b"github_pat_"
OUT = ROOT / "LOGS" / "pat_scan.json"


def objects(mirror: Path) -> list[tuple[str, str, str]]:
    r = subprocess.run(["git", "-C", str(mirror), "cat-file", "--batch-all-objects",
                        "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
                       capture_output=True, text=True, timeout=3600)
    out = []
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) == 3:
            out.append((parts[0], parts[1], parts[2]))
    return out


def scan(mirror: Path) -> dict:
    t0 = time.time()
    objs = objects(mirror)
    blobs = [(sha, size) for sha, typ, size in objs if typ == "blob"]
    hits = []
    # read in batches: one cat-file --batch process, feed it SHAs
    if blobs:
        proc = subprocess.Popen(["git", "-C", str(mirror), "cat-file", "--batch"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        try:
            for sha, _size in blobs:
                proc.stdin.write((sha + "\n").encode())
                proc.stdin.flush()
                header = proc.stdout.readline().split()
                if not header or len(header) < 3:
                    continue
                size = int(header[2])
                data = proc.stdout.read(size)
                proc.stdout.read(1)  # trailing newline
                if NEEDLE in data:
                    hits.append(sha)
        finally:
            proc.stdin.close()
            proc.kill()
    return {"repo": mirror.name.replace(".git", ""), "objects": len(objs),
            "blobs": len(blobs), "hits": hits, "seconds": round(time.time() - t0, 1)}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    names = argv or [p.name for p in sorted(MIRRORS.glob("*.git"))]
    results = []
    for name in names:
        m = MIRRORS / (name if name.endswith(".git") else name + ".git")
        if not m.exists():
            print(f"{name:<26} MISSING MIRROR")
            continue
        res = scan(m)
        results.append(res)
        flag = f"HIT x{len(res['hits'])}" if res["hits"] else "clean"
        print(f"{res['repo']:<26} {res['objects']:>7} objects  {res['blobs']:>7} blobs  "
              f"{flag:<10} {res['seconds']}s", flush=True)
        OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
    dirty = [r["repo"] for r in results if r["hits"]]
    print(f"\nscanned {len(results)} mirrors; histories containing the PAT: {dirty or 'none'}")
    print(f"log: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
