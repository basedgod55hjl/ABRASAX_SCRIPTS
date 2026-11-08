"""Pin the rotation-vector convention: does q map device->world or world->device?

Android's SensorEvent for TYPE_ROTATION_VECTOR documents q as the rotation that
takes a vector FROM the device frame INTO the world frame (world = East-North-Up).
Getting this backwards inverts every orientation we publish, and it still looks
plausible because a unit quaternion rotated either way is still unit length.

Two independent tests decide it:

  A. Gravity direction.
     A phone lying flat, screen up, sees accel ~ (0,0,+9.8) in the device frame
     (specific force points up, toward the sky, out of the screen).
     In world ENU that same direction is +Up = (0,0,+1).
     * if q is device->world:   q * (0,0,1)_device  ~= (0,0,+1)_world
     * if q is world->device:   q^-1 * (0,0,1)_device ~= (0,0,+1)_world

  B. Yaw consistency.
     Turning the phone about the vertical must change the world-frame
     horizontal heading of the device +X axis, and nothing else.
"""
import math
import sys

sys.path.insert(0, r"C:\ABRASAX")

from abrasax.live_imu import LiveImu

SERIAL = "R5CY308WZVK"


def norm(v):
    return math.sqrt(sum(x * x for x in v))


def unit(v):
    n = norm(v)
    return [x / n for x in v] if n else [0.0, 0.0, 0.0]


def qrot(q, v):
    x, y, z, w = q
    tx = 2 * (y * v[2] - z * v[1])
    ty = 2 * (z * v[0] - x * v[2])
    tz = 2 * (x * v[1] - y * v[0])
    return [v[0] + w * tx + (y * tz - z * ty),
            v[1] + w * ty + (z * tx - x * tz),
            v[2] + w * tz + (x * ty - y * tx)]


def qconj(q):
    return [-q[0], -q[1], -q[2], q[3]]


def main():
    frames = list(LiveImu(serial=SERIAL).stream(count=40))
    n = len(frames)
    acc = [sum(f.accel[i] for f in frames) / n for i in range(3)]
    rot = [sum(f.rotation[i] for f in frames) / n for i in range(4)]

    print(f"mean accel  {[round(v,3) for v in acc]}")
    print(f"mean rotvec {[round(v,4) for v in rot]}  |q|={norm(rot):.4f}")
    print(f"gravity axis in device frame: {[round(v,3) for v in unit(acc)]}")

    dev_up = unit(acc)

    fwd = qrot(rot, dev_up)          # q applied forward
    inv = qrot(qconj(rot), dev_up)   # q^-1 applied

    print(f"\nq   * (gravity-up) = {[round(v,3) for v in fwd]}")
    print(f"q^-1* (gravity-up) = {[round(v,3) for v in inv]}")

    # In world ENU, gravity-UP is +Z. Whichever maps closer to (0,0,1) tells us
    # which direction the quaternion runs.
    d_fwd = abs(fwd[2] - 1.0)
    d_inv = abs(inv[2] - 1.0)

    print(f"\n  distance from (0,0,+1):  forward={d_fwd:.3f}   inverse={d_inv:.3f}")
    if d_fwd < d_inv and d_fwd < 0.05:
        print("  => q is DEVICE -> WORLD (Android's documented convention)")
    elif d_inv < d_fwd and d_inv < 0.05:
        print("  => q is WORLD -> DEVICE (inverse of Android's documentation)")
    else:
        print("  => ambiguous: neither direction lands on +Z")

    # yaw check: rotate device +X into the world and read its bearing
    dev_x = [1.0, 0.0, 0.0]
    wx_f = qrot(rot, dev_x)
    wx_i = qrot(qconj(rot), dev_x)
    print(f"\ndevice +X in world via q   : {[round(v,3) for v in wx_f]}  "
          f"bearing={math.degrees(math.atan2(wx_f[1], wx_f[0])) % 360:.1f} deg")
    print(f"device +X in world via q^-1: {[round(v,3) for v in wx_i]}  "
          f"bearing={math.degrees(math.atan2(wx_i[1], wx_i[0])) % 360:.1f} deg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
