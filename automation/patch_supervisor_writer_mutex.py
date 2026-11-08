#!/usr/bin/env python3
"""patch_supervisor_writer_mutex.py -- make the supervisor enforce ONE brain-state writer.

Found 2026-10-31: three code paths wrote LOGS/brain_state.json with three
different schemas. The supervisor now launches the canonical writer, but nothing
stops a stray `tools/brain_state.py` / `jev_brain_state.py` (a manual run, a
cached launcher script, a stale scheduled task) from clobbering it again, and
nothing notices when the canonical writer dies silently -- the symptom is only
visible downstream as "overlay is stale".

This adds, inside supervisor.tick(), a mutex step that:
  * kills any live process running one of the retired writers
  * restarts the canonical writer if it is not alive
  * records the kill/restart in the ledger

Idempotent: detects its own marker and exits 0.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SUP = Path(r"C:\abrasax\SCRIPTS\automation\supervisor.py")
MARK = "# --- single brain-state writer mutex"

BLOCK = '''

# --- single brain-state writer mutex -----------------------------------------
# LOGS/brain_state.json has exactly one writer: tools/brain_state_writer.py.
# tools/brain_state.py and ENGINE/floating_brain/jev_brain_state.py are retired
# and emit different schemas (no heartbeat / no embed_ok), which made the
# overlay's input go stale whenever one of them ran. Verified defect: three
# writers, one file, and a fail in test_overlay_jev_wiring at age=71.3s.
_RETIRED_WRITERS = ("brain_state.py", "jev_brain_state.py")
_CANONICAL_WRITER = "brain_state_writer.py"


def _writer_procs() -> list[tuple[int, str]]:
    """(pid, cmdline) for every python process running a brain-state writer."""
    try:
        import psutil
    except Exception:            # noqa: BLE001 - keep the tick loop alive
        return []
    out = []
    for p in psutil.process_iter(["pid", "cmdline"]):
        cmd = " ".join(p.info["cmdline"] or [])
        if (_CANONICAL_WRITER in cmd or
                any(w in cmd for w in _RETIRED_WRITERS)):
            out.append((p.info["pid"], cmd))
    return out


def enforce_single_writer() -> dict:
    """Kill retired writers, keep exactly one canonical writer alive."""
    procs = _writer_procs()
    killed = []
    for pid, cmd in procs:
        if _CANONICAL_WRITER in cmd:
            continue
        try:
            import psutil
            psutil.Process(pid).kill()
            killed.append(pid)
        except Exception:        # noqa: BLE001
            pass
    alive = [p for p in procs if _CANONICAL_WRITER in p[1] and p[0] not in killed]
    started = None
    if not alive:
        res = _start_service("brain_state_writer", {
            "cmd": [sys.executable, "-u", str(ROOT / "tools" / _CANONICAL_WRITER)],
            "cwd": ROOT,
        })
        started = res.get("pid") or res.get("error")
    if killed or started:
        _ledger({"event": "writer_mutex", "killed": killed, "started": started})
    return {"killed": killed, "started": started, "alive": len(alive)}
'''

CALL_MARK = "enforce_single_writer()"


def main() -> int:
    src = SUP.read_text(encoding="utf-8")
    if MARK in src:
        print("already patched")
    else:
        # insert the block just before COOLDOWN_S (module scope, after AUTOSTART)
        anchor = "COOLDOWN_S = 180"
        if anchor not in src:
            print("FAIL: COOLDOWN_S anchor not found")
            return 2
        src = src.replace(anchor, BLOCK.strip("\n") + "\n\n" + anchor, 1)
        SUP.write_text(src, encoding="utf-8")
        print("inserted writer mutex block")

    src = SUP.read_text(encoding="utf-8")
    if CALL_MARK not in src:
        # call it from tick(): find the function and add the call after its docstring
        ti = src.find("def tick(")
        if ti < 0:
            print("FAIL: tick() not found")
            return 3
        # find the end of the docstring inside tick
        dq = src.find('"""', ti)
        dq2 = src.find('"""', dq + 3)
        if dq < 0 or dq2 < 0:
            print("FAIL: tick() docstring not found")
            return 4
        ins = dq2 + 3
        src = (src[:ins] + "\n    try:\n        enforce_single_writer()\n"
               "    except Exception:  # noqa: BLE001 - never kill the tick loop\n"
               "        pass" + src[ins:])
        SUP.write_text(src, encoding="utf-8")
        print("wired enforce_single_writer() into tick()")

    r = subprocess.run([sys.executable, "-m", "py_compile", str(SUP)],
                       capture_output=True, text=True)
    print("py_compile rc=%d %s" % (r.returncode, r.stderr.strip()[:400]))
    return 0 if r.returncode == 0 else 5


if __name__ == "__main__":
    sys.exit(main())
