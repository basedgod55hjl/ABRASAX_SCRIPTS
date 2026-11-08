import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r"C:\ABRASAX")

from abrasax.controller import Controller, Goal, Observation
from abrasax.phone_senses import build_registry

ledger = Path(tempfile.mkdtemp()) / "cycles.jsonl"

SERIAL = "R5CY308WZVK"


def observe_real():
    """Read the real sense stack and turn it into observations."""
    out = []
    reg = build_registry(serial=SERIAL)
    for row in reg.discover():
        key = row["key"]
        track = row.get("tracking") or {}
        out.append(Observation(source=key, value=track.get("state", "UNKNOWN"),
                               state="measured" if row.get("status") == "available"
                               else "unknown",
                               detail={"status": row.get("status"),
                                       "tracking": track.get("state")}))
    # a numeric metric: the IMU's observed rate
    for row in reg.discover():
        if row["key"] == "s25:imu-live":
            rate = (row.get("tracking") or {}).get("observed_rate_hz")
            if rate is not None:
                out.append(Observation("imu_rate_hz", rate, state="measured"))
    return out


def current_origin_of(target):
    # the sense stack writes measured observations
    return "measured"


applied = []


def apply_action(a):
    applied.append(a.to_dict())
    return True


c = Controller(observe=observe_real, apply=apply_action, ledger=ledger,
               current_origin_of=current_origin_of)

print("=== OBSERVE ===")
for o in c.observe():
    print(f"  {o.source:<16} {str(o.value):<12} state={o.state}")

print("\n=== JUDGE: is the IMU actually tracking at >= 40 Hz? ===")
r = c.run_cycle(Goal("imu-live-healthy", metric="imu_rate_hz",
                     threshold=40.0, direction="above"))
j = r.judgement
print(f"  verdict={j.verdict} confidence={j.confidence} basis={j.basis}")
for reason in j.reasons:
    print(f"    - {reason}")

print(f"\n=== cycle result ===")
print(f"  status={r.status} actions={len(r.actions)} "
      f"reviews={len(r.reviews)} applied={r.applied} "
      f"duration={r.duration_ms:.0f}ms")

print("\n=== ledger ===")
for line in ledger.read_text(encoding="utf-8").strip().splitlines():
    d = json.loads(line)
    print(f"  cycle={d['cycle']} layer={d['layer']} status={d['status']} "
          f"verdict={d['judgement']['verdict']} obs={len(d['observations'])}")
