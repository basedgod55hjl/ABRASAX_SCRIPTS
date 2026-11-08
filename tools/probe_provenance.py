"""Two provenance claims from probe_sources need verifying, not asserting.

CLAIM 1 - "rotation_vector is measured from handle 0x6f".
    Android does not expose a physical rotation-vector part; TYPE_ROTATION_VECTOR
    is a FUSED sensor the framework synthesises from accel+gyro+mag. Reporting it
    as 'measured' alongside a hardware handle would overstate what it is: the
    value is real, but its source is an algorithm over three sensors, not one
    chip. Test: does the fused output track its inputs?

CLAIM 2 - "gravity_direction is derived from handle 0x5b".
    Our code computes unit(-accel) from lsm6dsv_0. Android ALSO exposes a
    separate 'gravity' sensor (0x5b) that is itself fused. If our derivation and
    the platform's fused gravity disagree, one of them is wrong. Test: compare.

Both are answered by reading our own output and the device's in the same instant.
"""
import math
import sys

sys.path.insert(0, r"C:\ABRASAX")

from abrasax.adb_sensors import AdbSensorReader
from abrasax.live_imu import LiveImu, gravity_vector

SERIAL = "R5CY308WZVK"


def unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v] if n else [0.0, 0.0, 0.0]


def angle_between(a, b):
    a, b = unit(a), unit(b)
    d = max(-1.0, min(1.0, sum(a[i] * b[i] for i in range(3))))
    return math.degrees(math.acos(d))


def main():
    # one snapshot from each transport
    imu = LiveImu(serial=SERIAL)
    adb = AdbSensorReader(serial=SERIAL)

    s = imu.sample()
    d = adb.sample()
    if s is None or d is None:
        print("a transport is down")
        return 1

    print("=== CLAIM 2: our derived gravity vs Android's fused gravity sensor ===")
    ours = gravity_vector(s["imu"][:3])          # unit(-accel) from lsm6dsv_0
    # Android's own gravity sensor, as reported in its ring buffer
    readings = adb.readings()
    r = adb.pick(readings, "gravity")
    if r is None:
        print("  no 'gravity' sensor reported")
    else:
        theirs = r.values[:3]
        # Android's gravity sensor reports the gravity vector pointing DOWN
        ang = angle_between(ours, theirs)
        print(f"  ours   unit(-accel)      : {[round(v,4) for v in ours]}")
        print(f"  android gravity sensor   : {[round(v,4) for v in theirs]}")
        print(f"  angle between            : {ang:.2f} deg")
        if ang < 5:
            print("  PASS  our derivation agrees with the platform's fused gravity")
        elif ang > 175:
            print("  FAIL  opposite sign: we disagree about which way is up")
        else:
            print(f"  WARN  {ang:.1f} deg apart - check the fusion, not the sign")

    print("\n=== CLAIM 1: is rotation_vector a hardware part or a fusion? ===")
    # A fused sensor has no part number in its name, unlike lsm6dsv_0/ak0991x_0.
    named_hw = ("lsm6dsv_0", "ak0991x_0", "bmp5", "STK33F11")
    rv_name = next((n for n in readings if "rotation vector" in n.lower()
                    and "game" not in n.lower() and "geomagnetic" not in n.lower()), None)
    print(f"  rotation vector sensor name: {rv_name!r}")
    if rv_name and not any(h in rv_name for h in named_hw):
        print("  CONFIRMED: the name carries no hardware part id, unlike the four")
        print("  named chips. TYPE_ROTATION_VECTOR is synthesised by the")
        print("  framework from accelerometer + gyroscope + magnetometer.")
        print("  => its source is a FUSION over 3 sensors, not one sensor.")
    else:
        print("  UNEXPECTED: name carries a hardware part id")

    # does the fused output actually track its inputs? Rotate the accel-derived
    # up vector into the world frame with the quaternion; it must land on -Z.
    x, y, z, w = s["rotation_vector"]
    v = gravity_vector(s["imu"][:3])
    tx = 2 * (y * v[2] - z * v[1])
    ty = 2 * (z * v[0] - x * v[2])
    tz = 2 * (x * v[1] - y * v[0])
    world = [v[0] + w * tx + (y * tz - z * ty),
             v[1] + w * ty + (z * tx - x * tz),
             v[2] + w * tz + (x * ty - y * tx)]
    print(f"\n  quaternion applied to gravity -> {[round(u,4) for u in world]}")
    if world[2] < -0.95:
        print("  PASS  the fused quaternion is consistent with the accelerometer:")
        print("        it maps gravity onto world -Z, so the fusion is tracking.")
    else:
        print("  WARN  quaternion does not map gravity to -Z; fusion may be stale")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
