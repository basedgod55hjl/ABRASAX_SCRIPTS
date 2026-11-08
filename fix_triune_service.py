#!/usr/bin/env python3
"""fix_triune_service.py -- serve and register the awakened mind (triune-mind :9628).

The awareness loop had no owner: no catalog row, no supervisor entry, no port, so
`python -m abrasax services` could not see it and nothing ever started it. The service
module (ENGINE/abrasax_engine/triune_mind.py) now serves /health, /state and /insight;
this script claims the port in the three tables that have to agree.

Run: python SCRIPTS/fix_triune_service.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVICES = ROOT / "abrasax" / "services.py"
SUPERVISOR = ROOT / "SCRIPTS" / "automation" / "supervisor.py"

SVC_ANCHOR = '    {\n        "id": "lmstudio", "name": "LM Studio", "category": "llm",'
SVC_ENTRY = '''    {
        "id": "triune-mind", "name": "TRIUNE mind (awareness loop + model)", "category": "brain",
        "host": "127.0.0.1", "port": 9628, "protocol": "http",
        "entry": "ENGINE/abrasax_engine/triune_mind.py",
        "launch": "python ENGINE/abrasax_engine/triune_mind.py --serve --port 9628",
        "notes": "Three phi-harmonic faces over _TRIUNE_AWARENESS.py, with Face 2 actually "
                 "querying the local model (ABRASAX_MIND_MODEL, default liquid/lfm2.5-1.2b) "
                 "every 30 s. /health reports llm_calls/ok/fail + last latency; /state is "
                 "the full awareness dict; /insight is the current reflection.",
    },
'''

HEALTH_ANCHOR = '    "floating-brain-overlay": "/health",'
HEALTH_LINE = '    "triune-mind": "/health",'

AUTO_ANCHOR = '    "agent-core": {'
AUTO_ENTRY = '''    "triune-mind": {
        # The awareness loop, awake: Face 2 calls the local model, /health on 9628 proves
        # it. Without a row here the module could only ever run by hand.
        "cmd": [sys.executable, "ENGINE/abrasax_engine/triune_mind.py", "--serve",
                "--port", "9628"],
        "cwd": ROOT,
        "requires": [str(ROOT / "ENGINE" / "abrasax_engine" / "triune_mind.py")],
        "required_bind": 9628,
        "bind_grace_s": 25,
    },
'''


def main() -> int:
    svc = SERVICES.read_text(encoding="utf-8-sig")
    sup = SUPERVISOR.read_text(encoding="utf-8-sig")

    have_svc = '"id": "triune-mind"' in svc
    have_health = '"triune-mind": "/health"' in svc
    have_auto = '"triune-mind": {' in sup

    if "--check" in sys.argv:
        ok = have_svc and have_health and have_auto
        print(
            ("PASS " if ok else "FAIL ")
            + f"triune-mind registered: catalog={have_svc} health={have_health} autostart={have_auto}"
        )
        return 0 if ok else 1

    if have_svc and have_health and have_auto:
        print("already registered: triune-mind")
        return 0

    if not have_svc:
        if SVC_ANCHOR not in svc:
            print("FAIL  lmstudio anchor missing in services.py")
            return 1
        bak = SERVICES.with_suffix(".py.bak-triunemind")
        if not bak.exists():
            bak.write_text(svc, encoding="utf-8")
        svc = svc.replace(SVC_ANCHOR, SVC_ENTRY + SVC_ANCHOR, 1)
    if not have_health:
        if HEALTH_ANCHOR not in svc:
            print("FAIL  health anchor missing in services.py")
            return 1
        svc = svc.replace(HEALTH_ANCHOR, HEALTH_ANCHOR + "\n" + HEALTH_LINE, 1)
    SERVICES.write_text(svc, encoding="utf-8")

    if not have_auto:
        if AUTO_ANCHOR not in sup:
            print("FAIL  agent-core anchor missing in supervisor.py")
            return 1
        bak = SUPERVISOR.with_suffix(".py.bak-triunemind")
        if not bak.exists():
            bak.write_text(sup, encoding="utf-8")
        sup = sup.replace(AUTO_ANCHOR, AUTO_ENTRY + AUTO_ANCHOR, 1)
        SUPERVISOR.write_text(sup, encoding="utf-8")

    print("registered triune-mind: SERVICES + _HEALTH_PATHS + AUTOSTART")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
