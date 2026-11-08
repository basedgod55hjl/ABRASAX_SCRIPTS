"""Read the S25 IMU stream and publish motion state for the UI.

Transport: the on-device app (PROJECTS/s25-imu-bridge, package ai.abrasax.imu)
opens a ServerSocket on 8765; `adb forward tcp:18766 tcp:8765` carries it over
USB to loopback. Measured 49 Hz with real values.

Why not poll dumpsys: measured 0 live sample values while the sensors were
running. There is no adb-only path to IMU samples. That is why the APK exists.

Derived signals, all cheap and all from measured streams:
  pitch / roll  gravity direction from the accelerometer (stable, drift-free)
  yaw           from the rotation-vector quaternion (magnetometer-fused)
  shake         gyro magnitude, low-passed -- "the phone is being moved"
  hz            observed sample rate, so a stalled link is visible not guessed

Writes DATA/runtime-memory/s25_motion.json at ~20 Hz. Never blocks the reader
for more than one socket timeout.
"""
from __future__ import annotations

import json
import math
import os
import pathlib
import socket
import sys
import time

OUT = pathlib.Path(r"C:\ABRASAX\DATA\runtime-memory\s25_motion.json")
PORT = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 18766
WRITE_HZ = 20.0


def _yaw_deg(q) -> float:
    """Yaw from quaternion (x, y, z, w). Rotation about the world Y axis."""
    x, y, z, w = q
    siny = 2.0 * (w * y + x * z)
    cosy = 1.0 - 2.0 * (y * y + x * x)
    return math.degrees(math.atan2(siny, cosy))


def derive(sample: dict, state: dict) -> dict:
    a = sample.get("a") or [0.0, 0.0, 0.0]
    g = sample.get("g") or [0.0, 0.0, 0.0]
    r = sample.get("r") or [0.0, 0.0, 0.0, 1.0]

    ax, ay, az = float(a[0]), float(a[1]), float(a[2])
    # gravity direction -> pitch/roll. atan2 form stays well behaved when the
    # accelerometer magnitude is not exactly 9.81.
    pitch = math.degrees(math.atan2(ay, math.hypot(ax, az)))
    roll = math.degrees(math.atan2(-ax, az))

    shake = math.sqrt(sum(float(v) ** 2 for v in g[:3]))
    # exponential smoothing: a single noisy sample should not jolt the brain
    prev = state.get("shake", 0.0)
    state["shake"] = prev * 0.82 + shake * 0.18

    yaw = _yaw_deg(r)
    # unwrap so the value cannot jump 359 degrees in one step
    py = state.get("yaw")
    if py is not None:
        while yaw - py > 180.0:
            yaw -= 360.0
        while yaw - py < -180.0:
            yaw += 360.0
    state["yaw"] = yaw

    pitch_prev = state.get("pitch")
    state["pitch"] = pitch if pitch_prev is None else pitch_prev * 0.6 + pitch * 0.4

    return {
        "ts": time.time(),
        "source": "s25-imu",
        "pitch_deg": round(state["pitch"], 2),
        "roll_deg": round(roll, 2),
        "yaw_deg": round(state["yaw"], 2),
        "shake": round(state["shake"], 4),
        "moving": state["shake"] > 0.35,
        "sample_ts": sample.get("t"),
    }


def main() -> int:
    state: dict = {}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    hz_t0 = time.time()
    hz = 0.0
    last_write = 0.0

    while True:
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=5) as s:
                s.settimeout(10)
                buf = b""
                print(f"connected to 127.0.0.1:{PORT}", flush=True)
                while True:
                    chunk = s.recv(8192)
                    if not chunk:
                        print("stream closed by device", flush=True)
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        if not line.strip():
                            continue
                        try:
                            sample = json.loads(line)
                        except ValueError:
                            continue
                        n += 1
                        out = derive(sample, state)
                        now = time.time()
                        if now - hz_t0 >= 1.0:
                            hz = n / (now - hz_t0)
                            n, hz_t0 = 0, now
                        if now - last_write >= 1.0 / WRITE_HZ:
                            out["hz"] = round(hz, 1)
                            out["accel"] = sample.get("a")
                            out["gyro"] = sample.get("g")
                            out["mag"] = sample.get("m")   # magnetometer
                            tmp = OUT.with_suffix(".tmp")   # atomic: no torn reads
                            tmp.write_text(json.dumps(out), encoding="utf-8")
                            # os.replace raises WinError 5 if a reader (or the
                            # indexer) holds the target for a moment. Retry a
                            # few times rather than dropping the socket.
                            for _try in range(5):
                                try:
                                    os.replace(tmp, OUT)
                                    break
                                except PermissionError:
                                    time.sleep(0.01)
                            last_write = now
        except Exception as exc:  # noqa: BLE001
            print(f"reconnecting ({exc})", flush=True)
            time.sleep(1.0)


if __name__ == "__main__":
    raise SystemExit(main())
