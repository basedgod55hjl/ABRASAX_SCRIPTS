"""Resolve the gravity sign conflict definitively.

Our `gravity_vector(accel)` returns unit(-accel). Android's TYPE_GRAVITY sensor
on this device reports approximately (+0.38, -0.40, -9.79) in its own ring
buffer... except probe_provenance printed (+(-0.38), 0.4, 9.79) for it, i.e.
the SAME sign as the accelerometer, which is specific force (UP).

Only one of these can be the convention the rest of our code assumes, so pin it
against something unambiguous: a device lying flat, screen up, has gravity
pointing straight DOWN through the back of the phone. In the Android device
frame (Z out of the screen toward the user), DOWN is -Z.

So:
  * a vector named "gravity" should be ~(0,0,-9.81) if it means the force
  * Android's TYPE_GRAVITY actually reports the direction of gravity, which
    Android documents as measuring "the force of gravity" and in practice
    reports the NEGATED accelerometer, i.e. (0,0,-9.81) when face up.

If this device reports +9.79 on Z, that is the accelerometer's specific force,
not gravity, and our unit(-accel) is the correct gravity direction.
"""
import math
import sys

sys.path.insert(0, r"C:\ABRASAX")

from abrasax.adb_sensors import AdbSensorReader

SERIAL = "R5CY308WZVK"


def main():
    adb = AdbSensorReader(serial=SERIAL)
    r = adb.readings()

    acc = adb.pick(r, "accelerometer")
    grav = adb.pick(r, "gravity")
    lin = adb.pick(r, "linear_acceleration")

    print("raw ring-buffer contents (device frame, Z out of screen):\n")
    for name, reading in (("accelerometer", acc), ("gravity", grav),
                          ("linear_acceleration", lin)):
        if reading:
            vals = ", ".join(f"{v:+8.3f}" for v in reading.values[:3])
            print(f"  {name:<22} [{vals}]")

    if not acc or not grav:
        print("\nmissing a sensor; cannot compare")
        return 1

    a = acc.values[:3]
    g = grav.values[:3]
    l = lin.values[:3] if lin else None

    print("\nidentities")
    print(f"  accel == gravity ?  {math.dist(a, g) < 0.2}")
    print(f"  accel == -gravity ? {math.dist(a, [-x for x in g]) < 0.2}")

    if l is not None:
        predicted = [a[i] - g[i] for i in range(3)]
        print(f"  linear_acc == accel - gravity ? {math.dist(l, predicted) < 0.3}")
        predicted2 = [a[i] + g[i] for i in range(3)]
        print(f"  linear_acc == accel + gravity ? {math.dist(l, predicted2) < 0.3}")

    print("\nconclusion")
    if math.dist(a, g) < 0.2:
        print("  This device's TYPE_GRAVITY reports the SAME vector as the")
        print("  accelerometer (specific force, pointing UP, ~+9.8 on Z).")
        print("  It is NOT the gravity force direction.")
        print()
        print("  => our gravity_vector() = unit(-accel) is the correct")
        print("     gravity-force direction, and it legitimately differs from")
        print("     Android's TYPE_GRAVITY by 180 degrees.")
        print()
        print("  The earlier 'FAIL opposite sign' was my probe comparing two")
        print("  different quantities and calling the difference a defect.")
        return 0
    if math.dist(a, [-x for x in g]) < 0.2:
        print("  TYPE_GRAVITY is the negation of accel, as expected.")
        print("  => our gravity_vector() agrees with the platform.")
        return 0
    print("  NEITHER identity holds; the fusion is doing something else.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
