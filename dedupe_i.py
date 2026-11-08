"""dedupe_i.py — delete byte-identical duplicate files on I:, keep one of each.

Safety rules, enforced in code rather than asserted in a comment:
  * every candidate is re-hashed at delete time (not trusted from an earlier run),
  * a file is only removed when its SHA-256 equals the kept copy's SHA-256,
  * the kept copy is the shortest name (the un-suffixed original),
  * every decision is logged to LOGS/dedupe_I.json and printed.

    python SCRIPTS/dedupe_i.py --report     # re-hash, change nothing
    python SCRIPTS/dedupe_i.py --go         # delete the proven duplicates
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "LOGS"
DRIVE = Path("I:/")

# groups discovered by name; membership is re-proved by hash before any delete
GROUPS = [
    ["I:/v2.51.0.260929.zip", "I:/v2.51.0.260929 (1).zip"],
    ["I:/giaderza+lolagrant+1080h265.mp4", "I:/giaderza+lolagrant+1080h265 (1).mp4"],
    ["I:/Royal+Stuffing+(subtitles).mp4", "I:/Royal+Stuffing+(subtitles) (1).mp4"],
    ["I:/Amy's+Big+Wish+Episode+4+Part+4+-+Kitten+Milf.mp4",
     "I:/Amy's+Big+Wish+Episode+4+Part+4+-+Kitten+Milf (1).mp4",
     "I:/Amy's+Big+Wish+Episode+4+Part+4+-+Kitten+Milf (2).mp4"],
    ["I:/Microsoft.DataTools.AnalysisServices.vsix",
     "I:/Microsoft.DataTools.AnalysisServices (1).vsix",
     "I:/Microsoft.DataTools.AnalysisServices (2).vsix"],
    ["I:/Microsoft.DataTools.ReportingServices.vsix",
     "I:/Microsoft.DataTools.ReportingServices (1).vsix",
     "I:/Microsoft.DataTools.ReportingServices (2).vsix"],
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    go = "--go" in argv
    results = []
    freed = 0

    for group in GROUPS:
        present = [Path(p) for p in group if Path(p).exists()]
        if len(present) < 2:
            print(f"skip group (only {len(present)} present): {group[0]}")
            continue
        present.sort(key=lambda p: (len(p.name), p.name))
        keeper = present[0]
        keeper_hash = sha256(keeper)
        print(f"\nkeeper: {keeper.name}  {keeper_hash[:16]}  {keeper.stat().st_size/1e6:.0f} MB")
        for cand in present[1:]:
            cand_hash = sha256(cand)
            same = cand_hash == keeper_hash
            size = cand.stat().st_size
            row = {"keeper": str(keeper), "candidate": str(cand), "same": same,
                   "bytes": size, "deleted": False}
            if not same:
                print(f"  KEEP  {cand.name}  (hash differs {cand_hash[:16]})")
                results.append(row)
                continue
            print(f"  {'DELETE' if go else 'would delete'}  {cand.name}  {size/1e6:.0f} MB")
            if go:
                try:
                    cand.unlink()
                    row["deleted"] = True
                    freed += size
                except OSError as exc:
                    row["error"] = str(exc)
                    print(f"         failed: {exc}")
            results.append(row)

    payload = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "mode": "go" if go else "report", "freed_bytes": freed, "results": results}
    LOGS.mkdir(exist_ok=True)
    out = LOGS / "dedupe_I.json"
    out.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"\n{'freed' if go else 'would free'} {freed/1e9:.2f} GB   log: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
