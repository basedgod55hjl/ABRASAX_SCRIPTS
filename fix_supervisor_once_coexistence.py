"""fix_supervisor_once_coexistence.py -- a debug --once tick must not start services.

Measured 2026-11-01 16:17Z: `supervisor.py --once` was run for diagnostics while
the resident supervisor already owned LOGS/supervisor.pid (--once skips the
singleton by design). Both ticked the same down list:

  16:17:10Z  tick  started 12 services        (pid 27540, the --once)
  16:17:13Z  tick  started floating-brain-overlay + floating-brain  (pid 25000)
  16:18:28Z  start floating-brain  pid 27152
  16:18:29Z  start floating-brain  pid 33676   <- loser left running

Two different tricks were played on the same GPU port. The resident starts
anything that is down within one 30 s tick, so a concurrent --once gains
nothing and only widens the race.

Fix: --once stays allowed (it is the debug probe), but when a *live* resident
owns the pidfile it is forced to probe-only. No starts, no duplicate services.

Idempotent. Backs up to supervisor.py.bak-once-YYYYMMDD.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\SCRIPTS\automation\supervisor.py")

OLD = '''    try:
        if args.once:
            tick(args.interval, dry_run=args.dry_run, quiet=args.quiet)
            return 0
'''

NEW = '''    try:
        if args.once:
            # --once intentionally skips the singleton (debug probe), but it must
            # not START anything while a resident owns the pidfile: measured
            # 2026-11-01, a debug --once and the resident both saw the same
            # service down and each launched a copy of the GPU server 1 s apart.
            # The resident starts anything down within 30 s, so probe-only is
            # all a concurrent --once can usefully do.
            dry = args.dry_run
            if not dry:
                try:
                    _owner = int(PIDFILE.read_text().strip())
                except (OSError, ValueError):
                    _owner = 0
                if _owner and _owner != os.getpid() and _pid_alive(_owner):
                    dry = True
                    print(f"resident supervisor pid {_owner} owns the pidfile; "
                          f"--once is probe-only (no starts)")
            tick(args.interval, dry_run=dry, quiet=args.quiet)
            return 0
'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "probe-only (no starts)" in src:
        print("already patched")
        return 0
    if OLD not in src:
        print("ANCHOR NOT FOUND -- refusing to guess")
        return 1
    bak = TARGET.with_suffix(".py.bak-once-" + dt.date.today().strftime("%Y%m%d"))
    bak.write_text(src, encoding="utf-8")
    TARGET.write_text(src.replace(OLD, NEW, 1), encoding="utf-8")
    print(f"patched {TARGET} (backup {bak.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
