"""phone_link.py -- keep the S25 reachable over adb wireless debugging.

Wireless debugging disconnects when the handset idles, and it comes back on a NEW
port every session. This poll re-resolves the endpoint from mDNS and reconnects,
so `deploy_layers.py` finds the phone attached instead of reporting L2 failed.

    python SCRIPTS/phone_link.py --once     # check and reconnect if needed
    python SCRIPTS/phone_link.py            # every 60 s, forever
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time

SERIAL = "R5CY308WZVK"


def sh(cmd: str, timeout: int = 30) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return ""


def endpoint() -> str | None:
    m = re.search(rf"adb-{SERIAL}-\S+\s+_adb-tls-connect\._tcp\s+(\S+)",
                  sh("adb mdns services", 25))
    return m.group(1) if m else None


def attached() -> bool:
    """Wireless adb lists `IP:port`, NOT the serial, so match any device entry and
    confirm identity by model. Only state `device` counts; offline/unauthorized do not."""
    out = sh("adb devices", 25)
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            model = sh(f"adb -s {parts[0]} shell getprop ro.product.model", 15).strip()
            if model == "SM-S938U":
                return True
    return False


def ensure(verbose: bool = True) -> bool:
    if attached():
        if verbose:
            print(f"[phone] attached {SERIAL}", flush=True)
        return True
    ep = endpoint()
    if not ep:
        if verbose:
            print("[phone] no mDNS endpoint; enable Wireless debugging on the handset", flush=True)
        return False
    sh("adb start-server", 30)
    sh(f"adb connect {ep}", 30)
    for _ in range(10):  # adb flips offline -> device asynchronously
        time.sleep(1)
        if attached():
            if verbose:
                print(f"[phone] connected {ep}", flush=True)
            return True
    if verbose:
        print(f"[phone] FAILED {ep}", flush=True)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=60)
    a = ap.parse_args()
    if a.once:
        return 0 if ensure() else 1
    while True:
        ensure()
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())
