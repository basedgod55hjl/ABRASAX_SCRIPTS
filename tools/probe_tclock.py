"""Is the 50 Hz stream's `t` since-boot or epoch milliseconds?

My own probe comment claimed since-boot. The numbers said otherwise: t was
1792397458220, and interpreting that as epoch ms gave a wall time matching the
host clock to within a second. Since-boot would be ~69,000,000 ms.

Decide it against two independent references: the device's own uptime, and its
own wall clock. Whichever the value matches is the answer.
"""
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, r"C:\ABRASAX")

from abrasax.live_imu import LiveImu

ADB = r"C:\abrasax\_DEAD_PATH\Android\platform-tools\adb.exe"  # DEAD PATH (sirch): no adb.exe on this host
SERIAL = "R5CY308WZVK"


def sh(cmd):
    return subprocess.run([ADB, "-s", SERIAL, "shell", cmd],
                          capture_output=True, text=True, timeout=25).stdout


def main():
    # reference readings from the device, bracketing the sample
    before = sh("echo $(date +%s%3N) $(cat /proc/uptime)").split()
    host_t = time.time()
    s = LiveImu(serial=SERIAL).read_one()
    after = sh("echo $(date +%s%3N) $(cat /proc/uptime)").split()

    if s is None:
        print("no frame")
        return 1

    dev_wall_before, up_before = int(before[0]), float(before[1])
    dev_wall_after, up_after = int(after[0]), float(after[1])
    dev_wall_mid = (dev_wall_before + dev_wall_after) / 2
    up_mid = (up_before + up_after) / 2

    t = s.t_ms
    print(f"  stream t            : {t}")
    print(f"  device uptime (ms)  : {up_mid*1000:,.0f}")
    print(f"  device epoch (ms)   : {dev_wall_mid:,.0f}")
    print(f"  host   epoch (ms)   : {host_t*1000:,.0f}")

    d_epoch_dev = abs(t - dev_wall_mid)
    d_epoch_host = abs(t - host_t * 1000)
    d_boot = abs(t - up_mid * 1000)

    print(f"\n  |t - device epoch|  : {d_epoch_dev:,.0f} ms")
    print(f"  |t - host epoch|    : {d_epoch_host:,.0f} ms")
    print(f"  |t - uptime|        : {d_boot:,.0f} ms")

    print("\nverdict")
    if d_boot < 5000:
        print("  t is MILLISECONDS SINCE BOOT.")
        return 0
    if d_epoch_dev < 5000 or d_epoch_host < 5000:
        print("  t is EPOCH MILLISECONDS (Unix wall time).")
        print(f"  As a date: {datetime.fromtimestamp(t/1000, timezone.utc).isoformat()}")
        print("  => it CAN be compared with host time, and its age is meaningful.")
        return 0
    print("  t matches neither reference; do not interpret it as either.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
