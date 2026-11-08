"""Is mag stdev=16.8 real sensor noise, or an artifact of how I read it?

probe_uncertainty.py pooled all three mag axes into one stdev, which is wrong:
the axes have different means (~-11, +13, -40 uT), so pooling measures the
SPREAD BETWEEN AXES, not the noise on any one of them. A 50 uT field has axis
means tens of uT apart, so a pooled stdev of ~17 uT is exactly what a quiet
sensor looks like when measured this way.

Measure per axis. Also check whether the field itself is rotating (the device
may have been moved) versus the sensor being noisy.
"""
import statistics
import sys

sys.path.insert(0, r"C:\ABRASAX")

from abrasax.adb_sensors import AdbSensorReader
from abrasax.live_imu import LiveImu

import math
SERIAL = "R5CY308WZVK"

def main():
    frames = list(LiveImu(serial=SERIAL).stream(count=150))
    print(f"frames: {len(frames)}\n")

    print("per-axis, which is the honest way to measure noise:")
    for axis in range(3):
        vals = [f.mag[axis] for f in frames]
        pooled = statistics.pstdev(vals)
        diffs = [vals[i + 1] - vals[i] for i in range(len(vals) - 1)]
        # lag-1 difference stdev is robust to slow drift and reveals white noise
        noise = statistics.pstdev(diffs) / (2 ** 0.5)
        print(f"  mag[{axis}] mean={statistics.mean(vals):+8.3f} "
              f"stdev={pooled:7.3f}  white-noise est={noise:6.3f}")

    allvals = [f.mag[i] for f in frames for i in range(3)]
    print(f"\n  pooled across axes (WRONG) : stdev={statistics.pstdev(allvals):.3f}")
    print("  that number measures how far apart the axis means are, not noise")

    # is the field rotating? compare first and last third of the run
    n = len(frames)
    first = [sum(f.mag[i] for f in frames[:n // 3]) / (n // 3) for i in range(3)]
    last = [sum(f.mag[i] for f in frames[-(n // 3):]) / (n // 3) for i in range(3)]
    drift = sum(abs(first[i] - last[i]) for i in range(3))
    print(f"\n  mean field first third: {[round(v,2) for v in first]}")
    print(f"  mean field last  third: {[round(v,2) for v in last]}")
    print(f"  total drift            : {drift:.2f} uT")
    if drift > 5:
        print("  => the device moved during sampling; stdev includes real rotation")
    else:
        print("  => field is stable; the per-axis stdev is sensor noise")

    # calibration bias magnitude vs field magnitude
    r = AdbSensorReader(serial=SERIAL).readings()
    rd = AdbSensorReader(serial=SERIAL).pick(r, "magnetometer-uncalibrated")
    if rd and len(rd.values) >= 4:
        bias = abs(rd.values[3])
        import math
        truth = (sum(sum(f.mag[i] ** 2 for i in range(3)) for f in frames)
                 / len(frames)) ** 0.5
        print(f"\n  |field| ~ {truth:.2f} uT   |calibration bias| = {bias:.2f} uT")
        if bias > 0.25 * truth:
            print("  => bias is a LARGE fraction of the field: the magnetometer is")
            print("     poorly calibrated, which is a real, quantified uncertainty")
        else:
            print("  => bias is small relative to the field")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
