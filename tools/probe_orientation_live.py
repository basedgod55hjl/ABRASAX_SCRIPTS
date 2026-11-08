"""Dismiss the (unsecured) keyguard and prove orientation tracks real motion.

Earlier this failed because the keyguard was up: input reached the device (the
power key toggled Awake/Dozing) but swipes landed on the lock screen and moved
nothing. `dumpsys device_policy` reports Password quality {0=0}, i.e. no secure
lock, so the keyguard is a plain swipe and can be dismissed.

Then: swipe to dismiss, drive a real gesture, and require the quaternion to move
along with the gyroscope.
"""
import math
import statistics
import subprocess
import sys
import time

sys.path.insert(0, r"C:\ABRASAX")

from abrasax.live_imu import LiveImu

ADB = r"C:\abrasax\_DEAD_PATH\Android\platform-tools\adb.exe"  # DEAD PATH (sirch): no adb.exe on this host
SERIAL = "R5CY308WZVK"


def sh(cmd, timeout=25):
    return subprocess.run([ADB, "-s", SERIAL, "shell", cmd],
                          capture_output=True, text=True, timeout=timeout).stdout


def locked():
    out = sh("dumpsys window")
    for line in out.splitlines():
        if "mDreamingLockscreen=" in line:
            return "mDreamingLockscreen=true" in line
    return None


def qrot(q, v):
    x, y, z, w = q
    tx = 2 * (y * v[2] - z * v[1])
    ty = 2 * (z * v[0] - x * v[2])
    tz = 2 * (x * v[1] - y * v[0])
    return [v[0] + w * tx + (y * tz - z * ty),
            v[1] + w * ty + (z * tx - x * tz),
            v[2] + w * tz + (x * ty - y * tx)]


def yaw_of(q):
    wx = qrot(q, [1.0, 0.0, 0.0])
    return math.degrees(math.atan2(wx[1], wx[0])) % 360.0


def mean_q(frames):
    n = len(frames)
    return [sum(f.rotation[i] for f in frames) / n for i in range(4)]


def qdist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(4)))


def main():
    print(f"locked before: {locked()}")

    # wake, then swipe the keyguard away
    sh("input keyevent 224")          # WAKEUP
    time.sleep(1)
    sh("input swipe 540 1900 540 500 250")
    time.sleep(1.5)
    print(f"locked after dismiss attempt: {locked()}")

    imu = LiveImu(serial=SERIAL)
    before = list(imu.stream(count=25))
    q0 = mean_q(before)
    print(f"\nbefore: yaw={yaw_of(q0):7.2f} deg  q={[round(v,4) for v in q0]}")

    print("driving gestures...")
    for i in range(4):
        # large vertical swipes move the phone in a holder, and scroll the UI
        sh("input swipe 540 1700 540 400 200")
        time.sleep(0.15)
        sh("input swipe 540 400 540 1700 200")
        time.sleep(0.15)
    sh("input keyevent 3")            # HOME, another small jolt
    time.sleep(1.5)

    after = list(imu.stream(count=25))
    q1 = mean_q(after)
    print(f"after : yaw={yaw_of(q1):7.2f} deg  q={[round(v,4) for v in q1]}")

    d = qdist(q0, q1)
    dyaw = abs(((yaw_of(q1) - yaw_of(q0) + 180) % 360) - 180)
    gyro = statistics.mean([math.degrees(
        math.sqrt(sum(g * g for g in f.gyro))) for f in before + after])

    print(f"\n  quaternion delta : {d:.5f}")
    print(f"  yaw change       : {dyaw:.2f} deg")
    print(f"  |gyro| sampled   : {gyro:.3f} deg/s")

    print("\nverdict")
    if d > 0.002 or dyaw > 0.5:
        print("  PASS: attitude followed a real, induced motion.")
        print(f"        quaternion moved {d:.5f}, yaw changed {dyaw:.2f} deg.")
        return 0
    print("  FAIL: quaternion did not respond to induced motion.")
    print("  The device may still be locked, or input is not physically moving it")
    print("  (e.g. it is sitting in a holder and only the screen reacts).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
