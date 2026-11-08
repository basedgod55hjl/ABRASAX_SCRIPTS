"""Aggregate the wave-1 baseline jsonl (per-file d/p/b/t) to per-drive totals."""
import os
import sys
import json
import time

BASELINE = r"C:\abrasax\logs\drive_inventory.jsonl"
DATA_DIR = r"C:\abrasax\DATA"


def main():
    ts = sys.argv[1] if len(sys.argv) > 1 else time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(DATA_DIR, "baseline_summary_%s.json" % ts)
    agg = {}
    lines = 0
    bad = 0
    t0 = time.time()
    with open(BASELINE, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            lines += 1
            try:
                obj = json.loads(line)
            except Exception:
                bad += 1
                continue
            if not isinstance(obj, dict):
                bad += 1
                continue
            d = obj.get("d")
            p = obj.get("p")
            if not isinstance(d, str) or not d:
                d = p[:1] if isinstance(p, str) and p else "?"
            d = d[:1].upper()
            if not ("A" <= d <= "Z"):
                d = "?"
            b = obj.get("b", obj.get("size", 0))
            try:
                b = int(b)
            except (TypeError, ValueError):
                b = 0
            a = agg.setdefault(d, {"files": 0, "bytes": 0})
            a["files"] += 1
            a["bytes"] += b
    summary = {
        "ts": ts,
        "baseline_path": BASELINE,
        "lines": lines,
        "bad_lines": bad,
        "parse_sec": round(time.time() - t0, 1),
        "per_drive": agg,
        "total_files": sum(v["files"] for v in agg.values()),
        "total_bytes": sum(v["bytes"] for v in agg.values()),
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
