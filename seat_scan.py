"""scripts/seat_scan.py — run the abx.seat rubric in a detached process.

    python -m scripts.seat_scan --models deepseek-flash,deepseek-v4-pro --out LOGS/seat.json

Writes the full JSON envelope to --out plus a one-line verdict to --out.summary,
so a long scan can be polled without holding a terminal.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=None, help="comma list; default = provider catalogs")
    ap.add_argument("--route", default="auto")
    ap.add_argument("--out", default="LOGS/seat.json")
    args = ap.parse_args(argv)

    from tools.abx import seat

    result = seat.seat(models=args.models, route=args.route).to_dict()
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    rows = result["data"].get("results", [])
    lines = [f"tool={result['tool']} ok={result['ok']} dur={result['duration_s']}s"]
    for row in rows:
        lines.append(f"  {row['model']:<44} score={row['score']:<5} "
                     f"lat={row.get('latency_s')}s pass={[k for k, v in row['checks'].items() if v.get('pass')]}")
    lines.append(f"SEAT={result['data'].get('seat')}")
    summary = "\n".join(lines)
    Path(str(out) + ".summary").write_text(summary + "\n", encoding="utf-8")
    sys.stdout.write(summary + "\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
