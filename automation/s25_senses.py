"""Pull live S25 senses over adb into one JSON the UI can read.

Why a file and not a socket: the overlay already reads state files
(DATA/runtime-memory/vision_steer_state.json) and the activity bus reads
LOGS/usage.jsonl. A JSON snapshot needs no new service, no new port, and no
change to the supervisor's health table, so it cannot destabilise the HUD.

Design rules, each from something learned the hard way in this repo:
  * EVERY adb call is timeout-bounded. A stalled `dumpsys` must not hang the
    sampler -- a blocking local call on a render thread is what dropped the
    overlay to 7 fps earlier.
  * Every field is independently optional. A permission error or a changed
    dumpsys format must degrade one field, not the whole snapshot.
  * Nothing is written to the device. It reports 98% storage full and we are
    not going to be the reason it dies.

Usage:
    python s25_senses.py            # one snapshot, prints JSON
    python s25_senses.py --watch 5  # refresh every 5s, write the state file
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import time

ADB = r"C:\abrasax\_DEAD_PATH\scrcpy\scrcpy-win64-v4.1\adb.exe"  # DEAD PATH (sirch): no scrcpy bundle on this host
OUT = pathlib.Path(r"C:\ABRASAX\DATA\runtime-memory\s25_senses.json")
TIMEOUT = 8.0


def adb(*args: str) -> str:
    """Run one adb command, bounded, never raising."""
    try:
        r = subprocess.run([ADB, *args], capture_output=True, text=True,
                           timeout=TIMEOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.stdout or ""
    except Exception:  # noqa: BLE001
        return ""


def _kv(text: str, key: str, cast=float):
    m = re.search(rf"{key}:\s*([-\d.]+)", text)
    if not m:
        return None
    try:
        return cast(m.group(1))
    except (TypeError, ValueError):
        return None


def battery() -> dict:
    t = adb("shell", "dumpsys", "battery")
    return {
        "level_pct": _kv(t, "level", int),
        # dumpsys reports tenths of a degree C
        "temp_c": (lambda v: None if v is None else round(v / 10.0, 1))(_kv(t, "temperature")),
        "voltage_mv": _kv(t, "voltage", int),
        "status": (re.search(r"status:\s*(\d+)", t).group(1) if re.search(r"status:\s*(\d+)", t) else None),
        "plugged": (re.search(r"plugged:\s*(\d+)", t).group(1) if re.search(r"plugged:\s*(\d+)", t) else None),
        "health": (re.search(r"health:\s*(\d+)", t).group(1) if re.search(r"health:\s*(\d+)", t) else None),
    }


def screen() -> dict:
    t = adb("shell", "dumpsys", "power")
    m = re.search(r"mWakefulness=(\w+)", t)
    # Android 16 reports `mScreenState=` / `Display Power: state=`, older builds
    # only `mScreenOn=true`. Try all three so this survives an OS update.
    d = (re.search(r"mScreenState=(\w+)", t)
         or re.search(r"Display Power: state=(\w+)", t)
         or re.search(r"mScreenOn=(\w+)", t))
    return {"wakefulness": m.group(1) if m else None,
            "display": d.group(1) if d else None}


def foreground() -> dict:
    """Android 16 dropped the plain `mResumedActivity:` line in favour of
    `topResumedActivity=ComponentInfo{...}`; try each in order, then fall back
    to the window manager's focused window."""
    t = adb("shell", "dumpsys", "activity", "activities")
    pkg = None
    for pat in (r"topResumedActivity=ComponentInfo\{([\w.]+)/",
                r"mResumedActivity:.*?ActivityRecord\{[^}]*?([\w.]+)/",
                r"ResumedActivity:.*?([\w.]+)/[\w.$]+"):
        m = re.search(pat, t)
        if m:
            pkg = m.group(1)
            break
    if not pkg:
        w = adb("shell", "dumpsys", "window")
        m = (re.search(r"mCurrentFocus=Window\{[^}]*?\s([\w.]+)/", w)
             or re.search(r"mFocusedApp=.*?ActivityRecord\{[^}]*?([\w.]+)/", w))
        if m:
            pkg = m.group(1)
    return {"package": pkg, "activity": pkg}


def network() -> dict:
    t = adb("shell", "dumpsys", "wifi")
    ssid = re.search(r'SSID:\s*"([^"]*)"', t) or re.search(r'mWifiInfo.*?SSID:\s*([^,\s]+)', t)
    rssi = re.search(r"RSSI:\s*(-?\d+)", t)
    ip = None
    a = adb("shell", "ip", "-4", "addr", "show", "wlan0")
    m = re.search(r"inet\s+([\d.]+)/", a)
    if m:
        ip = m.group(1)
    return {
        "ssid": ssid.group(1) if ssid else None,
        "rssi_dbm": int(rssi.group(1)) if rssi else None,
        "ip": ip,
        "mobile_data": "1" == adb("shell", "settings", "get", "global", "mobile_data").strip(),
    }


