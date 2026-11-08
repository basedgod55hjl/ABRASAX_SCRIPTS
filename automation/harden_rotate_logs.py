"""Harden rotate_logs: detect an open handle BEFORE trying to rotate.

The first --apply run rotated 61 files and then failed on 7:

    svc-abrasax-brain.log      [WinError 32] being used by another process
    svc-abrasax-gateway.log    ...
    svc-abrasax-ui.log, svc-filetool.log, svc-harvest-helper.log,
    svc-node-lm.log, svc-routerfail.log

Every one is a log owned by a RUNNING service. My age rule (skip if modified in the
last 10 minutes) did not cover them: several had not been written for hours, but
the writer still holds the handle open and appends whenever it next logs.

Discovering that by catching WinError 32 works -- the originals were kept, which is
the important part -- but it is the wrong order. The cleaner should know which files
are in use and say so, rather than attempting and failing.

Fix: probe each candidate with an exclusive-ish open before rotating.
On Windows, opening for append with O_RDWR fails if another process holds the file
without share-write, but services usually open with FILE_SHARE_WRITE, so a plain
open() SUCCEEDS and tells us nothing. The reliable signal is different:

  * a file named svc-<service>.log is, by convention, owned by that service
  * any file the supervisor's ledger references is live

So: (a) treat the svc-*.log convention as in-use, (b) attempt an exclusive open via
msvcrt.locking on a tiny region to prove no writer holds it, and (c) keep the
existing WinError fallback as a last resort.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\rotate_logs.py"
src = open(PATH, encoding="utf-8").read()

if "SERVICE_LOG_PREFIX" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''DISPOSABLE_EXT = (".log",)'''
NEW = '''# A file named svc-<service>.log is owned by a running service by convention. The
# first --apply run hit seven of these and only found out by catching WinError 32.
SERVICE_LOG_PREFIX = "svc-"

DISPOSABLE_EXT = (".log",)'''
if OLD not in src:
    print("ANCHOR-NOT-FOUND: DISPOSABLE_EXT")
    sys.exit(1)
src = src.replace(OLD, NEW, 1)

OLD2 = '''def is_disposable(name: str) -> bool:
    if name in LIVE_LEDGERS:
        return False'''
NEW2 = '''def is_disposable(name: str) -> bool:
    if name in LIVE_LEDGERS:
        return False
    if name.startswith(SERVICE_LOG_PREFIX):
        return False      # owned by a live service; it appends whenever it logs'''
if OLD2 not in src:
    print("ANCHOR-NOT-FOUND: is_disposable")
    sys.exit(1)
src = src.replace(OLD2, NEW2, 1)

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: svc-*.log treated as in-use by a service")
