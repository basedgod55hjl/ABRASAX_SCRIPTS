"""What uncertainty can the device actually tell us?

Before inventing a confidence number, find out what is measurable. Candidate
sources of real uncertainty on this platform:

  1. RESOLUTION - `dumpsys sensorservice` reports each sensor's maxRange and
     resolution. Resolution is a hard floor on precision and is the honest
     basis for a per-sensor confidence.

  2. NOISE - sample a still device and measure the actual standard deviation.
     That is empirical, not datasheet.

  3. CALIBRATION - the uncalibrated variants (handles 0x8d, 0xa1, 0x15f) report
     a calibration bias as their 4th component. A non-zero bias means the
     *calibrated* reading has already had something subtracted from it, and the
     magnitude of that correction bounds the error.

  4. TIMING - the age of a ring-buffer sample, already implemented for position.

Anything not derivable from these is a guess and must be labelled a prior.
"""
import math
import re
import statistics
import subprocess
import sys
import time

sys.path.insert(0, r"C:\ABRASAX")

ADB = r"C:\abrasax\_DEAD_PATH\Android\platform-tools\adb.exe"  # DEAD PATH (sirch): no adb.exe on this host
SERIAL = "R5CY308WZVK"


def sh(cmd, timeout=30):
    return subprocess.run([ADB, "-s", SERIAL, "shell", cmd],
                          capture_output=True, text=True, timeout=timeout).stdout


def main():
    dump = sh("dumpsys sensorservice")

    print("=== 1. declared resolution and range ===\n")
    # the sensor list prints resolution/range on the line after the name
    lines = dump.splitlines()
    rows = []
    for i, line in enumerate(lines):
        m = re.match(r"^(?P<name>.+?)\s*\(handle=0x(?P<h>[0-9a-fA-F]+)\)"
                     r"\s*active-count", line)
        if not m:
            continue
        name, handle = m.group("name").strip(), m.group("h").lower()
        res = rng = None
        for j in range(i + 1, min(i + 4, len(lines))):
            if "maxDelay" in lines[j] or "handle=0x" in lines[j]:
                break
            mr = re.search(r"resolution=([\d.eE+-]+)", lines[j])
            mg = re.search(r"maxRange=([\d.eE+-]+)", lines[j])
            if mr:
                res = float(mr.group(1))
            if mg:
                rng = float(mg.group(1))
        if res is not None or rng is not None:
            rows.append((name, handle, res, rng))

    if not rows:
        print("  no resolution fields found in this dump format")
        # show a sample so the real format is visible
        print("  sample of the device list:")
        for line in lines[1:12]:
            print("   ", line)
    for name, handle, res, rng in rows:
        print(f"  {name[:50]:<50} 0x{handle:<8} res={res} range={rng}")

    print("\n=== 2. empirical noise on a still device ===\n")
    from abrasax.live_imu import LiveImu
    frames = list(LiveImu(serial=SERIAL).stream(count=100))
    if frames:
        for chan, idx in (("accel", slice(0, 3)), ("gyro", slice(3, 6))):
            for axis in range(3):
                vals = [f.accel[axis] if chan == "accel" else f.gyro[axis]
                        for f in frames]
                print(f"  {chan}[{axis}] mean={statistics.mean(vals):+8.4f} "
                      f"stdev={statistics.pstdev(vals):.5f}")
        vals = [f.mag[i] for f in frames for i in range(3)]
        print(f"  mag        mean={statistics.mean(vals):+8.4f} "
              f"stdev={statistics.pstdev(vals):.5f}")

    print("\n=== 3. calibration bias from the uncalibrated variants ===\n")
    from abrasax.adb_sensors import AdbSensorReader
    adb = AdbSensorReader(serial=SERIAL)
    r = adb.readings()
    for needle, label in (("magnetometer-uncalibrated", "mag"),
                          ("gyroscope-uncalibrated", "gyro"),
                          ("accelerometer-uncalibrated", "accel")):
        rd = adb.pick(r, needle)
        if rd and len(rd.values) >= 4:
            bias = rd.values[3]
            print(f"  {label:<6} bias={bias:+.4f}  "
                  f"(this much was subtracted from the calibrated value)")
        elif rd:
            print(f"  {label:<6} reported {len(rd.values)} values, no bias field")
        else:
            print(f"  {label:<6} uncalibrated variant not present")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
