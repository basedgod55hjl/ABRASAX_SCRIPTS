#!/usr/bin/env python3
"""dedupe.py - reversible duplicate consolidation for the ABRASAX archive roots.

Moves *byte-identical* duplicates out of C:\\ABRASAX\\ARCHIVE and C:\\ABRASAX\\_VAULT
into an external archive root (default J:\\ABRASAX-ARCHIVE\\dedupe-20261017), keeping
the original relative path, writing a JSONL manifest and leaving a
``<name>.dedupe-moved`` note beside every path that was emptied.

Guarantees
----------
* Never deletes. A file is only moved after the destination copy has been
  re-hashed and matches the source sha256.
* Never touches live code (anything outside ARCHIVE/ and _VAULT/), and never
  touches C:\\Users\\sirch\\Desktop.
* A file is only moved when a byte-identical copy is retained somewhere outside
  the move scope (live tree) -- or, with --allow-archive-internal, when an
  identical copy is kept in place inside ARCHIVE/_VAULT.
* --apply refuses to run unless the destination is writable and has >= 5 GB free.
* Dry run is the default; --apply is required to change anything.

Usage
-----
  python dedupe.py                    # dry run, prints the plan
  python dedupe.py --json plan.json   # dry run + machine-readable plan
  python dedupe.py --apply            # execute the plan

Exit codes: 0 ok/no-op, 2 refused (preflight), 3 partial (some moves failed).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from collections import defaultdict

ROOT = r"C:\ABRASAX"
MOVE_ROOTS = [os.path.join(ROOT, "ARCHIVE"), os.path.join(ROOT, "_VAULT")]
DEST_ROOT = r"J:\ABRASAX-ARCHIVE\dedupe-20261017"
MARKER_SUFFIX = ".dedupe-moved"
MAX_HASH_BYTES = 2 * 1024 * 1024          # ignore files larger than this
MIN_FREE_BYTES = 5 * 1024 * 1024 * 1024   # 5 GB guard on the destination
SKIP_DIRS = {
    "node_modules", "target", ".git", "__pycache__", ".venv", "venv", ".venv_gui",
    ".pytest_cache", ".mypy_cache", ".next", ".turbo", ".gradle", "system volume information",
    "$recycle.bin",
}
SKIP_EXT = {
    ".gguf", ".cubin", ".safetensors", ".onnx", ".pt", ".pth", ".so", ".dll", ".pyd",
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".mp3", ".wav", ".flac", ".m4a",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".zip", ".7z", ".rar",
    ".iso", ".img", ".vhd", ".vhdx",
}


def norm(p: str) -> str:
    return os.path.normcase(os.path.abspath(p))


def sha256_file(path: str) -> str | None:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def walk(root: str, deadline: float, max_files: int, max_depth: int = 16):
    """Yield (abspath, size) for regular files, bounded by time and count."""
    root = os.path.abspath(root)
    stack = [(root, 0)]
    n = 0
    while stack:
        if time.time() > deadline:
            return
        d, depth = stack.pop()
        try:
            it = os.scandir(d)
        except OSError:
            continue
        with it:
            for e in it:
                if n >= max_files or time.time() > deadline:
                    return
                try:
                    if e.is_dir(follow_symlinks=False):
                        if e.name.lower() in SKIP_DIRS or depth >= max_depth:
                            continue
                        stack.append((e.path, depth + 1))
                    elif e.is_file(follow_symlinks=False):
                        n += 1
                        yield e.path, e.stat(follow_symlinks=False).st_size
                except OSError:
                    continue


def collect_movable(deadline: float, max_files: int):
    out = []
    for r in MOVE_ROOTS:
        if not os.path.isdir(r):
            continue
        for p, size in walk(r, deadline, max_files):
            if size <= 0 or size > MAX_HASH_BYTES:
                continue
            if os.path.splitext(p)[1].lower() in SKIP_EXT:
                continue
            out.append((p, size))
    return out


def collect_live_index(deadline: float, max_files: int):
    """(basename, size) -> [paths] for everything outside the move scope."""
    idx = defaultdict(list)
    for top in sorted(os.listdir(ROOT)):
        p = os.path.join(ROOT, top)
        if not os.path.isdir(p) or top in ("ARCHIVE", "_VAULT"):
            continue
        for path, size in walk(p, deadline, max_files):
            if 0 < size <= MAX_HASH_BYTES:
                idx[(os.path.basename(path).lower(), size)].append(path)
    return idx


def find_live_twin(path: str, size: int, idx) -> str | None:
    """Return a live path whose bytes hash equal to *path*, else None."""
    mine = sha256_file(path)
    if not mine:
        return None
    for cand in idx.get((os.path.basename(path).lower(), size), ()):
        if sha256_file(cand) == mine:
            return cand
    return None


def plan(deadline: float, max_files: int, allow_internal: bool, max_hash_files: int):
    """Group by (basename, size) first -- that is the same practical rule fdupes
    uses -- then confirm byte identity with sha256.  Grouping by size alone on a
    679k-file corpus produces hundreds of thousands of pointless hashes on a disk
    that manages ~10-25 files/s, so the name+size key is what bounds this."""
    movable = collect_movable(time.time() + deadline / 2, max_files)
    idx = collect_live_index(time.time() + deadline / 2, max_files)
    by_key = defaultdict(list)
    for p, s in movable:
        by_key[(os.path.basename(p).lower(), s)].append(p)

    cand = []
    for (name, size), paths in by_key.items():
        live = idx.get((name, size), ())
        if live:
            cand.append((size * max(1, len(paths) - (0 if live else 1)), size, name, paths, list(live), True))
        elif allow_internal and len(paths) > 1:
            cand.append((size * (len(paths) - 1), size, name, paths, [], False))
    cand.sort(key=lambda c: -c[0])

    moves = []
    hashes = 0
    for _pot, size, name, paths, live, has_live in cand:
        if hashes >= max_hash_files or time.time() > deadline:
            break
        digests = []
        for p in paths:
            d = sha256_file(p)
            hashes += 1
            digests.append((p, d))
        by_sha = defaultdict(list)
        for p, d in digests:
            if d:
                by_sha[d].append(p)
        for d, same in by_sha.items():
            keeper = None
            for cand_path in live[:4]:
                hashes += 1
                if sha256_file(cand_path) == d:
                    keeper = cand_path
                    break
            if keeper is None and not (allow_internal and len(same) > 1):
                continue
            if keeper is None:
                keeper = sorted(same, key=lambda p: (len(p), p))[0]
            victims = [p for p in same if p != keeper]
            for v in victims:
                moves.append({
                    "src": v, "keeper": keeper, "sha256": d,
                    "size": size, "cls": "SAFE" if has_live else "ARCHIVE-INTERNAL",
                })
    return moves, len(movable), len(idx)


def preflight(dest_root: str, need_bytes: int) -> tuple[bool, str]:
    drive = os.path.splitdrive(os.path.abspath(dest_root))[0] + "\\"
    if not os.path.exists(drive):
        return False, f"destination drive {drive} does not exist"
    try:
        os.makedirs(dest_root, exist_ok=True)
        probe = os.path.join(dest_root, ".write-probe")
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("ok")
        os.remove(probe)
    except OSError as exc:
        return False, f"destination {dest_root} is not writable: {exc}"
    free = shutil.disk_usage(dest_root).free
    if free < MIN_FREE_BYTES:
        return False, f"only {free/1e9:.2f} GB free on {drive} (< 5 GB)"
    if free < need_bytes:
        return False, f"need {need_bytes/1e9:.2f} GB but only {free/1e9:.2f} GB free"
    return True, f"destination ok, {free/1e9:.1f} GB free"


def do_move(src: str, dest_root: str, digest: str) -> str:
    rel = os.path.relpath(src, ROOT)
    dest = os.path.join(dest_root, rel)
    if os.path.exists(dest):
        if sha256_file(dest) == digest:
            return dest  # already moved in an earlier pass
        raise FileExistsError(f"destination exists with different content: {dest}")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(src, dest)
    if sha256_file(dest) != digest:
        raise OSError(f"post-copy hash mismatch: {dest}")
    os.remove(src)
    marker = src + MARKER_SUFFIX
    with open(marker, "w", encoding="utf-8") as fh:
        fh.write(
            "moved by dedupe.py on %s\n"
            "original: %s\nnew path: %s\nsha256: %s\nbytes: %d\n"
            "restore: copy the new path back over this marker and delete it.\n"
            % (time.strftime("%Y-%m-%d %H:%M:%S"), src, dest, digest,
               os.path.getsize(dest))
        )
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="explicit dry run (this is the default; kept for scripting)")
    ap.add_argument("--apply", action="store_true", help="execute the plan (default: dry run)")
    ap.add_argument("--dest", default=DEST_ROOT)
    ap.add_argument("--budget", type=float, default=600.0, help="seconds per scan pass")
    ap.add_argument("--max-files", type=int, default=500000)
    ap.add_argument("--allow-archive-internal", action="store_true",
                    help="also move duplicates whose only surviving copy is inside ARCHIVE/_VAULT")
    ap.add_argument("--max-hash-files", type=int, default=4000,
                    help="stop after this many sha256 reads (disk here does ~10-25 files/s)")
    ap.add_argument("--json", metavar="FILE", help="write the plan/summary as JSON")
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    t0 = time.time()
    deadline = t0 + args.budget
    moves, n_movable, n_live = plan(deadline, args.max_files,
                                    args.allow_archive_internal, args.max_hash_files)

    total = sum(m["size"] for m in moves)
    print(f"scanned {n_movable} movable files, {n_live} live index keys")
    print(f"planned moves: {len(moves)} files, {total/1e6:.2f} MB")
    for m in sorted(moves, key=lambda x: -x["size"])[: args.top]:
        print(f"  {m['size']:>9} B  {m['cls']:<16} {m['src']}")
        print(f"             -> {m['keeper']}")

    summary = {
        "mode": "apply" if args.apply else "dry-run",
        "scanned_movable": n_movable,
        "planned_files": len(moves),
        "planned_bytes": total,
        "dest": args.dest,
        "moves": moves,
    }

    if not args.apply:
        print("\nDRY RUN - nothing moved. Re-run with --apply to execute.")
        if args.json:
            json.dump(summary, open(args.json, "w", encoding="utf-8"), indent=1)
        return 0

    if not moves:
        print("nothing to move")
        if args.json:
            json.dump(summary, open(args.json, "w", encoding="utf-8"), indent=1)
        return 0

    ok, msg = preflight(args.dest, int(total * 1.02) + 64 * 1024 * 1024)
    if not ok:
        print(f"REFUSED: {msg}", file=sys.stderr)
        return 2
    print(f"preflight: {msg}")

    manifest = os.path.join(args.dest, "manifest.jsonl")
    done = failed = 0
    moved_bytes = 0
    with open(manifest, "a", encoding="utf-8") as mf:
        for m in moves:
            try:
                dest = do_move(m["src"], args.dest, m["sha256"])
            except Exception as exc:  # keep going, report at the end
                failed += 1
                print(f"FAILED {m['src']}: {exc}", file=sys.stderr)
                continue
            mf.write(json.dumps({
                "old_path": m["src"], "new_path": dest, "sha256": m["sha256"],
                "bytes": m["size"], "kept_copy": m["keeper"],
                "moved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }) + "\n")
            mf.flush()
            done += 1
            moved_bytes += m["size"]

    summary.update({"moved_files": done, "moved_bytes": moved_bytes,
                    "failed": failed, "manifest": manifest})
    print(f"\napplied: {done} moved, {failed} failed, {moved_bytes/1e6:.2f} MB")
    print(f"manifest: {manifest} ({done} lines)")
    if args.json:
        json.dump(summary, open(args.json, "w", encoding="utf-8"), indent=1)
    return 0 if failed == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
