"""scripts/stage_index.py — measure every staged tree and write LOGS/stage_index.json.

Staging and measuring are separate concerns: `stage_all.py --skip-existing`
returns before it has counted anything, which made the index evidence-free.
This always walks the stage and records what is actually on disk.

Per row:
  files, bytes, bak_files (.bak/.old- artefacts), newest mtime,
  source tree from the plan, kind, and whether the stage is the canonical
  tree itself (source == "."), which must never be published from here.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from tools.abx import repos24  # noqa: E402
import build_now  # noqa: E402


def _walk(tree: Path) -> dict:
    files = [p for p in tree.rglob("*") if p.is_file()]
    bak = [p for p in files if ".bak" in p.name or ".old-" in p.name]
    newest = max((p.stat().st_mtime for p in files), default=0.0)
    exts: dict[str, int] = {}
    for p in files:
        ext = p.suffix.lower() or "(none)"
        exts[ext] = exts.get(ext, 0) + 1
    top = sorted(exts.items(), key=lambda kv: -kv[1])[:6]
    return {
        "files": len(files),
        "bytes": sum(p.stat().st_size for p in files),
        "bak_files": len(bak),
        "bak_names": [p.name for p in sorted(bak)][:10],
        "newest_mtime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(newest)) if newest else None,
        "top_extensions": top,
    }


def main() -> int:
    plan = {r["repo"]: r for r in repos24.ROWS}
    stage = build_now.STAGE
    rows = []
    if not stage.exists():
        sys.stdout.write(json.dumps({"ok": False, "error": f"stage missing: {stage}"}) + "\n")
        return 1

    for tree in sorted(p for p in stage.iterdir() if p.is_dir()):
        name = tree.name
        row = plan.get(name, {})
        measured = _walk(tree)
        entry = {
            "repo": name,
            "source": row.get("source"),
            "kind": row.get("kind"),
            "branch": row.get("branch"),
            "path": str(tree),
            "measured": True,
            "is_canonical_tree": row.get("source") == ".",
            "provenance": (tree / "PROVENANCE.md").exists(),
            **measured,
        }
        if entry["is_canonical_tree"]:
            entry["warning"] = "stage is a copy of the canonical tree; never publish from it"
        if measured["files"] <= 1:
            entry["warning"] = "empty shell: only .gitignore/PROVENANCE - nothing to publish"
        rows.append(entry)

    total_files = sum(r["files"] for r in rows)
    total_bytes = sum(r["bytes"] for r in rows)
    payload = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stage_root": str(stage),
        "count": len(rows),
        "total_files": total_files,
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / 1e6, 2),
        "warning": "ABRASAX-REBUILD dominates the total; it is the canonical tree, not a build product",
        "index": rows,
    }
    out = ROOT / "LOGS" / "stage_index.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    for r in rows:
        m = r
        sys.stdout.write(f"{m['repo']:<26} {m['files']:>6} files {m['bytes']/1e6:>9.2f} MB "
                         f"bak={m['bak_files']:<3} prov={m['provenance']} "
                         f"{m.get('warning', '')}\n")
    sys.stdout.write(f"\nTOTAL {total_files} files  {total_mb if False else payload['total_mb']} MB  "
                     f"({out})\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
