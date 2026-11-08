#!/usr/bin/env python3
"""fix_edge_services.py -- put the phone edge online: sensors + telegram backend.

Two services existed only as code before this script:
  * SYSTEMS/sensors/sensor_bridge.py  -- pulls the phone's 23 sensors over adb and POSTs to
    the gateway every 2 s; /health on :8797.
  * SYSTEMS/telegram/abrasax_tg_bot.py -- the single Telegram backend (token from .env,
    replies through the gateway); /health on :8798.

Registering them in the three places that must agree is what makes them "always online":
SERVICES (so the CLI/ops monitor/verifier can see them), _HEALTH_PATHS (so a probe hits an
endpoint the process itself serves), and the supervisor's AUTOSTART (so a crash is repaired
instead of noticed).

Run: python SCRIPTS/fix_edge_services.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVICES = ROOT / "abrasax" / "services.py"
SUPERVISOR = ROOT / "SCRIPTS" / "automation" / "supervisor.py"

SVC_ANCHOR = '    {\n        "id": "lmstudio", "name": "LM Studio", "category": "llm",'

SVC_ENTRIES = '''    {
        "id": "sensor-bridge", "name": "phone sensor bridge (ADB)", "category": "sensors",
        "host": "127.0.0.1", "port": 8797, "protocol": "http",
        "entry": "SYSTEMS/sensors/sensor_bridge.py",
        "launch": "python SYSTEMS/sensors/sensor_bridge.py --serve --port 8797",
        "notes": "Reads the phone's sensorservice over adb (TOOLS/platform-tools/adb.exe) and "
                 "POSTs a canonical sample to the gateway /v1/sensors/ingest every 2 s. "
                 "/health names the device, its live sensor count, the sample age and the "
                 "last error, so 'the senses are wired' is a measurement.",
    },
    {
        "id": "telegram-bot", "name": "Telegram backend", "category": "system",
        "host": "127.0.0.1", "port": 8798, "protocol": "http",
        "entry": "SYSTEMS/telegram/abrasax_tg_bot.py",
        "launch": "python SYSTEMS/telegram/abrasax_tg_bot.py --serve --port 8798",
        "notes": "One supervised bot (token from .env, replies through the gateway). "
                 "/status, /sensors /model /ping from the phone; /health reports polls, "
                 "replies and the last error.",
    },
'''

HEALTH_ANCHOR = '    "floating-brain-overlay": "/health",'
HEALTH_LINES = ['    "sensor-bridge": "/health",', '    "telegram-bot": "/health",']

AUTO_ANCHOR = '    "agent-core": {'
AUTO_ENTRY = '''    "sensor-bridge": {
        # The phone is a sensor pack: without this process nothing pulls it, and the world
        # model starves while the hardware sits on the desk reporting "23 live".
        "cmd": [sys.executable, "SYSTEMS/sensors/sensor_bridge.py", "--serve",
                "--port", "8797"],
        "cwd": ROOT,
        "requires": [str(ROOT / "SYSTEMS" / "sensors" / "sensor_bridge.py")],
        "required_bind": 8797,
        "bind_grace_s": 20,
    },
    "telegram-bot": {
        # The phone-facing front door. One poller only: a second one would steal updates.
        "cmd": [sys.executable, "SYSTEMS/telegram/abrasax_tg_bot.py", "--serve",
                "--port", "8798"],
        "cwd": ROOT,
        "requires": [str(ROOT / "SYSTEMS" / "telegram" / "abrasax_tg_bot.py")],
        "required_bind": 8798,
        "bind_grace_s": 20,
    },
'''


def main() -> int:
    svc = SERVICES.read_text(encoding="utf-8-sig")
    sup = SUPERVISOR.read_text(encoding="utf-8-sig")

    have = {
        "sensor-bridge": '"id": "sensor-bridge"' in svc,
        "telegram-bot": '"id": "telegram-bot"' in svc,
        "health": '"sensor-bridge": "/health"' in svc and '"telegram-bot": "/health"' in svc,
        "autostart": '"sensor-bridge": {' in sup and '"telegram-bot": {' in sup,
    }
    if "--check" in sys.argv:
        ok = all(have.values())
        print(("PASS " if ok else "FAIL ") + "edge services registered: " + json_like(have))
        return 0 if ok else 1
    if all(have.values()):
        print("already registered: sensor-bridge + telegram-bot")
        return 0

    if not have["sensor-bridge"] or not have["telegram-bot"]:
        if SVC_ANCHOR not in svc:
            print("FAIL  lmstudio anchor missing in services.py")
            return 1
        svc = svc.replace(SVC_ANCHOR, SVC_ENTRIES + SVC_ANCHOR, 1)
    if not have["health"]:
        if HEALTH_ANCHOR not in svc:
            print("FAIL  health anchor missing in services.py")
            return 1
        svc = svc.replace(
            HEALTH_ANCHOR, HEALTH_ANCHOR + "\n" + "\n".join(HEALTH_LINES), 1
        )
    bak = SERVICES.with_suffix(".py.bak-edge")
    if not bak.exists():
        bak.write_text(SERVICES.read_text(encoding="utf-8-sig"), encoding="utf-8")
    SERVICES.write_text(svc, encoding="utf-8")

    if not have["autostart"]:
        if AUTO_ANCHOR not in sup:
            print("FAIL  agent-core anchor missing in supervisor.py")
            return 1
        bak = SUPERVISOR.with_suffix(".py.bak-edge")
        if not bak.exists():
            bak.write_text(SUPERVISOR.read_text(encoding="utf-8-sig"), encoding="utf-8")
        sup = sup.replace(AUTO_ANCHOR, AUTO_ENTRY + AUTO_ANCHOR, 1)
        SUPERVISOR.write_text(sup, encoding="utf-8")

    print("registered sensor-bridge :8797 + telegram-bot :8798 (catalog, health, autostart)")
    return 0


def json_like(d: dict) -> str:
    return " ".join(f"{k}={v}" for k, v in d.items())


if __name__ == "__main__":
    raise SystemExit(main())
