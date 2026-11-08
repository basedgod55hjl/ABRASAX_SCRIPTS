"""Keep the floating-brain renderer continuously bound to live LLM inference.

`string_brain.py --loop` does the work but dies with its terminal. This supervisor
exists so the binding is *durable*: it re-launches the driver if it exits, backs
off on repeated failures, and writes a heartbeat the rest of the system can read.

Design notes, learned the hard way on this box:
  * The renderer must be up before the driver starts, or every push fails. Wait for
    :9700 rather than racing it.
  * A broken coupling must never look healthy. The heartbeat records the last push
    result verbatim, not a boolean.
  * Regenerating the same reply every cycle would make a frozen image look alive,
    so the topic rotates and the clock advances each pass.

Usage:
    python SCRIPTS/automation/alive_bind.py --interval 8
    python SCRIPTS/automation/alive_bind.py --cycles 3 --interval 2   (bounded)
"""
import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = r"C:\ABRASAX"
PY = os.path.join(ROOT, "PYTHON", ".venv_gui", "Scripts", "python.exe")
DRIVER = os.path.join(ROOT, "SCRIPTS", "automation", "string_brain.py")
HEARTBEAT = os.path.join(ROOT, "LOGS", "alive-bind.jsonl")

RENDER_HOST, RENDER_PORT = "127.0.0.1", 9700
BRAIN_HOST, BRAIN_PORT = "127.0.0.1", 9626

TOPICS = [
    "Describe what a thought feels like in one short sentence.",
    "What is the golden ratio's role in stability? One sentence.",
    "Explain phase locking to a child. One sentence.",
    "What makes a pattern feel alive? One sentence.",
    "Describe the colour of a coherent field. One sentence.",
    "What is the difference between noise and signal? One sentence.",
    "Describe a brain made of light. One sentence.",
    "What does it mean for two things to resonate? One sentence.",
]


def port_open(host, port, timeout=1.0):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def wait_for(host, port, label, limit=180.0):
    t0 = time.time()
    while time.time() - t0 < limit:
        if port_open(host, port):
            return True
        time.sleep(1.0)
    print(f"[alive-bind] {label} :{port} never came up", flush=True)
    return False


def heartbeat(record):
    try:
        with open(HEARTBEAT, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=8.0)
    ap.add_argument("--cycles", type=int, default=0, help="0 = run until killed")
    ap.add_argument("--max-failures", type=int, default=5)
    args = ap.parse_args()

    print(f"[alive-bind] waiting for renderer :{RENDER_PORT}", flush=True)
    if not wait_for(RENDER_HOST, RENDER_PORT, "renderer"):
        return 2
    print(f"[alive-bind] renderer up, waiting for brain :{BRAIN_PORT}", flush=True)
    if not wait_for(BRAIN_HOST, BRAIN_PORT, "brain", limit=60):
        print("[alive-bind] brain down; continuing anyway (renderer has a synthetic fallback)",
              flush=True)

    stop = {"flag": False}

    def _stop(signum, frame):
        stop["flag"] = True

    try:
        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)
    except (ValueError, OSError):
        pass

    cycle = 0
    failures = 0
    t_start = time.time()

    while not stop["flag"]:
        topic = TOPICS[cycle % len(TOPICS)]
        cmd = [PY, DRIVER, "--prompt", topic, "--cycles", "1"]

        t0 = time.time()
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            out = (r.stdout or "").strip()
            err = (r.stderr or "").strip()
            rc = r.returncode
        except subprocess.TimeoutExpired:
            out, err, rc = "", "timeout after 120s", -1
        except Exception as e:  # noqa: BLE001
            out, err, rc = "", f"{type(e).__name__}: {e}", -1

        record = None
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    pass

        ok = bool(record) and record.get("push") == "drive-ok"

        hb = {
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "cycle": cycle,
            "ok": ok,
            "elapsed_s": round(time.time() - t0, 2),
            "topic": topic,
            "reply": (record or {}).get("reply"),
            "push": (record or {}).get("push"),
            "routed_via": (record or {}).get("routed_via"),
            "tokens": (record or {}).get("tokens"),
            "rc": rc,
            "err": err[:200] if err else None,
            "uptime_s": round(time.time() - t_start, 1),
        }
        heartbeat(hb)
        print(json.dumps(hb), flush=True)

        if ok:
            failures = 0
        else:
            failures += 1
            if failures >= args.max_failures:
                print(f"[alive-bind] {failures} consecutive failures, stopping", flush=True)
                return 1
            time.sleep(min(30.0, 2.0 * failures))

        cycle += 1
        if args.cycles and cycle >= args.cycles:
            break

        # Sleep, but stay responsive to the stop flag.
        slept = 0.0
        while slept < args.interval and not stop["flag"]:
            time.sleep(0.5)
            slept += 0.5

    print(f"[alive-bind] stopped after {cycle} cycles, {time.time() - t_start:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
