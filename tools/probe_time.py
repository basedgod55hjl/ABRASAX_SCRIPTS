"""What does "last update time" actually mean here, and which clock is it on?

Three different clocks are in play and conflating them is the usual bug:

  1. DEVICE MONOTONIC  `t` in the 50 Hz stream, and `ts=` in dumpsys. A
     number of milliseconds since boot. Comparable only with other device
     numbers, NEVER with wall time.

  2. DEVICE WALL       the `wall=` field dumpsys prints next to `ts=`. Real
     human time on the handset, but the handset's clock can be skewed from the
     host's.

  3. HOST WALL         `captured_at`, stamped by this machine when it read the
     value. This is the only clock that tells you how fresh OUR copy is.

Everything we publish so far carries `captured_at` (host clock). That is honest
about when we copied it, but it says nothing about when the DEVICE last updated
the underlying sample - which for a ring buffer can be much older.

Measure the gap.
"""
import math
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, r"C:\ABRASAX")

ADB = r"C:\abrasax\_DEAD_PATH\Android\platform-tools\adb.exe"  # DEAD PATH (sirch): no adb.exe on this host
SERIAL = "R5CY308WZVK"


def sh(cmd, timeout=30):
    return subprocess.run([ADB, "-s", SERIAL, "shell", cmd],
                          capture_output=True, text=True, timeout=timeout).stdout


def device_now():
    """Device wall clock and monotonic uptime, read as close together as possible."""
    out = sh("echo $(date +%s%3N) $(cat /proc/uptime)")
    parts = out.split()
    if len(parts) < 2:
        return None, None
    wall_ms = int(parts[0])
    uptime_s = float(parts[1])
    return wall_ms, uptime_s


def main():
    print("=== clocks ===")
    host_before = time.time()
    wall_ms, uptime = device_now()
    host_after = time.time()
    if wall_ms is None:
        print("  could not read device clock")
        return 1

    host_ms = 1000.0 * (host_before + host_after) / 2.0
    skew_ms = wall_ms - host_ms
    print(f"  host wall   : {datetime.fromtimestamp(host_ms/1000, timezone.utc).isoformat()}")
    print(f"  device wall : {datetime.fromtimestamp(wall_ms/1000, timezone.utc).isoformat()}")
    print(f"  skew        : {skew_ms:+.0f} ms  ({skew_ms/1000:+.1f} s)")
    print(f"  device up   : {uptime:.1f} s ({uptime/3600:.2f} h)")

    if abs(skew_ms) < 2000:
        print("  PASS  device and host clocks agree within 2 s")
    else:
        print(f"  WARN  clocks differ by {skew_ms/1000:.1f} s; a device wall")
        print("        timestamp cannot be compared to host time directly")

    print("\n=== age of a dumpsys ring-buffer sample ===")
    dump = sh("dumpsys sensorservice")
    # Motion Sensor block carries wall= and ts=
    cur = None
    newest = None
    for line in dump.splitlines():
        h = re.match(r"^(?P<name>.+?):\s+last\s+\d+\s+events\s*$", line.rstrip())
        if h:
            cur = h.group("name").strip()
            continue
        e = re.match(r"^\s*(?P<idx>\d+)\s+\(ts=(?P<ts>[\d.]+),\s*wall=(?P<wall>[^)]*)\)", line)
        if cur and e:
            newest = (cur, float(e.group("ts")), e.group("wall").strip())
    if newest:
        name, ts, wall = newest
        age_dev = uptime - ts
        print(f"  sensor      : {name}")
        print(f"  device ts   : {ts:.2f} s since boot")
        print(f"  device wall : {wall}")
        print(f"  AGE         : {age_dev:.1f} s  <- how old the DEVICE's value is")
        print()
        print("  our `captured_at` would say ~0 s, because we read it just now.")
        print("  Both are true and they answer different questions. Publishing only")
        print("  captured_at lets a 30-minute-old ring entry look brand new.")

    print("\n=== the 50 Hz stream's own clock ===")
    from abrasax.live_imu import LiveImu
    frames = list(LiveImu(serial=SERIAL).stream(count=20))
    if frames:
        t0, t1 = frames[0].t_ms, frames[-1].t_ms
        print(f"  t first -> last : {t0} -> {t1}  (span {t1-t0} ms)")
        print(f"  as wall         : {datetime.fromtimestamp(t1/1000, timezone.utc).isoformat()}")
        print(f"  comparing that to now gives: "
              f"{(time.time()*1000 - t1)/1000:.0f} s")
        print("  -> nonsense: `t` is milliseconds since BOOT, not epoch. It must")
        print("     never be formatted as a date or compared with wall time.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
