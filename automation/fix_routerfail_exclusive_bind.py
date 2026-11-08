"""routerfail: refuse a duplicate bind instead of silently sharing the port.

ThreadingHTTPServer inherits allow_reuse_address = 1. On Windows SO_REUSEADDR
lets a SECOND process bind an address already in use, so several routerfail
instances ended up LISTENING on 127.0.0.1:9782 simultaneously (observed pids
66444 + 16276 + 8256) and split incoming connections. The existing
"cannot bind" error path never fired because the bind never failed.

Fix: subclass with allow_reuse_address = False. The existing OSError handler
then does its job and the duplicate exits rc=2.
"""
import shutil
import sys
from pathlib import Path

TARGET = Path("C:/ABRASAX/TOOLS/source-tools/subsystems/routerfail/routerfail.py")
BAK = TARGET.with_suffix(".py.bak-exclusive-bind")

OLD = """    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as e:
        log(f"cannot bind {HOST}:{PORT} - {e}")
        return 2
"""

NEW = """    # allow_reuse_address defaults to 1. On Windows that lets a SECOND process
    # bind a port already in use, so duplicates silently shared :9782 and split
    # traffic. Refuse the bind instead so the OSError path below fires.
    class _ExclusiveServer(ThreadingHTTPServer):
        allow_reuse_address = False
        daemon_threads = True

    try:
        server = _ExclusiveServer((HOST, PORT), Handler)
    except OSError as e:
        log(f"cannot bind {HOST}:{PORT} - {e}")
        return 2
"""


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")

    if "_ExclusiveServer" in src:
        print("already applied")
        return 0

    if OLD not in src:
        print("FAIL: anchor not found verbatim")
        return 1

    if not BAK.exists():
        shutil.copy2(TARGET, BAK)
        print(f"backup: {BAK}")

    patched = src.replace(OLD, NEW, 1)
    compile(patched, str(TARGET), "exec")
    TARGET.write_text(patched, encoding="utf-8")
    print(f"patched: {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
