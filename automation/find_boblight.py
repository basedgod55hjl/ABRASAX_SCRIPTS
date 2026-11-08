"""Locate any file matching *oblight*, safely and testably.

Three bugs this replaces, each found by running the previous version:
  1. `'J:\\\\'` produced a doubled backslash -> os.walk followed a junction cycle
     -> RecursionError after ~1000 levels.
  2. `os.stat()` on a child raised FileNotFoundError for a directory whose name
     ends in a space (`...\\Gabby `) -- Windows strips trailing spaces on path
     normalisation, so the path we stat is not the path on disk.
  3. os.walk gives no per-entry error handling, so ONE unreadable directory
     aborts the whole drive scan.

The fix is a non-recursive scandir walk where every filesystem call is inside
`try/except OSError`. `walk()` is a pure generator so TESTS/python/
test_find_boblight.py can prove it against fixtures instead of a live drive.
"""
from __future__ import annotations

import os
import sys

DEFAULT_ROOTS = [r"C:\Users\lucar", "J:/", r"C:\ABRASAX", r"C:\ProgramData"]

PRUNE = {"node_modules", ".git", "__pycache__", "WinSxS", "System32",
         "Installer", "$RECYCLE.BIN", "System Volume Information"}

MAX_DEPTH = 12

# FILE_ATTRIBUTE_REPARSE_POINT
_REPARSE = 0x400

NEEDLE = "oblight"


def _is_reparse(entry: os.DirEntry) -> bool:
    """True for junctions / symlinks. Never walk these -- they can cycle."""
    try:
        st = entry.stat(follow_symlinks=False)
    except OSError:
        return True
    return bool(getattr(st, "st_file_attributes", 0) & _REPARSE)


def walk(root: str, max_depth: int = MAX_DEPTH, prune=PRUNE,
         keep_dirs: bool = False):
    """Yield file paths under `root` whose name contains NEEDLE (case-insensitive).

    Iterative, depth-capped, pruned, cycle-proof. Any unreadable entry is
    skipped rather than aborting the walk.

    NOTE ON COLLIDING PRUNES: ``PRUNE`` contains bare basenames, so it prunes
    *any* directory with that name. ``Installer`` is a real example -- it is
    the Windows MSI cache, but ``C:\\Program Files (x86)\\Ubisoft\\...\\Installer``
    is also pruned by it. Pass ``prune=set()`` for a full-depth sweep.

    ``keep_dirs`` also matches *directory* names, not just files. Directories
    whose name matches are yielded but not descended into -- that is what makes
    an "is it anywhere at all" sweep fast: pruning ``Assembly-CSharp.dll``-style
    cache trees while still reporting the directory itself.
    """
    root = os.path.normpath(root)
    if not os.path.isdir(root):
        return
    stack: list[tuple[str, int]] = [(root, 0)]
    while stack:
        dp, depth = stack.pop()
        try:
            entries = list(os.scandir(dp))
        except OSError:
            continue
        for e in entries:
            try:
                if e.is_dir(follow_symlinks=False):
                    if keep_dirs and NEEDLE in e.name.lower():
                        yield e.path
                    if depth + 1 > max_depth:
                        continue
                    if e.name in prune or e.name.startswith("$"):
                        continue
                    if _is_reparse(e):
                        continue
                    stack.append((e.path, depth + 1))
                elif NEEDLE in e.name.lower():
                    yield e.path
            except OSError:
                # Unreadable / vanished / name-normalisation mismatch.
                continue

def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    shallow = "--shallow" in argv
    full = "--full" in argv
    argv = [a for a in argv if not a.startswith("--")]
    # A shallow pass must not be depth-capped by MAX_DEPTH, or it never reaches
    # the deep AppData/Programs trees where game installs live.
    max_depth = 64 if shallow else MAX_DEPTH
    prune = set() if full else PRUNE
    roots = argv or DEFAULT_ROOTS
    hits: list[tuple[int, str]] = []
    for root in roots:
        root = os.path.normpath(root)
        if not os.path.isdir(root):
            print(f"skip (absent): {root}", flush=True)
            continue
        print(f"scan: {root}", flush=True)
        for p in walk(root, max_depth=max_depth, prune=prune,
                      keep_dirs=shallow):
            try:
                hits.append((os.path.getsize(p), p))
            except OSError:
                hits.append((0, p))
    print(f"\nmatches: {len(hits)}", flush=True)
    for sz, p in sorted(hits, key=lambda t: (-t[0], t[1]))[:25]:
        kind = "DIR " if os.path.isdir(p) else "    "
        print(f"  {kind}{sz / 1024:10.1f} KB  {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
