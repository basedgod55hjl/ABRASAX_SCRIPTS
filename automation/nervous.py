"""Nervous system: every sensor and every metric in one normalized snapshot.

THE PROBLEM THIS SOLVES
-----------------------
Telemetry was scattered across files with different shapes and cadences:
s25_senses.json (5 s, phone), s25_motion.json (49 Hz, IMU), cost.json,
state-chain.jsonl, plus PC GPU/CPU/RAM which nothing was collecting at all.
Every consumer therefore re-implemented its own parsing.

This module is the single afferent bundle: it samples everything, normalizes it
into one schema, and publishes DATA/runtime-memory/nervous.json at ~2 Hz. The UI
reads that one file; other subsystems can too.

GRAVITY
-------
Android's accelerometer reports proper acceleration including gravity, so the
gravity vector is simply the (smoothed) accelerometer direction, and its
magnitude is the local g. From it we derive the device's tilt relative to true
down, which is the physically meaningful signal -- unlike raw ax/ay/az which
change sign as the phone rotates.

Cost per sample: one nvidia-smi call (cached 1 s), two Win32 calls, and two
small file reads. No HTTP unless a health probe is due.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import math
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(r"C:\ABRASAX")
MEM = ROOT / "DATA" / "runtime-memory"
OUT = MEM / "nervous.json"

MOTION = MEM / "s25_motion.json"
SENSES = MEM / "s25_senses.json"
COST = MEM / "cost.json"
CHAIN = ROOT / "LOGS" / "state-chain.jsonl"

WRITE_HZ = 2.0
GPU_CACHE_S = 1.0


# ------------------------------------------------------------------ Win32 ----
class MEMSTATUS(ctypes.Structure):
    _fields_ = [("dwLength", wt.DWORD), ("dwMemoryLoad", wt.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def ram() -> dict:
    m = MEMSTATUS()
    m.dwLength = ctypes.sizeof(MEMSTATUS)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        return {}
    gb = 1024 ** 3
    return {"used_pct": float(m.dwMemoryLoad),
            "total_gb": round(m.ullTotalPhys / gb, 1),
            "used_gb": round((m.ullTotalPhys - m.ullAvailPhys) / gb, 2)}


class FILETIME(ctypes.Structure):
    _fields_ = [("lo", wt.DWORD), ("hi", wt.DWORD)]


def _ft(v: FILETIME) -> int:
    return (v.hi << 32) | v.lo


_cpu_prev: dict = {}


def cpu() -> dict:
    """CPU% from GetSystemTimes deltas -- no psutil, which is not installed."""
    idle, kern, user = FILETIME(), FILETIME(), FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern),
                                                ctypes.byref(user)):
        return {}
    i, k, u = _ft(idle), _ft(kern), _ft(user)
    prev = _cpu_prev.get("v")
    _cpu_prev["v"] = (i, k, u)
    if not prev:
        return {}
    di, dk, du = i - prev[0], k - prev[1], u - prev[2]
    total = dk + du
    if total <= 0:
        return {}
    return {"used_pct": round(100.0 * (1.0 - di / total), 1)}


_gpu_cache = {"t": 0.0, "d": {}}


def gpu() -> dict:
    now = time.time()
    if now - _gpu_cache["t"] < GPU_CACHE_S:
        return _gpu_cache["d"]
    _gpu_cache["t"] = now
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,"
                            "temperature.gpu,power.draw", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        parts = [p.strip() for p in (r.stdout or "").splitlines()[0].split(",")]
        d = {"util_pct": float(parts[0]), "vram_used_mb": float(parts[1]),
             "vram_total_mb": float(parts[2]), "temp_c": float(parts[3]),
             "power_w": float(parts[4])}
        _gpu_cache["d"] = d
        return d
    except Exception:  # noqa: BLE001
        _gpu_cache["d"] = {}
        return {}


# --------------------------------------------------------------- gravity ----
_grav = {"v": None}

_LAT = [39.1927, -84.4586]   # last known phone fix; refreshed from senses
_T0 = time.time()


def gravity(accel, dt: float = 0.05) -> dict:
    """Gravity vector in device frame, smoothed, plus tilt from true down.

    The accelerometer measures proper acceleration (includes gravity), so at
    rest |a| ~= 9.81 and a/|a| points opposite to gravity in world terms. We
    keep it in the device frame -- that IS the gravity vector expressed in the
    device's own axes, which is what a renderer needs.
    """
    if not accel:
        return {}
    try:
        ax, ay, az = (float(accel[0]), float(accel[1]), float(accel[2]))
    except (TypeError, ValueError, IndexError):
        return {}
    mag = math.sqrt(ax * ax + ay * ay + az * az)
    if mag < 1e-6:
        return {}
    ux, uy, uz = ax / mag, ay / mag, az / mag
    prev = _grav["v"]
    # exponential smoothing: raw IMU is noisy at 50 Hz
    a = 0.25 if prev is None else 0.12
    if prev is None:
        ux, uy, uz = ux, uy, uz
    else:
        ux = prev[0] * (1 - a) + ux * a
        uy = prev[1] * (1 - a) + uy * a
        uz = prev[2] * (1 - a) + uz * a
        n = math.sqrt(ux * ux + uy * uy + uz * uz) or 1.0
        ux, uy, uz = ux / n, uy / n, uz / n
    _grav["v"] = (ux, uy, uz)
    # tilt: angle between the gravity vector and the device's +Y axis (top edge)
    tilt = math.degrees(math.acos(max(-1.0, min(1.0, uy))))
    return {"g_vector": [round(ux, 4), round(uy, 4), round(uz, 4)],
            "g_magnitude": round(mag, 3),
            "tilt_from_top_deg": round(tilt, 2),
            "flat_on_table": mag > 9.0 and abs(uz) > 0.9}


def heading(accel, mag) -> dict:
    """Tilt-compensated compass bearing from accelerometer + magnetometer.

    a is the measured gravity direction (device frame, points up), m is the
    earth field (~25-65 uT, points north and downward in the N hemisphere).
    east = m x a, north = a x east. The bearing of north in the device's own
    horizontal plane, measured from the device +Y edge, is the phone's
    compass heading.

    Approximate: no magnetic declination correction, so it is true to a few
    degrees depending on location. Reported as measured, not as true north.
    """
    if not accel or not mag:
        return {}
    try:
        ax, ay, az = (float(accel[0]), float(accel[1]), float(accel[2]))
        mx, my, mz = (float(mag[0]), float(mag[1]), float(mag[2]))
    except (TypeError, ValueError, IndexError):
        return {}
    an = math.sqrt(ax * ax + ay * ay + az * az)
    mn = math.sqrt(mx * mx + my * my + mz * mz)
    if an < 1e-6 or mn < 1e-6:
        return {}
    ax, ay, az = ax / an, ay / an, az / an
    mx, my, mz = mx / mn, my / mn, mz / mn
    # east = m x a
    ex = my * az - mz * ay
    ey = mz * ax - mx * az
    ez = mx * ay - my * ax
    en = math.sqrt(ex * ex + ey * ey + ez * ez)
    if en < 1e-6:
        return {}
    ex, ey, ez = ex / en, ey / en, ez / en
    # north = a x east
    nx = ay * ez - az * ey
    ny = az * ex - ax * ez
    nz = ax * ey - ay * ex
    hdg = math.degrees(math.atan2(nx, ny))
    return {"heading_deg": round((hdg + 360.0) % 360.0, 1),
            "mag_uT": round(mn * 1.0, 1),
            "north_dev": [round(nx, 3), round(ny, 3), round(nz, 3)],
            "declination_corrected": False}


def earth() -> dict:
    """Real earth time: solar position, day phase, moon phase, growth.

    The solar maths is the standard NOAA approximation: mean longitude, mean
    anomaly, ecliptic longitude, declination, equation of time, then the hour
    angle for sunrise/sunset at h0 = -0.833 deg (refraction + solar radius).
    Accuracy is ~1 minute at mid latitudes, which is far better than needed to
    know whether it is night.
    """
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc)
    lat = _LAT[0]
    lon = _LAT[1]
    n = now.timetuple().tm_yday
    hours = now.hour + now.minute / 60.0 + now.second / 3600.0

    # fractional year (radians)
    g = 2.0 * math.pi / 365.0 * (n - 1 + (hours - 12) / 24.0)
    # equation of time (minutes) and solar declination (radians)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                       - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g)
            - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
            - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))

    # hour angle for sunrise/sunset
    # NOAAA uses cos(90.833 deg) in the denominator form -- that value is
    # NEGATIVE (-0.01454). Writing cos(h0) with h0 = -0.833 deg gives +0.9999,
    # which pushed |cos_ha| above 1 and made every sunrise/sunset null.
    h0 = math.radians(-0.833)
    _lat_r = math.radians(lat)
    cos_ha = ((math.sin(h0) - math.sin(decl) * math.sin(_lat_r))
              / (math.cos(decl) * math.cos(_lat_r)))
    if -1.0 <= cos_ha <= 1.0:
        ha = math.degrees(math.acos(cos_ha))
        sunrise_utc = 720.0 - 4.0 * (lon + ha) - eqtime     # minutes UTC
        sunset_utc = 720.0 - 4.0 * (lon - ha) - eqtime
    else:
        ha = None
        sunrise_utc = sunset_utc = None

    # current solar altitude
    true_solar = hours * 60.0 + eqtime + 4.0 * lon
    ha_now = math.radians((true_solar / 4.0) - 180.0)
    alt = math.degrees(math.asin(
        math.sin(math.radians(lat)) * math.sin(decl)
        + math.cos(math.radians(lat)) * math.cos(decl) * math.cos(ha_now)))

    if alt > 6.0:
        phase = "day"
    elif alt > 0.0:
        phase = "golden"
    elif alt > -6.0:
        phase = "twilight"
    else:
        phase = "night"

    # moon phase: synodic month from a known new moon (2000-01-06 18:14 UTC)
    known_new = 947182440.0
    synodic = 29.530588853 * 86400.0
    frac = ((now.timestamp() - known_new) % synodic) / synodic
    illum = round((1.0 - math.cos(2.0 * math.pi * frac)) / 2.0, 3)

    def _hm(m):
        if m is None:
            return None
        m = m % 1440.0
        return f"{int(m // 60):02d}:{int(m % 60):02d}Z"

    return {
        "utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "local": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "epoch": round(now.timestamp(), 0),
        "day_of_year": n,
        "sun_altitude_deg": round(alt, 2),
        "day_phase": phase,
        "sunrise": _hm(sunrise_utc),
        "sunset": _hm(sunset_utc),
        "daylight_h": round((sunset_utc - sunrise_utc) / 60.0, 2) if sunrise_utc is not None else None,
        "moon_illum": illum,
        "lat": lat, "lon": lon,
        "clock_up_s": round(now.timestamp() - _T0, 0),
    }


def _read(p: pathlib.Path) -> dict:
    """Read JSON, tolerating a writer mid-replace.

    Measured: a truncate-then-write from s25_motion made this return {},
    and the whole motion+gravity block went null. Writers are atomic now,
    but one retry costs nothing and covers writers that are not.
    """
    for _ in range(2):
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            time.sleep(0.01)
    return {}


def chain() -> dict:
    try:
        lines = [l for l in CHAIN.read_text(encoding="utf-8").splitlines() if l.strip()]
        if not lines:
            return {}
        head = json.loads(lines[-1])
        return {"len": len(lines), "head": head.get("hash", "")[:32]}
    except OSError:
        return {}


def snapshot() -> dict:
    t0 = time.time()
    mo = _read(MOTION)
    se = _read(SENSES)
    co = _read(COST)
    acc = mo.get("accel")      # raw accelerometer from the IMU app
    mag = mo.get("mag")        # raw magnetometer from the IMU app
    # only reconstruct from angles if the raw vector is absent
    if not acc and mo.get("pitch_deg") is not None and mo.get("roll_deg") is not None:
        p = math.radians(float(mo["pitch_deg"]))
        r = math.radians(float(mo["roll_deg"]))
        acc = [math.sin(r) * 9.81, math.sin(p) * 9.81,
               math.cos(p) * math.cos(r) * 9.81]

    _loc = se.get("location") or {}
    if _loc.get("available"):
        try:
            _LAT[0] = float(_loc["lat"])
            _LAT[1] = float(_loc["lon"])
        except (KeyError, TypeError, ValueError):
            pass
    return {
        "ts": time.time(),
        "schema": 1,
        "phone": {
            "battery_pct": (se.get("battery") or {}).get("level_pct"),
            "battery_temp_c": (se.get("battery") or {}).get("temp_c"),
            "storage_free_gb": (se.get("storage") or {}).get("free_gb"),
            "foreground": (se.get("foreground") or {}).get("package"),
            "screen": (se.get("screen") or {}).get("wakefulness"),
            "ssid": (se.get("network") or {}).get("ssid"),
            "ip": (se.get("network") or {}).get("ip"),
            "location": se.get("location") or {"available": False},
            "thermal": se.get("thermal") or {},
            "wifi_link": se.get("wifi_link") or {},
        },
        "motion": {
            "hz": mo.get("hz"),
            "pitch_deg": mo.get("pitch_deg"),
            "roll_deg": mo.get("roll_deg"),
            "yaw_deg": mo.get("yaw_deg"),
            "shake": mo.get("shake"),
            "moving": mo.get("moving"),
        },
        "gravity": gravity(acc),
        "heading": heading(acc, mag),
        "pc": {"gpu": gpu(), "cpu": cpu(), "ram": ram()},
        "llm": {"calls_today": co.get("calls_today"),
                "paid_calls_today": co.get("paid_calls_today"),
                "exhausted": co.get("exhausted")},
        "earth": earth(),
        "chain": chain(),
        "sample_ms": int((time.time() - t0) * 1000),
    }


def main() -> int:
    MEM.mkdir(parents=True, exist_ok=True)
    if "--once" in sys.argv:
        snap = snapshot()
        OUT.write_text(json.dumps(snap, indent=2), encoding="utf-8")
        print(json.dumps(snap, indent=2))
        return 0
    period = 1.0 / WRITE_HZ
    print(f"nervous system -> {OUT} at {WRITE_HZ} Hz", flush=True)
    while True:
        t0 = time.time()
        snap = snapshot()
        OUT.write_text(json.dumps(snap), encoding="utf-8")
        g = snap.get("gravity") or {}
        pc = snap.get("pc") or {}
        print(f"  g={g.get('g_magnitude')} tilt={g.get('tilt_from_top_deg')} "
              f"gpu={(pc.get('gpu') or {}).get('util_pct')}% "
              f"cpu={(pc.get('cpu') or {}).get('used_pct')}% "
              f"({snap['sample_ms']}ms)", flush=True)
        time.sleep(max(0.0, period - (time.time() - t0)))


if __name__ == "__main__":
    raise SystemExit(main())
