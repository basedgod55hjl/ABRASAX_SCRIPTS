"""fix_supervisor_pidfile_race.py -- make the supervisor's singleton atomic.

Defect (measured 2026-11-01): main() guarded the singleton with a *check-then-write*
on LOGS/supervisor.pid:

    if PIDFILE.exists():
        pid = int(PIDFILE.read_text())
        if pid and pid != os.getpid() and _pid_alive(pid):
            return 0
    PIDFILE.write_text(str(os.getpid()))

Two supervisors launched in the same second both read "no live owner" and both
wrote the file; the second overwrote the first. Both then ran the 30 s tick, so
the ledger carries interleaved ticks and duplicate `start` events for the same
service (floating-brain and floating-brain-overlay were each started twice
inside 12 s, and both times the loser's process was left running). Evidence:
LOGS/supervisor-ledger.jsonl 16:17:10Z / 16:17:13Z / 16:18:28Z / 16:18:29Z.

Fix: claim the pidfile with O_CREAT|O_EXCL, which is atomic on Win32 and POSIX.
A stale file (dead pid, unparsable, empty) is removed exactly once and the claim
retried. The loser exits without ticking and without touching the winner's file.

Idempotent. Backs up to supervisor.py.bak-pidrace-YYYYMMDD.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\SCRIPTS\automation\supervisor.py")

OLD = '''    LOGS.mkdir(parents=True, exist_ok=True)
    if not args.once:
        if PIDFILE.exists():
            try:
                pid = int(PIDFILE.read_text().strip())
            except (OSError, ValueError):
                pid = 0
            if pid and pid != os.getpid() and _pid_alive(pid):
                print(f"supervisor already running (pid {pid}); exiting")
                return 0
        PIDFILE.write_text(str(os.getpid()), encoding="utf-8")
'''

NEW = '''    LOGS.mkdir(parents=True, exist_ok=True)
    owns_pidfile = True
    if not args.once:
        owns_pidfile = _claim_pidfile()
        if not owns_pidfile:
            print("supervisor already running; exiting")
            return 0
'''

HELPER_ANCHOR = "def main(argv: list[str] | None = None) -> int:"

HELPER = '''def _claim_pidfile() -> bool:
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
            try:
                pid = int(PIDFILE.read_text().strip())
            except (OSError, ValueError):
                pid = 0
            if pid and pid != os.getpid() and _pid_alive(pid):
                return False              # a live supervisor owns it
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
    return False


'''

UNLINK_OLD = '''    finally:
        if not args.once:
            try:
                PIDFILE.unlink()
            except OSError:
                pass
'''

UNLINK_NEW = '''    finally:
        # Only the owner may remove the file: a loser that unlinked here would
        # delete the live supervisor's pidfile and invite a third instance.
        if not args.once and owns_pidfile:
            try:
                PIDFILE.unlink()
            except OSError:
                pass
'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "_claim_pidfile" in src:
        print("already patched")
        return 0
    for anchor in (OLD, UNLINK_OLD, HELPER_ANCHOR):
        if anchor not in src:
            print(f"ANCHOR NOT FOUND: {anchor.splitlines()[0]!r} -- refusing to guess")
            return 1
    bak = TARGET.with_suffix(".py.bak-pidrace-" + dt.date.today().strftime("%Y%m%d"))
    bak.write_text(src, encoding="utf-8")
    out = src.replace(UNLINK_OLD, UNLINK_NEW, 1)
    out = out.replace(HELPER_ANCHOR, HELPER + HELPER_ANCHOR, 1)
    out = out.replace(OLD, NEW, 1)
    TARGET.write_text(out, encoding="utf-8")
    print(f"patched {TARGET} (backup {bak.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
