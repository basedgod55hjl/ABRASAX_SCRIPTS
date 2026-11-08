"""What history do we actually have, and can it answer questions?

Having a JSONL file is not the same as having history. This checks:
  1. structure      - what fields exist, are they consistent
  2. time coverage  - span, gaps, real intervals
  3. provenance     - does each record say which sensor/transport produced it
  4. queryability   - can we answer "what was the temperature trend" and
                      "when did the phone start tracking"
  5. honesty        - are simulated records distinguishable from measured ones
"""
import collections
import json
import pathlib
import sys

sys.path.insert(0, r"C:\ABRASAX")

DATA = pathlib.Path(r"C:\ABRASAX\DATA\sensors")
PULSE = pathlib.Path(r"C:\ABRASAX\LOGS\pulse.jsonl")


def load(path):
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def main():
    files = sorted(DATA.glob("*.jsonl"))
    print(f"=== sensor journal: {len(files)} file(s) ===\n")
    allrec = []
    for f in files:
        recs = load(f)
        print(f"  {f.name}: {len(recs)} records, {f.stat().st_size:,} bytes")
        allrec.extend(recs)

    if not allrec:
        print("  no records")
        return 1

    print(f"\n  total: {len(allrec)}")

    print("\n=== structure ===\n")
    keys = collections.Counter()
    for r in allrec:
        keys.update(r.keys())
    for k, n in keys.most_common(24):
        print(f"  {k:<20} present in {n:4d}/{len(allrec)}")

    print("\n=== time coverage ===\n")
    stamps = []
    for r in allrec:
        for k in ("received_at", "captured_at", "timestamp"):
            v = r.get(k)
            if isinstance(v, str) and v:
                stamps.append(v)
                break
    if stamps:
        print(f"  first : {stamps[0]}")
        print(f"  last  : {stamps[-1]}")
        print(f"  count : {len(stamps)}")
        uniq = len(set(stamps))
        print(f"  unique: {uniq}  ({len(stamps)-uniq} duplicates)")

    print("\n=== provenance in history ===\n")
    has_origin = sum(1 for r in allrec if r.get("origin"))
    has_sensor = sum(1 for r in allrec if r.get("sensor_id") or r.get("provider_id"))
    has_prov = sum(1 for r in allrec if r.get("provenance"))
    has_conf = sum(1 for r in allrec if "confidence" in r)
    has_fresh = sum(1 for r in allrec if r.get("freshness"))
    n = len(allrec)
    print(f"  origin        {has_origin:4d}/{n}")
    print(f"  sensor_id     {has_sensor:4d}/{n}")
    print(f"  provenance    {has_prov:4d}/{n}   <- which chip produced it")
    print(f"  confidence    {has_conf:4d}/{n}")
    print(f"  freshness     {has_fresh:4d}/{n}   <- when the device updated it")

    print("\n=== can it answer a real question? ===\n")
    # pressure trend, if present
    pres = [r for r in allrec if isinstance(r.get("env"), list) and r["env"] and r["env"][0]]
    if pres:
        vals = [r["env"][0] for r in pres]
        print(f"  pressure readings : {len(vals)}")
        print(f"  min / max / first / last : "
              f"{min(vals):.2f} / {max(vals):.2f} / {vals[0]:.2f} / {vals[-1]:.2f} hPa")
        print(f"  span              : {max(vals)-min(vals):.3f} hPa")
    else:
        print("  no pressure history")

    origins = collections.Counter(r.get("origin", "?") for r in allrec)
    print(f"\n  by origin        : {dict(origins)}")

    print("\n=== pulse history ===\n")
    if PULSE.exists():
        precs = load(PULSE)
        ticks = [r for r in precs if r.get("event") == "tick"]
        print(f"  records    : {len(precs)}")
        print(f"  ticks      : {len(ticks)}")
        if ticks:
            print(f"  first tick : {ticks[0].get('ts')}")
            print(f"  last tick  : {ticks[-1].get('ts')}")
            ing = [t.get("ingested", 0) for t in ticks]
            print(f"  ingested   : total {sum(ing)}, per tick "
                  f"{min(ing)}-{max(ing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
