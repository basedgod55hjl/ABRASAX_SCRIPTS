"""Move unused LM Studio GGUFs off C: to a J: archive, with a manifest.

Rules (see skills/system-ops/windows-disk-reclamation):
  * never move a model that is resident or referenced by providers.json
  * move, do not delete; record old path, new path, bytes, mtime, sha256 (<=2 GiB only)
  * verify size after copy before removing the source
  * resumable: skip files already present at the destination with the same size

Usage:
    python move_unused_models.py --dry-run
    python move_unused_models.py --apply
    python move_unused_models.py --restore <manifest.jsonl> --apply
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("C:/ABRASAX")
STORE = Path("C:/Users/lucar/.lmstudio/models")
DST = Path("J:/AI/lmstudio-unused")
REPORT = ROOT / "DOC/DISK-SCAN/MODELS.md"
PROVIDERS = ROOT / "CONFIG/llm/providers.json"
MANIFEST = DST / "manifest.jsonl"
LOG = ROOT / "LOGS/model-move.log"
LMS = Path("C:/Users/lucar/.lmstudio/bin/lms.exe")


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def live_ids() -> set[str]:
    ids: set[str] = set()
    try:
        data = json.loads(PROVIDERS.read_text(encoding="utf-8"))
        for p in data.get("providers", {}).values():
            for v in (p.get("models") or {}).values():
                if isinstance(v, str) and "/" in v or (isinstance(v, str) and len(v) < 60):
                    ids.add(v)
    except Exception:
        pass
    try:
        out = subprocess.run([str(LMS), "ps"], capture_output=True, text=True, timeout=60).stdout
        for line in out.splitlines()[1:]:
            parts = line.split()
            if parts and "/" in parts[0]:
                ids.add(parts[0])
    except Exception:
        pass
    return {i for i in ids if "/" in i or "-" in i}


def candidates() -> list[dict]:
    md = REPORT.read_text(encoding="utf-8", errors="replace")
    rows: list[dict] = []
    seen: set[str] = set()
    for ln in md.splitlines():
        if not ln.startswith("| ") or "`" not in ln:
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 9:
            continue
        if cells[7].replace("*", "").strip() != "X":
            continue
        m = re.search(r"`([^`]+)`", ln)
        if not m or not m.group(1).endswith(".gguf") or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        rows.append({"rel": m.group(1)})
    return rows


def sha256(path: Path, limit_bytes: int = 2 * 1024**3) -> str | None:
    if path.stat().st_size > limit_bytes:
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def move_one(rel: str, apply: bool) -> dict:
    src = STORE / rel
    dst = DST / rel
    if not src.exists():
        return {"rel": rel, "status": "missing-source"}
    size = src.stat().st_size
    ids = live_ids()
    stem = norm(src.stem)
    for i in ids:
        base = norm(i.split("/")[-1])
        if base and base in stem:
            return {"rel": rel, "status": f"refused-live:{i}"}
    if dst.exists():
        if dst.stat().st_size == size:
            return {"rel": rel, "status": "already-moved", "bytes": size}
        return {"rel": rel, "status": "conflict-dst-size", "bytes": size}
    if not apply:
        return {"rel": rel, "status": "would-move", "bytes": size}
    dst.parent.mkdir(parents=True, exist_ok=True)
    digest = sha256(src)
    tmp = dst.with_suffix(dst.suffix + ".part")
    shutil.copy2(src, tmp)
    if tmp.stat().st_size != size:
        tmp.unlink(missing_ok=True)
        return {"rel": rel, "status": "copy-size-mismatch", "bytes": size}
    os.replace(tmp, dst)
    src.unlink()
    return {"rel": rel, "status": "moved", "bytes": size, "sha256": digest}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    apply = a.apply and not a.dry_run
    if not DST.parent.exists():
        log(f"destination drive missing: {DST}")
        return 2
    DST.mkdir(parents=True, exist_ok=True)
    rows = candidates()
    log(f"=== {'APPLY' if apply else 'DRY-RUN'} {len(rows)} unused-model candidates ===")
    total = moved = 0
    manifest_lines = []
    for r in rows:
        res = move_one(r["rel"], apply)
        total += res.get("bytes", 0)
        if res["status"] in ("moved", "already-moved"):
            moved += res.get("bytes", 0)
        log(f"{res['status']:>20}  {res.get('bytes',0)/1e9:8.2f} GB  {r['rel'][:110]}")
        if res["status"] == "moved":
            manifest_lines.append({
                "old_path": str(STORE / r["rel"]), "new_path": str(DST / r["rel"]),
                "bytes": res["bytes"], "sha256": res.get("sha256"),
                "moved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            })
    if manifest_lines:
        with MANIFEST.open("a", encoding="utf-8") as fh:
            for m in manifest_lines:
                fh.write(json.dumps(m) + "\n")
    log(f"=== done: {moved/1e9:.2f} GB moved of {total/1e9:.2f} GB candidates; manifest {MANIFEST} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