def storage() -> dict:
    t = adb("shell", "df", "/data")
    m = re.search(r"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)%", t)
    if not m:
        return {}
    total_kb, used_kb, free_kb, pct = (int(x) for x in m.groups())
    return {"total_gb": round(total_kb / 1048576, 1),
            "used_gb": round(used_kb / 1048576, 1),
            "free_gb": round(free_kb / 1048576, 1),
            "used_pct": pct}


def location() -> dict:
    """Coarse location only, and only if the device already grants it."""
    t = adb("shell", "dumpsys", "location")
    m = re.search(r"last location=Location\[(\w+)\s+([-\d.]+),([-\d.]+)", t)
    if not m:
        return {"available": False}
    return {"available": True, "provider": m.group(1),
            "lat": float(m.group(2)), "lon": float(m.group(3))}




def thermal() -> dict:
    """Per-cluster thermal zones, in degrees C.

    /sys/class/thermal exposes one zone per CPU cluster plus aoss/cpuss, all in
    millidegrees. This is the real silicon temperature -- dumpsys battery only
    reports the battery cell.
    """
    out = adb("shell", "for z in /sys/class/thermal/thermal_zone*; do "
              "echo -n \"$(cat $z/type 2>/dev/null)=\"; "
              "cat $z/temp 2>/dev/null; echo; done")
    zones = {}
    for line in out.splitlines():
        if "=" not in line:
            continue
        name, _, val = line.partition("=")
        try:
            zones[name.strip()] = round(int(val.strip()) / 1000.0, 1)
        except ValueError:
            continue
    if not zones:
        return {}
    return {"zones": dict(sorted(zones.items(), key=lambda kv: -kv[1])[:8]),
            "max_c": max(zones.values())}


def wifi_link() -> dict:
    """RSSI, frequency, link speed and score from the live RSSI poll."""
    t = adb("shell", "dumpsys wifi | grep -m1 CMD_RSSI_POLL")
    if not t:
        return {}
    d = {}
    m = re.search(r"rssi=(-?\d+)", t)
    if m:
        d["rssi_dbm"] = int(m.group(1))
    m = re.search(r"f=(\d+)", t)
    if m:
        d["freq_mhz"] = int(m.group(1))
    m = re.search(r"link=(\d+)", t)
    if m:
        d["link_mbps"] = int(m.group(1))
    m = re.search(r"score=(\d+)", t)
    if m:
        d["score"] = int(m.group(1))
    return d

def device() -> dict:
    t = adb("shell", "getprop", "ro.product.model").strip()
    return {"model": t or None,
            "serial": adb("shell", "getprop", "ro.serialno").strip() or None,
            "android": adb("shell", "getprop", "ro.build.version.release").strip() or None,
            "sdk": adb("shell", "getprop", "ro.build.version.sdk").strip() or None}


def snapshot() -> dict:
    t0 = time.time()
    snap = {"ts": time.time(), "source": "adb"}
    for name, fn in (("device", device), ("battery", battery), ("screen", screen),
                     ("foreground", foreground), ("network", network),
                     ("storage", storage), ("location", location),
                     ("thermal", thermal), ("wifi_link", wifi_link)):
        try:
            snap[name] = fn()
        except Exception as exc:  # noqa: BLE001
            snap[name] = {"error": repr(exc)[:120]}
    snap["sample_ms"] = int((time.time() - t0) * 1000)
    return snap


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    watch = 0.0
    if "--watch" in argv:
        i = argv.index("--watch")
        watch = float(argv[i + 1]) if i + 1 < len(argv) else 5.0

    if watch <= 0:
        print(json.dumps(snapshot(), indent=2))
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    print(f"watching, writing {OUT} every {watch}s", flush=True)
    while True:
        snap = snapshot()
        tmp = OUT.with_suffix(".tmp")   # atomic: no torn reads
        tmp.write_text(json.dumps(snap), encoding="utf-8")
        os.replace(tmp, OUT)
        print(f"  {snap.get('battery', {}).get('level_pct')}% "
              f"{snap.get('battery', {}).get('temp_c')}C "
              f"{snap.get('foreground', {}).get('package')} "
              f"({snap['sample_ms']}ms)", flush=True)
        time.sleep(watch)


if __name__ == "__main__":
    raise SystemExit(main())
