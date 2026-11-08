"""fix_bind_grace_per_service.py - a slow-booting service is not a broken one.

MEASURED 2026-11-01T17:54:19Z, first live exercise of the new lmstudio row:

    {"ts": "2026-11-01T17:54:19Z", "event": "blocked", "svc": "lmstudio",
     "error": "never bound :1234", ...}

while :1234 was serving HTTP 200 one second later. `lms server start` needs
3-6 s to open the port; `bind_never_opened` gave it 3.0 s flat. Two costs:

1. a false "blocked" record for a service that did start;
2. worse, the failure path wrote "never bound :1234" into `_exe_probe_cache` for
   the CLI's path, TTL 600 s - so `_exe_unrunnable` would then call a perfectly
   good lms.exe broken for ten minutes and preflight would refuse to start it.

Fix: a per-service `bind_grace_s` (lmstudio: 15 s), and no exe-cache poisoning
from a bind timeout - "the port has not opened yet" is not "the binary cannot
run".

Idempotent: re-running changes nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\SCRIPTS\automation\supervisor.py")

OLD_FN = '''def bind_never_opened(spec: dict, grace_s: float = 3.0) -> dict | None:
    """After a launch, is the service's required port still closed?

    fb_server.exe exits immediately on this host; the supervisor used to call
    that "started" and then restart it every cooldown forever. A declared
    required_bind turns that into one block.
    """
    port = spec.get("required_bind")
    if port is None:
        return None
    deadline = time.time() + grace_s
    while time.time() < deadline:
        if _port_open(int(port), 0.4):
            return None
        time.sleep(0.25)
    _exe_probe_cache[str(spec.get("cmd", ["?"])[0]).lower()] = (
        time.time(), f"never bound :{port}")
    return {"error": f"never bound :{port}", "blocked": True}'''

NEW_FN = '''def bind_never_opened(spec: dict, grace_s: float = 3.0) -> dict | None:
    """After a launch, is the service's required port still closed?

    fb_server.exe exits immediately on this host; the supervisor used to call
    that "started" and then restart it every cooldown forever. A declared
    required_bind turns that into one block.

    A per-service ``bind_grace_s`` overrides the default. Measured
    2026-11-01T17:54:19Z: `lms server start` needed 3-6 s to open :1234 and the
    flat 3.0 s grace recorded "never bound :1234" one second before the port
    answered HTTP 200.

    The exe-probe cache is deliberately NOT written here. It used to be, with a
    600 s TTL, so one slow boot made `_exe_unrunnable` call a healthy binary
    broken for ten minutes and preflight refused to restart it.
    """
    port = spec.get("required_bind")
    if port is None:
        return None
    try:
        grace_s = float(spec.get("bind_grace_s") or grace_s)
    except (TypeError, ValueError):
        pass
    deadline = time.time() + grace_s
    while time.time() < deadline:
        if _port_open(int(port), 0.4):
            return None
        time.sleep(0.25)
    return {"error": f"never bound :{port} after {grace_s:.0f}s", "blocked": True}'''

OLD_SPEC = '''        "requires": [str(_LMS)],
        "required_bind": 1234,'''
NEW_SPEC = '''        "requires": [str(_LMS)],
        "required_bind": 1234,
        # lms server start needs 3-6 s to open :1234 (measured 17:54:19Z: a
        # 3.0 s grace reported "never bound" one second early).
        "bind_grace_s": 15,'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if '"bind_grace_s": 15' in src:
        print("already applied")
        return 0
    for old, new in ((OLD_FN, NEW_FN), (OLD_SPEC, NEW_SPEC)):
        if src.count(old) != 1:
            raise SystemExit(f"anchor not unique ({src.count(old)}x): {old[:60]!r}")
        src = src.replace(old, new, 1)
    TARGET.write_text(src, encoding="utf-8", newline="")
    print("patched", TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
