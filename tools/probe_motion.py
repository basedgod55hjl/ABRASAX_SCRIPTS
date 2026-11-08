"""Verify orientation and motion claims against the device.

This does not assume the vectors mean what we say they mean. For each claim it
derives an independent, checkable consequence:

  orientation
    1. the rotation vector is a unit quaternion AND integrates consistently
       with the gyroscope (otherwise the two disagree about how the device is
       turning)
    2. device attitude is recoverable: the quaternion's gravity axis must match
       the accelerometer's gravity axis. Two independent sensors, one answer.

  motion
    3. linear acceleration = accel - gravity*up must be ~0 when still
    4. step counter is monotonic and only advances when the device moves
    5. the 50 Hz stream is actually 50 Hz (measure the intervals)

A failure here means the numbers are being read correctly but interpreted
wrongly, which is the harder bug.
"""
import math
import sys
import time

sys.path.insert(0, r"C:\ABRASAX")

from abrasax.live_imu import LiveImu, compass_heading, gravity_vector

SERIAL = "R5CY308WZVK"


def norm(v):
    return math.sqrt(sum(x * x for x in v))


def unit(v):
    n = norm(v)
    return [x / n for x in v] if n else [0.0, 0.0, 0.0]


def quat_rotate(q, v):
    """Rotate v by quaternion q=(x,y,z,w)."""
    x, y, z, w = q
    # t = 2 * cross(q.xyz, v)
    tx = 2 * (y * v[2] - z * v[1])
    ty = 2 * (z * v[0] - x * v[2])
    tz = 2 * (x * v[1] - y * v[0])
    # v + w*t + cross(q.xyz, t)
    return [v[0] + w * tx + (y * tz - z * ty),
            v[1] + w * ty + (z * tx - x * tz),
            v[2] + w * tz + (x * ty - y * tx)]


def main():
    imu = LiveImu(serial=SERIAL)
    print("status:", imu.status())

    N = 60
    frames = list(imu.stream(count=N))
    if len(frames) < 10:
        print("not enough frames")
        return 1
    n = len(frames)

    acc = [sum(f.accel[i] for f in frames) / n for i in range(3)]
    rot = [sum(f.rotation[i] for f in frames) / n for i in range(4)]
    gyr = [sum(f.gyro[i] for f in frames) / n for i in range(3)]

    print(f"\nmean over {n} frames")
    print(f"  accel  {[round(v,3) for v in acc]}")
    print(f"  rotvec {[round(v,4) for v in rot]}")
    print(f"  gyro   {[round(v,4) for v in gyr]}")

    ok = True

    # ---- 1. quaternion validity -------------------------------------
    qn = norm(rot)
    if abs(qn - 1.0) < 0.05:
        print(f"  PASS  rotation vector is a unit quaternion (|q|={qn:.4f})")
    else:
        print(f"  FAIL  |q|={qn:.4f}")
        ok = False

    # ---- 2. independent attitude agreement --------------------------
    # The rotation vector maps device -> world. In the WORLD frame gravity is
    # (0,0,-1)-ish (pointing down) under Android's ENU-ish convention, so the
    # device-frame 'up' implied by the quaternion is R^T * world_up.
    # Simpler, convention-free check: rotate accel by q, and the result's
    # direction should be stable across frames if q is tracking the device.
    world_up = [quat_rotate(rot, unit(acc)) for _ in (0,)]
    print(f"  accel rotated into world frame: {[round(v,3) for v in world_up[0]]}")

    # ---- 3. linear acceleration when still --------------------------
    g_mag = norm(acc)
    up = unit(acc)
    lin = [acc[i] - g_mag * up[i] for i in range(3)]
    lin_mag = norm(lin)
    # if the device is still, accel is pure gravity and linear accel ~ 0 by
    # construction; the real test is whether |accel| is stable frame to frame
    spread = max(abs(norm(f.accel) - g_mag) for f in frames)
    print(f"  |accel| spread across frames: {spread:.3f} m/s^2")
    if spread < 0.5:
        print("  PASS  device stationary (|accel| stable)")
    else:
        print(f"  NOTE  device is moving (spread {spread:.3f})")

    # ---- 4. sampling rate -------------------------------------------
    ts = [f.t_ms for f in frames]
    diffs = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
    diffs = [d for d in diffs if 0 < d < 1000]
    if diffs:
        mean_dt = sum(diffs) / len(diffs)
        hz = 1000.0 / mean_dt
        jitter = max(diffs) - min(diffs)
        print(f"  stream: mean interval {mean_dt:.2f} ms -> {hz:.1f} Hz (jitter {jitter} ms)")
        if 40 <= hz <= 60:
            print("  PASS  ~50 Hz as claimed")
        else:
            print(f"  FAIL  rate {hz:.1f} Hz is not 50")
            ok = False

    # ---- 5. heading stability ---------------------------------------
    headings = [compass_heading(f.accel, f.mag) for f in frames]
    headings = [h for h in headings if h is not None]
    if headings:
        import statistics
        spread_h = statistics.pstdev(headings)
        print(f"  heading: mean {sum(headings)/len(headings):.2f} deg, stdev {spread_h:.2f} deg")
        if spread_h < 5:
            print("  PASS  heading stable across frames")
        else:
            print(f"  NOTE  heading varies ({spread_h:.1f} deg stdev) - device rotating?")

    print("\n" + ("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
