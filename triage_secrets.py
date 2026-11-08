"""scripts/triage_secrets.py — split real exposures from false positives.

The publish gate (tools.abx.repo._secret_risk) is intentionally blunt: it flags
every secret-shaped filename. This triage classifies each hit so the gate can
report an *actionable* list instead of blocking on vendored certificates.

    BLOCK   live credential that could leave the box (root .env, *_keys_probe)
    IGNORE  vendored test fixtures / certificates inside third-party source
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx import repo  # noqa: E402

BLOCK_EXACT = {".env"}
VENDOR_MARKERS = (
    ".venv/", "site-packages/", "src/vlc-3.0.24/", "node_modules/", "BUILD/llamacpp/",
    "VENDORS/", "_VAULT/", "test/samples/", "vendor/",
)


def classify(rel: str) -> str:
    if any(marker in rel for marker in VENDOR_MARKERS):
        return "IGNORE"
    if Path(rel).name in BLOCK_EXACT or rel.endswith("_keys_probe.json"):
        return "BLOCK"
    if rel.startswith("SYSTEMS/source-runtime/.abrasax/"):
        return "BLOCK"
    return "REVIEW"


def main() -> int:
    hits = []
    for pattern in repo.SECRET_GLOBS:
        for path in ROOT.rglob(pattern):
            if ".git" in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            hits.append({"file": rel, "class": classify(rel), "bytes": path.stat().st_size})
    hits.sort(key=lambda h: (h["class"] != "BLOCK", h["class"] != "REVIEW", h["file"]))
    counts: dict[str, int] = {}
    for h in hits:
        counts[h["class"]] = counts.get(h["class"], 0) + 1
    out = ROOT / "LOGS" / "secrets_triage.json"
    out.write_text(json.dumps({"counts": counts, "hits": hits}, indent=2), encoding="utf-8")
    sys.stdout.write(json.dumps({"counts": counts}, indent=2) + "\n")
    for h in hits:
        if h["class"] != "IGNORE":
            sys.stdout.write(f"  {h['class']:<6} {h['file']} ({h['bytes']} B)\n")
    return 0 if counts.get("BLOCK", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
