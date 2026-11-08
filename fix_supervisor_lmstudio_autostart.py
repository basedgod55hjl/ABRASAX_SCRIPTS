"""fix_supervisor_lmstudio_autostart.py - a dead LM Studio server must not stay dead.

MEASURED 2026-11-01T18:47Z, stack otherwise healthy:

    python SCRIPTS/verify_stack_run.py -> FAIL  http lmstudio :1234  [None ...]
    LOGS/ops-state.json                -> "signature": "down:lmstudio"
    lms server status                  -> The server is not running.

Nothing restarted it: `lmstudio` is catalogued with `entry: None` / `launch:
None` ("external desktop app"), so it is in neither SERVICES-autostart nor
AUTOSTART, and the supervisor can only watch it die. Every route that names
lmstudio (the gateway's default local route among them) fails while it is down.

`lms server start` is idempotent and simply reports already-running when the
port is owned. Adding the row to AUTOSTART, with :1234 as the required bind,
lets one tick put the local inference service back.

Idempotent: re-running changes nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\SCRIPTS\automation\supervisor.py")

OLD_CONST = """_LLAMA_MODEL = _llama_model()
"""
NEW_CONST = """_LLAMA_MODEL = _llama_model()
# LM Studio ships its own CLI; `lms server start` is the only supported way to
# bring its OpenAI server up without a desktop session.
_LMS = Path.home() / ".lmstudio" / "bin" / "lms.exe"
"""

OLD_AUTOSTART = '''AUTOSTART: dict[str, dict] = {
'''
NEW_AUTOSTART = '''AUTOSTART: dict[str, dict] = {
    "lmstudio": {
        # Catalogued with entry/launch = None ("external desktop app"), so the
        # supervisor could not restart it. Measured 2026-11-01T18:47Z: its
        # server died, :1234 refused, ops-state read "down:lmstudio", and the
        # only evidence was a FAIL from the verifier. `lms server start` is
        # idempotent; the bind on :1234 is what proves it worked.
        # Not `lms server start` directly: stopping the server deletes
        # ~/.lmstudio/.internal/temp and the next load fails with ENOENT
        # (measured twice, 2026-11-01T18:57Z), so the wrapper recreates it and
        # waits for /v1/models before this process exits 0.
        "cmd": [sys.executable, str(ROOT / "tools" / "lmstudio_start.py")],
        "cwd": ROOT,
        "requires": [str(_LMS)],
        "required_bind": 1234,
    },
'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if '"lmstudio": {' in src:
        print("already applied")
        return 0
    for old, new in ((OLD_CONST, NEW_CONST), (OLD_AUTOSTART, NEW_AUTOSTART)):
        if src.count(old) != 1:
            raise SystemExit(f"anchor not unique ({src.count(old)}x): {old[:60]!r}")
        src = src.replace(old, new, 1)
    TARGET.write_text(src, encoding="utf-8", newline="")
    print("patched", TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
