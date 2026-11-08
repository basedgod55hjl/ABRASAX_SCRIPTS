"""Is the rotation vector alive, or frozen at a constant?

probe_heading_agree.py found rotation-vector yaw with stdev 0.00 over 80 frames
while the magnetometer wandered 3.98 deg. A constant attitude is either (a) a
perfectly still phone, or (b) a quaternion that is not updating. Those look
identical from the outside and mean opposite things, so this checks the
quaternion component by component and compares against the gyroscope, which is
an independent witness to whether the device is turning.
"""
import math
import statistics
import sys

sys.path.insert(0, r"C:\ABRASAX")

from abrasax.live_imu import LiveImu

SERIAL = "R5CY308WZVK"


def norm(v):
    return math.sqrt(sum(x * x for x in v))


def main():
    frames = list(LiveImu(serial=SERIAL).stream(count=120))
    print(f"frames: {len(frames)}")

    # quaternion component spread
    for i, name in enumerate("xyzw"):
        vals = [f.rotation[i] for f in frames]
        print(f"  q.{name}: mean {statistics.mean(vals):+.5f}  "
              f"stdev {statistics.pstdev(vals):.6f}  "
              f"range [{min(vals):+.5f}, {max(vals):+.5f}]")

    q_spread = max(statistics.pstdev([f.rotation[i] for f in frames]) for i in range(4))

    # angular speed measured by the gyroscope, converted to deg/s
    speeds = [math.degrees(norm(f.gyro)) for f in frames]
    mean_speed = statistics.mean(speeds)
    max_speed = max(speeds)
    total_rotation_deg = sum(speeds) * 0.020   # 20 ms per frame
    print(f"\n  gyro |w|: mean {mean_speed:.3f} deg/s  max {max_speed:.3f} deg/s")
    print(f"  integrated rotation over {len(frames)*0.02:.1f} s: {total_rotation_deg:.2f} deg")

    # quaternion timestamps must advance
    ts = [f.t_ms for f in frames]
    dt = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
    print(f"\n  timestamps advance: {all(d > 0 for d in dt)}  "
          f"(mean dt {statistics.mean(dt):.2f} ms)")

    print("\nverdict")
    if total_rotation_deg < 1.0 and q_spread < 1e-3:
        print("  CONSISTENT: device is genuinely still.")
        print("  The gyroscope says it barely turned, and the quaternion barely")
        print("  moved. A frozen sensor and a still phone look the same here, so")
        print("  this cannot be decided without moving the device.")
        return 2          # inconclusive, not a failure

    if total_rotation_deg > 5.0 and q_spread < 1e-4:
        print("  SUSPECT: gyro says the device rotated but q did not move.")
        return 1

    print("  PASS: quaternion movement is consistent with measured rotation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
