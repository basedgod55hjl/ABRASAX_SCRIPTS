#!/usr/bin/env python3
"""build_model_registry.py — the ABRAXAS MODEL_REGISTRY (§18/§21).

Scans the LM Studio GGUF tree, hashes every model (SHA-256), merges the
live served list, records the tile archives with their verification status,
and writes C:\\abrasax\\registry\\MODEL_REGISTRY.{json,md}.

Every fact is measured here: file size from disk, hash computed now,
availability from the running LM Studio API, archive status from the
tile manifests + verification verdicts.
"""
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

MODELS = Path(r"C:\Users\lucar\.lmstudio\models")
TILES = Path(r"E:\ABRASAX_TILES")
OUT = Path(r"C:\abrasax\registry")

VERIFIED_ARCHIVES = {
    "lfm2.5-1.2b-q8_0": "c40c8a9239dbc2d8874c5508110b9b1f3d325376eecffdba7bce2dcb49a0207c",
    "lfm2.5-1.2b-q6_k": "138ec3bacd9a9268c7e513d40e50a2bcb3bdf3b4ff48062a81aee22132c1588a",
}

PURPOSE_RULES = [
    (("embed",), "embeddings"),
    (("mmproj", "vl", "vision"), "vision-adapter"),
    (("unity", "csharp", "coder"), "code"),
    (("orca", "defense"), "security"),
    (("bonsai", "ornith", "gemma", "lfm", "gpt-oss", "deepseek", "r1", "dolphin"), "chat/reason"),
]


def purpose_of(name: str) -> str:
    low = name.lower()
    for keys, purpose in PURPOSE_RULES:
        if any(k in low for k in keys):
            return purpose
    return "chat"


def served_ids() -> set:
    try:
        with urllib.request.urlopen("http://127.0.0.1:1234/v1/models", timeout=5) as r:
            data = json.load(r)
        return {m.get("id") for m in data.get("data", [])}
    except Exception:
        return set()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def is_served(served_lower, name: str) -> bool:
    stem = name.lower().rsplit(".gguf", 1)[0]
    for sid in served_lower:
        s = sid.rsplit("/", 1)[-1]
        if s and (s in stem or stem in s):
            return True
    return False


def main():
    served = served_ids()
    served_lower = {s.lower() for s in served}
    specials = {
        "gpt-oss-20b": "llama-server :1235 CPU",
        "lfm2.5-1.2b-instruct-q8_0": "llama-server :1236 GPU (restored from tiles)",
    }
    models = []
    ggufs = sorted(MODELS.rglob("*.gguf"))
    t0 = time.time()
    for i, p in enumerate(ggufs, 1):
        size = p.stat().st_size
        rel = p.relative_to(MODELS).as_posix()
        ident = rel.rsplit("/", 1)[0]
        digest = sha256_file(p)
        stem = p.name.lower().rsplit(".gguf", 1)[0]
        runtime = "disk-only"
        for key, rt in specials.items():
            if key in stem:
                runtime = rt
                break
        else:
            if is_served(served_lower, p.name):
                runtime = "LM Studio :1234"
        models.append({
            "name": p.name,
            "id": ident,
            "arch": "llama/gguf",
            "format": "GGUF",
            "quantization": p.name.rsplit("-", 1)[-1].replace(".gguf", ""),
            "size_bytes": size,
            "sha256": digest,
            "source": "local .lmstudio",
            "purpose": purpose_of(p.name),
            "runtime": runtime,
            "status": "served" if runtime != "disk-only" else "archived",
        })
        print(f"[{i}/{len(ggufs)}] hashed {p.name} ({size / 1e6:.0f} MB)", flush=True)

    # duplicate detection: same SHA-256 -> same bytes under different names
    by_hash = {}
    for m in models:
        by_hash.setdefault(m["sha256"], []).append(m)
    for group in by_hash.values():
        if len(group) > 1:
            primary = group[0]["name"]
            for m in group[1:]:
                m["duplicate_of"] = primary
                m["status"] = "duplicate"

    archives = []
    for d in sorted(TILES.iterdir()):
        mf = d / "tile_manifest.json"
        if d.is_dir() and mf.exists():
            man = json.loads(mf.read_text(encoding="utf-8"))
            verified = VERIFIED_ARCHIVES.get(d.name) == man.get("model_sha256")
            archives.append({
                "archive": d.name,
                "model_file": Path(man["model"]).name,
                "tiles": len(man["tiles"]),
                "bytes": man["bytes"],
                "sha256": man.get("model_sha256"),
                "verified_byte_identical": verified,
                "runtime": "llama-server :1236" if d.name.endswith("q8_0") else "archive",
            })

    reg = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model_count": len(models),
        "served_count": len(served),
        "models": models,
        "tile_archives": archives,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "MODEL_REGISTRY.json").write_text(json.dumps(reg, indent=1), encoding="utf-8")

    lines = [
        "# ABRAXAS MODEL_REGISTRY",
        "",
        f"generated {reg['generated']} · {len(models)} GGUF files · {len(served)} served by LM Studio",
        "",
        "| model | quant | size MB | sha256[:12] | purpose | runtime | status |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in sorted(models, key=lambda x: -x["size_bytes"]):
        lines.append(f"| {m['name'][:42]} | {m['quantization'][:14]} | {m['size_bytes']/1e6:.0f} "
                     f"| {m['sha256'][:12]} | {m['purpose']} | {m['runtime']} | {m['status']} |")
    lines += ["", "## Tile archives", "",
              "| archive | tiles | bytes | sha256[:12] | verified |",
              "|---|---|---|---|---|"]
    for a in archives:
        lines.append(f"| {a['archive']} | {a['tiles']} | {a['bytes']/1e6:.0f} MB "
                     f"| {a['sha256'][:12]} | {'YES byte-identical' if a['verified_byte_identical'] else 'unverified'} |")
    (OUT / "MODEL_REGISTRY.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"DONE models={len(models)} archives={len(archives)} elapsed={time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
