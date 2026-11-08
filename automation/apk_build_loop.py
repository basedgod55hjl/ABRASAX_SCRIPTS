#!/usr/bin/env python3
"""Nonstop APK build/upgrade loop.

Each pass:
  1. hash the Android source tree (Kotlin/XML/Gradle),
  2. if it changed (or the APK is missing), run PHONE/build_apk.py,
  3. if the build succeeded and a device is online, install and launch it,
  4. append a JSON record and sleep.

It never installs a failed build. Stop with:
    echo stop > LOGS/apk_build_loop.stop

Usage:
    python SCRIPTS/automation/apk_build_loop.py --once
    python SCRIPTS/automation/apk_build_loop.py --interval 600
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "PHONE" / "ABRASAX_AGI_APK" / "ABRASAX_AGI_APK"
APK = PROJECT / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
BUILDER = ROOT / "PHONE" / "build_apk.py"
STATE = ROOT / "LOGS" / "apk_build_loop.json"
LOG = ROOT / "LOGS" / "apk_build_loop.jsonl"
OUT = ROOT / "LOGS" / "apk_build_loop.out"
STOP = ROOT / "LOGS" / "apk_build_loop.stop"
PKG = "com.abrasax.agi.debug"


def run(cmd: list[str], timeout: int = 1800) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return 1, f"{type(exc).__name__}: {exc}"


def source_hash() -> str:
    h = hashlib.sha256()
    roots = [
        PROJECT / "app" / "src" / "main",
        PROJECT / "app" / "build.gradle.kts" if (PROJECT / "app" / "build.gradle.kts").exists()
        else PROJECT / "app" / "build.gradle",
        PROJECT / "build.gradle.kts" if (PROJECT / "build.gradle.kts").exists()
        else PROJECT / "build.gradle",
        PROJECT / "settings.gradle.kts" if (PROJECT / "settings.gradle.kts").exists()
        else PROJECT / "settings.gradle",
        PROJECT / "gradle.properties",
    ]
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            h.update(str(root.relative_to(PROJECT)).encode())
            h.update(root.read_bytes())
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in {
                ".kt", ".java", ".xml", ".gradle", ".kts", ".properties", ".json",
            }:
                continue
            h.update(str(p.relative_to(PROJECT)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


def device() -> str | None:
    rc, out = run(["adb", "devices"], timeout=30)
    if rc != 0:
        return None
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            return parts[0]
    return None


def tick(iteration: int, install: bool) -> dict:
    h = source_hash()
    old = {}
    if STATE.exists():
        try:
            old = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            old = {}
    changed = old.get("source_hash") != h or not APK.exists()
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "iteration": iteration,
           "source_hash": h, "changed": changed, "built": False,
           "installed": False, "device": None, "apk_mb": None, "note": ""}
    if changed:
        rc, out = run(["python", str(BUILDER)], timeout=1800)
        rec["build_rc"] = rc
        rec["build_tail"] = out.strip()[-800:]
        if APK.exists():
            rec["apk_mb"] = round(APK.stat().st_size / 1e6, 2)
        rec["built"] = rc == 0 and APK.exists() and APK.stat().st_size > 1_000_000
    else:
        rec["note"] = "no source change"
    if install and rec["built"]:
        serial = device()
        rec["device"] = serial
        if serial:
            rc, out = run(["adb", "-s", serial, "install", "-r", "-d", str(APK)], timeout=600)
            rec["install_rc"] = rc
            rec["install_tail"] = out.strip()[-400:]
            rec["installed"] = rc == 0 and "Success" in out
            if rec["installed"]:
                run(["adb", "-s", serial, "shell", "appops", "set", PKG,
                     "MANAGE_EXTERNAL_STORAGE", "allow"], timeout=60)
                run(["adb", "-s", serial, "shell", "monkey", "-p", PKG,
                     "-c", "android.intent.category.LAUNCHER", "1"], timeout=60)
        else:
            rec["note"] = "build ok; no device online"
    STATE.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    # stdout is redirected to LOGS/apk_build_loop.out by the launcher; opening
    # the same file here deadlocks on Windows with a PermissionError.
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=600)
    ap.add_argument("--no-install", action="store_true")
    args = ap.parse_args()
    install = not args.no_install
    if args.once:
        r = tick(1, install)
        print(json.dumps(r, indent=2))
        return 0 if r["built"] or not r["changed"] else 1
    i = 0
    while not STOP.exists():
        i += 1
        try:
            r = tick(i, install)
            print(f"{r['ts']} iter={i} changed={r['changed']} built={r['built']} "
                  f"installed={r['installed']}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"tick_error {type(exc).__name__}: {exc}", flush=True)
        time.sleep(max(30, args.interval))
    print("stop file present; exiting")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
