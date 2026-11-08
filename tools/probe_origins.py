"""Do we actually distinguish measured / derived / inferred / simulated?

The schema says ORIGINS = (measured, derived, inferred, simulated). The question
is whether the producers USE them correctly, or whether everything is stamped
`measured` regardless of how it was obtained.

Cases that must be classified differently:
  accel            read from lsm6dsv_0              -> measured
  gravity_direction computed as unit(-accel)        -> derived
  heading_deg      computed from accel+mag          -> derived
  altitude_m       barometric formula over pressure -> derived
  rotation_vector  framework fusion of 3 sensors    -> measured (it is a real
                   sensor output) but its INPUTS are fused, so a consumer may
                   want to know; check what we currently say
  position.lat/lon provider fix                     -> measured
  anything synthetic                                 -> simulated
  a hypothesis / proposal                            -> inferred

Report what each producer actually stamps today.
"""
import json
import sys

sys.path.insert(0, r"C:\ABRASAX")

from abrasax.adb_sensors import AdbPhoneProvider, AdbSensorReader
from abrasax.live_imu import LiveImu, LiveImuProvider
from abrasax.position import PositionProvider, PositionReader
from abrasax.sensor_event import ORIGINS


def show(label, ev):
    if ev is None:
        print(f"  {label:<22} (no event)")
        return
    d = ev.to_dict()
    p = d.get("payload") or {}
    print(f"  {label:<22} origin={d.get('origin'):<10} "
          f"confidence={d.get('confidence')}")
    # what does the payload claim internally, and does it agree?
    inner = p.get("origin")
    print(f"  {'':<22} payload.origin={inner!r}  "
          f"{'AGREES' if inner == d.get('origin') else 'DISAGREES'}")
    # derived quantities carried inside a 'measured' envelope
    derived = []
    for k in ("derived", "gravity_direction", "heading_deg", "altitude_m"):
        if k in p:
            derived.append(k)
    if derived:
        print(f"  {'':<22} contains computed fields: {derived}")
        print(f"  {'':<22} but the whole event is labelled "
              f"{d.get('origin')!r}")


def main():
    print(f"schema ORIGINS = {ORIGINS}\n")

    print("=== what each producer stamps ===")
    show("s25:imu-live", LiveImuProvider(LiveImu(serial="R5CY308WZVK")).read())
    show("s25:adb", AdbPhoneProvider(AdbSensorReader(serial="R5CY308WZVK")).read())
    show("s25:position", PositionProvider(PositionReader(serial="R5CY308WZVK")).read())

    print("\n=== the problem ===")
    print("  A single event carries accel (measured), gravity_direction")
    print("  (derived), heading_deg (derived) and a barometric altitude")
    print("  (derived) under ONE origin label. A consumer reading")
    print("  origin='measured' cannot tell which numbers were observed and")
    print("  which were computed from them. The label is true of the event")
    print("  and misleading about its parts.")
    print()
    print("  There is no 'inferred' anywhere in the producers - the fourth")
    print("  origin in the schema is unused, so a hypothesis and a derived")
    print("  estimate are currently indistinguishable when both are absent.")

    print("\n=== provenance already knows the difference ===")
    from abrasax.sensor_provenance import provenance_for
    for f in ("accel", "gravity_direction", "heading_deg", "altitude_m",
              "rotation_vector"):
        s = provenance_for(f)
        if s:
            print(f"  {f:<20} provenance kind = {s.kind}")
    print("  -> the per-field truth exists; it is the EVENT-LEVEL origin")
    print("     that is too coarse to express it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
