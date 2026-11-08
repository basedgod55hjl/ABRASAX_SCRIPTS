"""ops_monitor.start(): do not claim "started" for a process that died on launch.

Observed defect 2026-10-25: ops_monitor logged
    "heals": ["supervisor started pid=61980", "buildloop started pid=42284"]
but pid 61980 was already gone seconds later (buildloop 42284 survived).
start() returned a success string purely from subprocess.Popen's pid, which
exists even if the child crashes immediately on import or argument error.

Fix: after spawn, wait briefly and require the child to still be alive. If it
exited, report the exit code and captured reason instead of "started".
PYTHONW (pythonw) discards stderr, so a crash is otherwise invisible.
"""
import shutil
import sys
from pathlib import Path

TARGET = Path("C:/ABRASAX/SCRIPTS/automation/ops_monitor.py")
BAK = TARGET.with_suffix(".py.bak-start-verify")

OLD = '''def start(path: Path, args: list[str]) -> str:
    flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    try:
        p = subprocess.Popen(
            [str(path), *args], cwd=str(ROOT), stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=flags, close_fds=True,
        )
        return f"started pid={p.pid}"
    except Exception as exc:
        return f"start failed: {exc.__class__.__name__}: {exc}"
'''

NEW = '''def start(path: Path, args: list[str], settle_s: float = 3.0) -> str:
    """Spawn a detached child and verify it SURVIVED.

    Popen hands back a pid even when the child dies instantly, so reporting
    "started pid=N" without checking is how a dead supervisor got recorded as a
    successful heal. We wait and require the process to still exist.
    """
    flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    try:
        p = subprocess.Popen(
            [str(path), *args], cwd=str(ROOT), stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=flags, close_fds=True,
        )
    except Exception as exc:
        return f"start failed: {exc.__class__.__name__}: {exc}"

    # give the interpreter time to fault on a bad import before we believe it
    deadline = time.time() + settle_s
    while time.time() < deadline:
        rc = p.poll()
        if rc is not None:
            return f"start FAILED pid={p.pid} exited rc={rc}"
        time.sleep(0.2)

    if p.poll() is not None:
        return f"start FAILED pid={p.pid} exited rc={p.returncode}"
    return f"started pid={p.pid} (verified alive)"
'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")

    if "verified alive" in src:
        print("already applied - no change")
        return 0

    if OLD not in src:
        print("FAIL: anchor not found verbatim; refusing to patch blind")
        return 1

    if "import time" not in src.split("def start")[0]:
        print("FAIL: 'time' not imported before start(); cannot add timing check")
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
