"""guard_to_hud - bridge the layerguard proxy into the floating brain HUD.

The floating brain's ActivityBus reads the newest usable JSON record from
C:\\ABRASAX\\LOGS\\usage.jsonl to populate its LLM panel. The guard proxy
writes its own audit at _WORK\\layerguard\\logs\\proxy_audit.jsonl, which the
HUD does not see. This bridge tails the guard audit and mirrors each allowed
completion into usage.jsonl with route=layerguard, so the HUD shows the real
guarded brain (OrcaCyber) instead of a stale route.

Stdlib only. Never prints or copies prompt/response secrets beyond what the
audit already stores (audit stores digests, not content).
"""
import json
import os
import sys
import time
from pathlib import Path

AUDIT = Path(r"C:\abrasax\_DEAD_PATH\layerguard\logs\proxy_audit.jsonl")  # DEAD PATH (sirch): original C:\Users\sirch\_WORK\layerguard tree has no local equivalent
USAGE = Path(r"C:\ABRASAX\LOGS\usage.jsonl")
INTERVAL = 2.0


def main() -> int:
    pos = 0
    while True:
        try:
            if not AUDIT.exists():
                time.sleep(INTERVAL)
                continue
            with AUDIT.open("r", encoding="utf-8", errors="replace") as fh:
                fh.seek(pos)
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    # Only mirror decisions the guard ALLOWED (fail-closed):
                    # blocked calls must not surface as live LLM activity.
                    if rec.get("decision") != "allow":
                        continue
                    entry = {
                        "ts": time.time(),
                        "route": "layerguard",
                        "model": rec.get("model_effective") or rec.get("model") or "guard",
                        "tokens_per_s": 0.0,
                        "prompt": rec.get("path", ""),
                        "response": "guard allow",
                        "kind": "guard_bridge",
                        "ok": True,
                    }
                    with USAGE.open("a", encoding="utf-8") as uf:
                        uf.write(json.dumps(entry) + "\n")
                pos = fh.tell()
        except Exception:
            pass
        time.sleep(INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
