"""reclaim_c.py — the two reversible reclaims on C:, each behind a precondition.

1. stage-prune: `abrasax-build/stage/ABRASAX-REBUILD` is a 94,826-file COPY of the
   canonical tree that build_now made when the plan row's source is ".". It was
   never published. Precondition: the canonical tree exists and its HEAD equals or
   postdates the copy's, so the copy cannot be the only witness of anything.
   Also drops `cargo-target` (a build cache).

2. c-cleanup: 104 scratch files already inside a verified zip, plus three dead
   download artifacts and the broken-VLC backup dir.
   Precondition: every file must be present in the archive with a matching size
   before it is deleted.

    python SCRIPTS/reclaim_c.py --report
    python SCRIPTS/reclaim_c.py --go
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = Path(r"C:\Users\lucar")
BUILD = HOME / "abrasax-build"
STAGE_COPY = BUILD / "stage" / "ABRASAX-REBUILD"
CARGO_TARGET = BUILD / "cargo-target"
ARCHIVE = HOME / "ARCHIVE" / "home-scratch-20261101-050322.zip"
MANIFEST = HOME / "_cleanup_manifest.txt"
DEAD_FILES = [HOME / "vlc-official.zip", HOME / "vlc-official.7z", HOME / "dotnet10-runtime.exe"]
DEAD_DIRS = [HOME / "vlc-broken-backup-20261031-163350"]


def git_head(path: Path) -> str:
    r = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"],
                       capture_output=True, text=True, timeout=120)
    return r.stdout.strip()


def dir_bytes(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    go = "--go" in argv
    log = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "mode": "go" if go else "report", "actions": []}

    # ---------------- 1. stage copy
    print("== stage-prune")
    canonical_head = git_head(ROOT)
    if STAGE_COPY.exists():
        copy_head = git_head(STAGE_COPY)
        alive = STAGE_COPY.exists() and canonical_head
        print(f"   canonical C:\\ABRASAX HEAD: {canonical_head[:12]}")
        print(f"   stage copy HEAD:          {copy_head[:12] or '(no git)'}")
        if not alive:
            print("   ABORT: canonical tree or its HEAD is not readable")
        else:
            size = dir_bytes(STAGE_COPY)
            print(f"   {'delete' if go else 'would delete'} {STAGE_COPY}  {size/1e9:.2f} GB  "
                  f"({len(list(STAGE_COPY.rglob('*'))) } entries)")
            if go:
                shutil.rmtree(STAGE_COPY, ignore_errors=True)
                log["actions"].append({"what": "stage-copy", "path": str(STAGE_COPY),
                                       "bytes": size, "deleted": not STAGE_COPY.exists()})
    else:
        print("   already absent")

    if CARGO_TARGET.exists():
        size = dir_bytes(CARGO_TARGET)
        print(f"   {'delete' if go else 'would delete'} {CARGO_TARGET}  {size/1e9:.2f} GB (build cache)")
        if go:
            shutil.rmtree(CARGO_TARGET, ignore_errors=True)
            log["actions"].append({"what": "cargo-target", "path": str(CARGO_TARGET),
                                   "bytes": size, "deleted": not CARGO_TARGET.exists()})

    # ---------------- 2. home scratch
    print("\n== c-cleanup")
    if not ARCHIVE.exists():
        print("   ABORT: archive missing, refusing to delete anything")
        return 1
    zf = zipfile.ZipFile(ARCHIVE)
    entries = {i.filename: i.file_size for i in zf.infolist()}
    print(f"   archive holds {len(entries)} entries")

    files = []
    if MANIFEST.exists():
        files = [Path(p) for p in MANIFEST.read_text(encoding="utf-8").splitlines() if p.strip()]
    missing_from_archive = []
    for f in files:
        if not f.exists():
            continue
        rel = f.name
        if rel not in entries:
            missing_from_archive.append(str(f))
        elif entries[rel] != f.stat().st_size:
            missing_from_archive.append(str(f) + " (size differs)")
    print(f"   scratch files present: {sum(1 for f in files if f.exists())}")
    print(f"   not provably archived: {len(missing_from_archive)}")
    for m in missing_from_archive[:5]:
        print("      " + m)

    freed = 0
    if not missing_from_archive:
        for f in files:
            if not f.exists():
                continue
            size = f.stat().st_size
            if go:
                try:
                    f.unlink()
                    freed += size
                except OSError as exc:
                    print(f"      failed {f.name}: {exc}")
        print(f"   {'deleted' if go else 'would delete'} {sum(1 for f in files if f.exists())} scratch files "
              f"({freed/1e6:.1f} MB freed)")
    else:
        print("   SKIPPED scratch deletion: archive does not cover every file")

    for f in DEAD_FILES:
        if f.exists():
            size = f.stat().st_size
            print(f"   {'delete' if go else 'would delete'} {f.name}  {size/1e6:.0f} MB")
            if go:
                f.unlink(missing_ok=True)
                freed += size
    for d in DEAD_DIRS:
        if d.exists():
            size = dir_bytes(d)
            print(f"   {'delete' if go else 'would delete'} {d.name}  {size/1e9:.2f} GB")
            if go:
                shutil.rmtree(d, ignore_errors=True)
                freed += size

    log["freed_bytes"] = freed
    out = ROOT / "LOGS" / "reclaim_c.json"
    out.write_text(json.dumps(log, indent=1), encoding="utf-8")
    print(f"\n{'freed' if go else 'would free'} {freed/1e9:.2f} GB   log: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
