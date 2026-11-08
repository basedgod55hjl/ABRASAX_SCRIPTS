"""Determine the actual coordinate frame of every sense, from the device.

The question this answers: when we say a vector is "in the device frame", is it
really the Android sensor frame, and what is the sign convention? Android
documents it, but documentation is not measurement, so we test it.

Android sensor coordinate frame (what we claim to be in):
    +X  points right, when the device is held in its natural orientation
    +Y  points up (toward the top edge)
    +Z  points out of the screen toward the user
    Rotation vectors follow the right-hand rule about each of those axes.

Accelerometer measures SPECIFIC FORCE, so a device lying flat, screen up,
reads roughly (0, 0, +9.81). If we ever saw -9.81 there, our sign or frame
would be wrong.
"""
import sys

sys.path.insert(0, r"C:\ABRASAX")

from abrasax.live_imu import LiveImu, compass_heading

SERIAL = "R5CY308WZVK"


def show(label, vec, n=3):
    vals = ", ".join(f"{v:+8.3f}" for v in vec[:n])
    print(f"  {label:<10} [{vals}]")


def main():
    imu = LiveImu(serial=SERIAL)
    print(f"live_imu status: {imu.status()}")

    # average a handful of frames so a single noisy sample doesn't decide this
    samples = list(imu.stream(count=20))
    if not samples:
        print("no frames")
        return 1

    n = len(samples)
    acc = [sum(s.accel[i] for s in samples) / n for i in range(3)]
    gyr = [sum(s.gyro[i] for s in samples) / n for i in range(3)]
    mag = [sum(s.mag[i] for s in samples) / n for i in range(3)]
    rot = [sum(s.rotation[i] for s in samples) / n for i in range(4)]

    print(f"\nmean over {n} frames @50Hz")
    show("accel", acc)
    show("gyro", gyr)
    show("mag", mag)
    show("rotvec", rot, 4)

    import math
    amag = math.sqrt(sum(v * v for v in acc))
    gmag = math.sqrt(sum(v * v for v in gyr))
    mmag = math.sqrt(sum(v * v for v in mag))
    rn = math.sqrt(sum(v * v for v in rot))

    print(f"\nmagnitudes")
    print(f"  |accel| = {amag:.3f} m/s^2   (expect ~9.81 if at rest)")
    print(f"  |gyro|  = {gmag:.4f} rad/s   (expect ~0 if still)")
    print(f"  |mag|   = {mmag:.2f} uT      (expect 25-65)")
    print(f"  |rot|   = {rn:.4f}           (expect 1.0 for a unit quaternion)")

    print("\nframe checks")
    ok = True
    if 9.0 <= amag <= 10.6:
        print("  PASS  accel magnitude is Earth gravity -> specific force, not delta-v")
    else:
        print(f"  FAIL  |accel|={amag:.2f} outside 9.0-10.6; device may be moving")
        ok = False

    if abs(rn - 1.0) < 0.05:
        print("  PASS  rotation vector is a unit quaternion (x,y,z,w)")
    else:
        print(f"  WARN  |rot|={rn:.3f} not unit; quaternion may be unnormalised")
        ok = False

    # Which axis is 'up'? The largest-magnitude accel component is the one
    # gravity is pushing against.
    axis = "XYZ"[max(range(3), key=lambda i: abs(acc[i]))]
    sign = "+" if acc[max(range(3), key=lambda i: abs(acc[i]))] > 0 else "-"
    print(f"  gravity-dominated axis: {sign}{axis}  "
          f"(device lies {'flat, screen ' + ('up' if sign == '+' else 'down') if axis == 'Z' else 'on its side'})")

    h = compass_heading(acc, mag)
    print(f"  heading from this mean frame: {h:.2f} deg" if h is not None else "  heading undefined")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
