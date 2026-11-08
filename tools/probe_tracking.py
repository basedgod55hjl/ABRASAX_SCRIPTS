"""Characterise the stream properly, then derive tracking from it.

read_one() opens a fresh TCP connection per frame, so pacing it in a Python loop
yields ~1 frame per connection (11 frames in 10 s) - that measures connection
setup, not the sensor. Use stream() and cut it off by wall-clock.

Then answer the real question: is "tracking" derivable from the vocabularies we
already publish (status / sync_status / quality), or is it a fourth axis?
"""
import statistics
import sys
import threading
import time

sys.path.insert(0, r"C:\ABRASAX")

from abrasax.freshness import from_epoch_ms
from abrasax.live_imu import LiveImu

SERIAL = "R5CY308WZVK"
WINDOW_S = 5.0


def collect(window_s=WINDOW_S, limit=1000):
    """Stream frames for `window_s` seconds."""
    imu = LiveImu(serial=SERIAL)
    out = []
    stop = threading.Event()

    def timer():
        stop.wait(window_s)

    t = threading.Thread(target=timer, daemon=True)
    t.start()
    for f in imu.stream():
        out.append(f)
        if stop.is_set() or len(out) >= limit:
            break
    return out


def main():
    frames = collect()
    print("=== a real 5-second window ===\n")
    if len(frames) < 20:
        print(f"only {len(frames)} frames")
        return 1

    ts = [f.t_ms for f in frames]
    dts = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
    dts = [d for d in dts if 0 < d < 1000]

    print(f"  frames            : {len(frames)}")
    print(f"  interval mean     : {statistics.mean(dts):.2f} ms")
    print(f"  interval stdev    : {statistics.pstdev(dts):.2f} ms")
    print(f"  max gap           : {max(dts)} ms")
    print(f"  duplicate stamps  : {sum(1 for d in dts if d == 0)}")
    print(f"  achieved rate     : {len(frames)/WINDOW_S:.1f} Hz")

    acc = [tuple(round(v, 3) for v in f.accel) for f in frames]
    uniq = len(set(acc))
    print(f"\n  distinct accel triples : {uniq} / {len(acc)}")
    print(f"  value changes          : {len(acc) - uniq}")

    ages = [from_epoch_ms(f.t_ms, stale_after_s=2.0).age_s for f in frames[-5:]]
    print(f"  age, last 5 frames     : {', '.join(f'{a:.3f}s' for a in ages)}")

    # ---- derive tracking state -----------------------------------------
    last_age = from_epoch_ms(frames[-1].t_ms, stale_after_s=2.0).age_s
    rate = len(frames) / WINDOW_S
    moved = uniq / len(acc)

    if last_age > 10.0:
        state = "LOST"
    elif last_age > 2.0:
        state = "STALE"
    elif len(frames) < 20:
        state = "ACQUIRING"
    elif rate < 0.5 * 50:
        state = "DEGRADED"          # arriving, but far below the claimed rate
    elif moved < 0.02:
        state = "STILL"             # current samples, values not changing
    else:
        state = "TRACKING"

    print(f"\n=== derived state: {state} ===")
    print(f"  evidence: age={last_age:.3f}s rate={rate:.1f}Hz "
          f"change_ratio={moved:.3f}")

    print("\n=== is this derivable from the existing vocabularies? ===\n")
    print("  status       'available'  = connected")
    print("  sync_status  'unsynced'   = clock not aligned")
    print("  quality      'poor'       = confidence low")
    print()
    print("  None of the three says whether samples are STILL ARRIVING NOW.")
    print("  A source can be available+unsynced+poor and be perfectly live, or")
    print("  available+synced+ok and be 2 hours stale. Tracking is a fourth")
    print("  axis: liveness of the stream, independent of quality or clock.")
    print()
    print("  The trap this classification avoids: a still phone delivers")
    print("  identical values 50x/sec. 'Value unchanged' must mean STILL,")
    print("  not DEAD - otherwise every stationary device reads as broken.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
