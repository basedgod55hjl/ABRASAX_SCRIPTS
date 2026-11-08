"""Two independent ways to know which way the phone points. Do they agree?

  magnetometer heading : from the magnetic field vector, tilt-compensated.
                         Absolute, but corrupted by nearby metal/magnets and
                         by uncalibrated hard/soft iron.

  rotation-vector yaw  : from the fused gyro+accel+mag attitude, rotated into
                         the world frame. Smooth and drift-corrected, but its
                         zero is whatever the world frame's X axis is.

They are NOT the same quantity:
  * magnetic heading is relative to MAGNETIC NORTH
  * the world frame of TYPE_ROTATION_VECTOR is ENU, whose +X is EAST
So a correct pair differs by a constant ~90 degrees, plus the local magnetic
declination, plus any magnetometer error. The test is therefore:

    (rv_bearing - mag_heading) should be STABLE across samples,
    not necessarily zero.

If it drifts, one of them is being computed wrongly.
"""
import math
import statistics
import sys

sys.path.insert(0, r"C:\ABRASAX")

from abrasax.live_imu import LiveImu, compass_heading

SERIAL = "R5CY308WZVK"

# Louisville, KY area -- the fix we read was 39.19,-84.46.
# Magnetic declination there is roughly -5 deg (west), i.e. magnetic north sits
# slightly west of true north. Used only as a plausibility bound, not as truth.
DECLINATION_DEG = -5.0


def qrot(q, v):
    x, y, z, w = q
    tx = 2 * (y * v[2] - z * v[1])
    ty = 2 * (z * v[0] - x * v[2])
    tz = 2 * (x * v[1] - y * v[0])
    return [v[0] + w * tx + (y * tz - z * ty),
            v[1] + w * ty + (z * tx - x * tz),
            v[2] + w * tz + (x * ty - y * tx)]


def main():
    frames = list(LiveImu(serial=SERIAL).stream(count=80))
    print(f"frames: {len(frames)}")

    rows = []
    for f in frames:
        h = compass_heading(f.accel, f.mag)
        if h is None:
            continue
        # device +X in the world frame, via the device->world quaternion
        wx = qrot(f.rotation, [1.0, 0.0, 0.0])
        # world frame is ENU: bearing of +X measured from EAST, going north
        rv = math.degrees(math.atan2(wx[1], wx[0])) % 360.0
        rows.append((h, rv, f.mag, f.accel))

    print(f"usable: {len(rows)}")
    mags = [r[0] for r in rows]
    rvs = [r[1] for r in rows]
    print(f"\nmagnetic heading : mean {statistics.mean(mags):7.2f}  "
          f"stdev {statistics.pstdev(mags):6.2f}")
    print(f"rotation-vector  : mean {statistics.mean(rvs):7.2f}  "
          f"stdev {statistics.pstdev(rvs):6.2f}")

    diffs = [((rv - mg + 180) % 360) - 180 for mg, rv in zip(mags, rvs)]
    print(f"\noffset (rv - mag) : mean {statistics.mean(diffs):7.2f}  "
          f"stdev {statistics.pstdev(diffs):6.2f}")

    # magnetic field quality
    fmag = [math.sqrt(sum(v * v for v in r[2])) for r in rows]
    print(f"|mag| uT          : mean {statistics.mean(fmag):7.2f}  "
          f"min {min(fmag):.2f}  max {max(fmag):.2f}")

    print("\ninterpretation")
    print("  ENU +X is EAST, magnetic heading is from NORTH,")
    print("  so a healthy pair differs by ~90 deg (plus declination).")
    expect = 90.0 + DECLINATION_DEG
    off = statistics.mean(diffs)
    sd = statistics.pstdev(diffs)
    residual = ((off - expect + 180) % 360) - 180
    print(f"  expected offset ~ {expect:+.1f} deg, measured {off:+.1f} deg, "
          f"residual {residual:+.1f} deg")
    if sd < 3.0:
        print(f"  PASS  offset is STABLE (stdev {sd:.2f} deg): both pipelines agree "
              f"on rotation rate")
    else:
        print(f"  FAIL  offset drifts (stdev {sd:.2f} deg): one pipeline is wrong")
    if abs(residual) < 45:
        print(f"  PASS  residual {residual:+.1f} deg is within magnetometer error")
    else:
        print(f"  WARN  residual {residual:+.1f} deg is large: mag likely "
              f"uncalibrated or perturbed nearby")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
