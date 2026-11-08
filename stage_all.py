"""scripts/stage_all.py — stage every buildable repo, bounded and self-reporting.

Unlike build_now.py --dry-run (which also stages the 3.4 GB canonical tree),
this stages only the *mapped source* rows, in plan order, and writes a stage
index with file counts and sizes so a stage can be audited without walking it.

    python scripts/stage_all.py                  # stage every source row
    python scripts/stage_all.py --skip-existing  # only rows not yet staged
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from tools.abx import repos24  # noqa: E402
import build_now  # noqa: E402

STAGE = build_now.STAGE


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--only", nargs="*", default=None)
    args = ap.parse_args(argv)

    rows = [r for r in repos24.ROWS
            if r.get("source") and r["kind"] in ("production", "shell")
            and (not args.only or r["repo"] in args.only)]

    index = []
    for row in rows:
        name = row["repo"]
        dest = STAGE / name
        if args.skip_existing and dest.exists():
            index.append({"repo": name, "state": "already-staged", "path": str(dest)})
            sys.stdout.write(f"{name:<26} already-staged\n")
            continue
        try:
            dest = build_now._stage(row)
            build_now._provenance(row, dest)
        except Exception as exc:  # noqa: BLE001
            index.append({"repo": name, "state": "failed", "error": f"{type(exc).__name__}: {exc}"})
            sys.stdout.write(f"{name:<26} FAILED {exc}\n")
            continue
        files = [p for p in dest.rglob("*") if p.is_file()]
        bak = [p for p in files if ".bak" in p.name or ".old-" in p.name]
        entry = {
            "repo": name,
            "state": "staged",
            "path": str(dest),
            "files": len(files),
            "bytes": sum(p.stat().st_size for p in files),
            "bak_files": len(bak),
            "source": row["source"],
            "kind": row["kind"],
        }
        index.append(entry)
        sys.stdout.write(f"{name:<26} staged files={entry['files']:<4} "
                         f"{entry['bytes']/1e6:6.2f} MB  bak={entry['bak_files']}\n")
        sys.stdout.flush()

    payload = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "count": len(index), "index": index}
    (ROOT / "LOGS" / "stage_index.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    bad = [e["repo"] for e in index if e["state"] == "failed"]
    total = sum(e.get("bytes", 0) for e in index)
    sys.stdout.write(f"\nSTAGE {len(index) - len(bad)}/{len(index)} ok  {total/1e6:.2f} MB  failed={bad}\n")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
