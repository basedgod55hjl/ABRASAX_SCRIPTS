"""fix_pidfile_empty_window.py - a loser could delete a winner that was still writing.

MEASURED 2026-11-01T18:33Z, full suite under load:

    FAILED tests/test_supervisor_pidfile_race.py::test_exactly_one_winner_under_a_real_process_race
    (the same test passes 9/9 when run alone)

The claim is O_CREAT|O_EXCL, which is atomic - but the winner writes its pid in a
SECOND step, so for a few hundred microseconds the file exists and is EMPTY. A
loser that arrives in that window reads no owner, calls it "stale", unlinks the
winner's file and creates its own. Two winners, and the first one no longer owns
the lock it thinks it owns.

That window only opens under load, which is exactly when the singleton matters -
the same failure mode as the 16:17Z duplicate-supervisor incident, one layer
down.

Fix: distinguish the two "no owner" cases.
  * EMPTY file, younger than the grace window -> a winner is mid-write; wait and
    re-read instead of unlinking.
  * empty and older than the grace, or a non-empty body that names no live pid
    (dead pid / garbage) -> genuinely stale, unlink and retry.

Idempotent.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\SCRIPTS\automation\supervisor.py")

OLD = '''def _claim_pidfile() -> bool:
    """Atomically claim LOGS/supervisor.pid. True only for the one winner.

    Check-then-write is not a lock: two supervisors started in the same second
    both saw "no live owner" and both wrote the file (measured 2026-11-01), so
    both ran the tick and started duplicate services. O_CREAT|O_EXCL is atomic
    on Win32 and POSIX, so only one caller can create the file.
    """
    for _attempt in range(2):
        try:
            fd = os.open(PIDFILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            pid = _pidfile_owner()
            if pid and pid != os.getpid():
                return False              # a real, live supervisor owns it
            # Stale (dead pid / empty / garbage): remove once, then retry.
            try:
                PIDFILE.unlink()
            except OSError:
                return False
            continue
        except OSError:
            return False
        else:
            try:
                os.write(fd, str(os.getpid()).encode("ascii"))
            finally:
                os.close(fd)
            return True
    return False'''

NEW = '''# The winner creates the file with O_CREAT|O_EXCL and writes its pid in a second
# step. A loser arriving inside that window used to read an empty file, call it
# stale, and unlink the winner's lock (measured 2026-11-01 under load: two
# winners). An empty file younger than this is a winner mid-write, not a corpse.
_CLAIM_GRACE_S = 2.0


def _pidfile_body() -> str | None:
    try:
        return PIDFILE.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def _claim_pidfile(grace_s: float | None = None) -> bool:
    """Atomically claim LOGS/supervisor.pid. True only for the one winner.

    Check-then-write is not a lock: two supervisors started in the same second
    both saw "no live owner" and both wrote the file (measured 2026-11-01), so
    both ran the tick and started duplicate services. O_CREAT|O_EXCL is atomic
    on Win32 and POSIX, so only one caller can create the file.

    The second step (writing the pid) is NOT atomic with the create, so an empty
    file is treated as "someone is writing", not as "stale", until the grace
    expires. A non-empty body that names no live pid is stale immediately.
    """
    grace = _CLAIM_GRACE_S if grace_s is None else float(grace_s)
    deadline = time.time() + grace + 3.0
    while True:
        try:
            fd = os.open(PIDFILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            pid = _pidfile_owner()
            if pid and pid != os.getpid():
                return False              # a real, live supervisor owns it
            body = _pidfile_body()
            if body in (None, ""):
                # Empty: either a winner mid-write (wait) or a leftover from a
                # process that died between create and write (age decides).
                try:
                    age = time.time() - PIDFILE.stat().st_mtime
                except OSError:
                    return False
                if age < grace and time.time() < deadline:
                    time.sleep(0.02)
                    continue
            try:
                PIDFILE.unlink()
            except OSError:
                return False
            continue
        except OSError:
            return False
        else:
            try:
                os.write(fd, str(os.getpid()).encode("ascii"))
                os.fsync(fd)
            finally:
                os.close(fd)
            return True'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "_CLAIM_GRACE_S" in src:
        print("already applied")
        return 0
    if src.count(OLD) != 1:
        raise SystemExit(f"anchor {src.count(OLD)}x")
    TARGET.write_text(src.replace(OLD, NEW, 1), encoding="utf-8", newline="")
    print("patched", TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
