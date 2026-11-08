"""Rotate disposable logs; never delete a live ledger.

MEASURED (audit_tree.py):
    LOGS total        339 files, 22.49 MB
    LIVE ledgers        7 files,  0.98 MB   <- 4 of them written 0 min ago
    EVIDENCE           32 files,  3.19 MB
    DISPOSABLE         63 files, 16.73 MB   <- epic-install.log alone is 12.48 MB

Design rules, because a log cleaner is easy to get catastrophically wrong:

  1  LIVE ledgers are never touched. Four had a write in the last 60 seconds; a
     writer may hold the handle, and deleting or truncating it corrupts the record
     the rest of the system reads.
  2  Rotation, not deletion. Disposable logs are gzipped into
     LOGS/archive/YYYYMM/ and the original removed only after the gzip is verified
     to decompress to the same length. If verification fails, the original stays.
  3  Files modified in the last 10 minutes are left alone -- they may be an
     in-progress build the user wants to read.
  4  Nothing outside LOGS is considered.
  5  --apply required. Default is a dry run with an exact byte count.

Usage:
    python rotate_logs.py              # dry run
    python rotate_logs.py --apply
"""
import gzip
import os
import shutil
import sys
import time

ROOT = r"C:\ABRASAX"
LOGS = os.path.join(ROOT, "LOGS")
ARCHIVE = os.path.join(LOGS, "archive")

# exactly the set verified in audit_tree.py
LIVE_LEDGERS = {
    "supervisor-ledger.jsonl", "supervisor-state.json", "ops-state.json",
    "alive-bind.jsonl", "mem-governor.jsonl", "build-queue.jsonl",
    "gateway-server.log",
}

# evidence cited by documents: keep in place, they are small
KEEP_SUBSTR = ("overlay_shot", "hud-screen", "hud-v2", "pytest-", "suite")

# A file named svc-<service>.log is owned by a running service by convention. The
# first --apply run hit seven of these and only found out by catching WinError 32.
SERVICE_LOG_PREFIX = "svc-"

DISPOSABLE_EXT = (".log",)
DISPOSABLE_SUBSTR = (".bak-",)
MIN_AGE_MINUTES = 10
APPLY = "--apply" in sys.argv


def is_disposable(name: str) -> bool:
    if name in LIVE_LEDGERS:
        return False
    if name.startswith(SERVICE_LOG_PREFIX):
        return False      # owned by a live service; it appends whenever it logs
    if any(k in name for k in KEEP_SUBSTR):
        return False
    if name.startswith("_"):
        return True
    if name.endswith(DISPOSABLE_EXT):
        return True
    if any(s in name for s in DISPOSABLE_SUBSTR):
        return True
    return False


def main() -> int:
    now = time.time()
    plan = []
    skipped_live = 0
    skipped_recent = 0

    for dp, dn, fns in os.walk(LOGS):
        dn[:] = [d for d in dn if d not in ("__pycache__", "archive")]
        for fn in fns:
            full = os.path.join(dp, fn)
            if fn in LIVE_LEDGERS:
                skipped_live += 1
                continue
            if not is_disposable(fn):
                continue
            try:
                st = os.stat(full)
            except OSError:
                continue
            if st.st_size == 0:
                # Archiving nothing produces a 20-40 byte gzip and makes the
                # archive count misleading. An empty log has nothing to preserve.
                skipped_recent += 1
                continue
            age_min = (now - st.st_mtime) / 60
            if age_min < MIN_AGE_MINUTES:
                skipped_recent += 1
                continue
            plan.append((full, st.st_size, age_min))

    plan.sort(key=lambda t: -t[1])
    total = sum(p[1] for p in plan)

    print(f"=== ROTATION PLAN ({'APPLY' if APPLY else 'DRY RUN'}) ===")
    print(f"  live ledgers skipped      : {skipped_live}")
    print(f"  modified <{MIN_AGE_MINUTES} min, skipped : {skipped_recent}")
    print(f"  files to rotate           : {len(plan)}")
    print(f"  bytes to reclaim          : {total:,} ({total / 1e6:.2f} MB)")
    for full, size, age in plan[:12]:
        print(f"    {size / 1e6:8.2f} MB  {age:6.1f} min old  "
              f"{os.path.relpath(full, LOGS)}")
    if len(plan) > 12:
        print(f"    ... and {len(plan) - 12} more")

    if not APPLY:
        print("\ndry run -- re-run with --apply to gzip into LOGS/archive/YYYYMM/")
        return 0

    stamp = time.strftime("%Y%m")
    dest_dir = os.path.join(ARCHIVE, stamp)
    os.makedirs(dest_dir, exist_ok=True)

    rotated = 0
    reclaimed = 0
    failed = []

    for full, size, _age in plan:
        rel = os.path.relpath(full, LOGS).replace(os.sep, "_")
        dest = os.path.join(dest_dir, rel + ".gz")
        try:
            raw = open(full, "rb").read()
            with gzip.open(dest, "wb", compresslevel=6) as gz:
                gz.write(raw)
            # verify before removing the original
            back = gzip.open(dest, "rb").read()
            if len(back) != len(raw):
                failed.append((full, "gzip round-trip length mismatch"))
                os.remove(dest)
                continue
            os.remove(full)
            rotated += 1
            reclaimed += size
        except OSError as e:
            failed.append((full, str(e)))

    print(f"\nrotated {rotated} file(s), reclaimed {reclaimed:,} bytes "
          f"({reclaimed / 1e6:.2f} MB) -> {dest_dir}")
    if failed:
        print(f"{len(failed)} failure(s); originals were kept:")
        for f, why in failed[:10]:
            print(f"  {os.path.relpath(f, LOGS)}: {why}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
