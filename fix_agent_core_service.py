#!/usr/bin/env python3
"""fix_agent_core_service.py -- put the Hermes agent core in the service catalog.

Measured 2026-11-01: AGENTS/agent-system/agent-core had source, dist and a green
end-to-end self-test, but it appeared in neither abrasax/services.py nor the supervisor's
AUTOSTART table. Nothing ever started it, `python -m abrasax services` could not see it,
and "Hermes" was a directory rather than a service.

Adds one row to each of the three places that have to agree:
  * abrasax/services.py  SERVICES   -- the catalog the CLI, ops monitor and verifier read
  * abrasax/services.py  _HEALTH_PATHS -- /api/health is served by the process itself
  * SCRIPTS/automation/supervisor.py AUTOSTART -- how to (re)start it, and the bind that
    proves it actually took :4200

Run: python SCRIPTS/fix_agent_core_service.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVICES = ROOT / "abrasax" / "services.py"
SUPERVISOR = ROOT / "SCRIPTS" / "automation" / "supervisor.py"

SVC_ANCHOR = '    {\n        "id": "lmstudio", "name": "LM Studio", "category": "llm",'
SVC_ENTRY = '''    {
        "id": "agent-core", "name": "Hermes agent core (IPC bus)", "category": "agents",
        "host": "127.0.0.1", "port": 4200, "protocol": "http",
        "entry": "AGENTS/agent-system/agent-core/dist/index.js",
        "launch": "node dist/index.js  (AGENT_PORT, default 4200; chat UI on 4220)",
        "notes": "Hex agent bus: Planner/Executor/Observer/Hermes over WS + REST. "
                 "Hermes routes a task to a real agent and relays the reply to every "
                 "connected client (see agent-core/src/selftest/hermes-e2e.ts).",
    },
'''

HEALTH_ANCHOR = '    "floating-brain-overlay": "/health",'
HEALTH_LINE = '    "agent-core": "/api/health",\n'

AUTO_ANCHOR = '    "abrasax-gateway": {\n        "cmd": [sys.executable, "-m", "abrasax", "gateway", "--port", "9001"],'
AUTO_ENTRY = '''    "agent-core": {
        # The Hermes agent core (IPC bus on :4200). It existed as source + dist with a
        # green self-test but no process: neither this table nor SERVICES named it, so
        # nothing ever started it. The bind on :4200 is the proof it is really serving.
        "cmd": [_NODE, "dist/index.js"],
        "cwd": ROOT / "AGENTS" / "agent-system" / "agent-core",
        "requires": [str(ROOT / "AGENTS" / "agent-system" / "agent-core" / "dist" / "index.js")],
        "required_bind": 4200,
        "bind_grace_s": 20,
    },
'''


def main() -> int:
    svc = SERVICES.read_text(encoding="utf-8-sig")
    sup = SUPERVISOR.read_text(encoding="utf-8-sig")

    have_svc = '"id": "agent-core"' in svc
    have_health = '"agent-core": "/api/health"' in svc
    have_auto = '"agent-core": {' in sup

    if "--check" in sys.argv:
        ok = have_svc and have_health and have_auto
        print(
            ("PASS " if ok else "FAIL ")
            + f"agent-core registered: catalog={have_svc} health={have_health} autostart={have_auto}"
        )
        return 0 if ok else 1

    if have_svc and have_health and have_auto:
        print("already registered: agent-core")
        return 0

    if not have_svc:
        if SVC_ANCHOR not in svc:
            print("FAIL  lmstudio anchor missing in services.py")
            return 1
        bak = SERVICES.with_suffix(".py.bak-agentcore")
        if not bak.exists():
            bak.write_text(svc, encoding="utf-8")
        svc = svc.replace(SVC_ANCHOR, SVC_ENTRY + SVC_ANCHOR, 1)
    if not have_health:
        if HEALTH_ANCHOR not in svc:
            print("FAIL  health anchor missing in services.py")
            return 1
        svc = svc.replace(HEALTH_ANCHOR, HEALTH_ANCHOR + "\n" + HEALTH_LINE.rstrip("\n"), 1)
    SERVICES.write_text(svc, encoding="utf-8")

    if not have_auto:
        if AUTO_ANCHOR not in sup:
            print("FAIL  AUTOSTART anchor missing in supervisor.py")
            return 1
        bak = SUPERVISOR.with_suffix(".py.bak-agentcore")
        if not bak.exists():
            bak.write_text(sup, encoding="utf-8")
        sup = sup.replace(AUTO_ANCHOR, AUTO_ENTRY + AUTO_ANCHOR, 1)
        SUPERVISOR.write_text(sup, encoding="utf-8")

    print("registered agent-core: SERVICES + _HEALTH_PATHS + AUTOSTART")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
