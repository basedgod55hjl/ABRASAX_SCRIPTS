#!/usr/bin/env python3
"""abrasax snapshot -- manifest-driven CODE + DOC + CONFIG archive.

Produces, in C:\\ABRASAX\\_VAULT\\snapshots\\:
    abrasax-code-YYYYmmdd-HHMM.zip   deterministic-ordered deflate archive
    abrasax-code-YYYYmmdd-HHMM.MANIFEST.json
        per-file sha256 + size, skipped-file log with reasons, and a top-level
        ``manifest_sha256`` over the sorted (path, sha256) list.

Stdlib only, so it runs under any Python >= 3.8 including a bare interpreter.

Commands
    python snapshot.py                     # build a snapshot
    python snapshot.py --dry-run           # show what would be captured, write nothing
    python snapshot.py --verify ZIP        # reopen zip, rehash every file, compare
    python snapshot.py --verify ZIP --sample 25 --seed 7
    python snapshot.py --verify-tree DIR   # check an extracted tree against a manifest
    python snapshot.py --list              # list snapshots with sizes
    python snapshot.py --prune-keep 3      # OPT-IN: delete all but newest N (never run implicitly)

Exit codes: 0 ok / verified, 1 verification failure, 2 usage or safety refusal.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import random
import re
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "abrasax-snapshot-manifest/1"
ROOT = Path(__file__).resolve().parents[2]          # C:\ABRASAX
SNAP_DIR = ROOT / "_VAULT" / "snapshots"
ZIP_PREFIX = "abrasax-code-"

# ---------------------------------------------------------------- include rules
# (base dir relative to ROOT, globs relative to that base, recursive?)
INCLUDE = [
    ("abrasax",                    ("**/*",),                 True),
    ("SCRIPTS",                    ("**/*",),                 True),
    ("TESTS/python",               ("**/*",),                 True),
    ("DOC",                        ("*.md", "*.json"),        False),
    ("CONFIG",                     ("*.json",),               False),
    ("CONFIG/llm",                 ("*.json",),               False),
    ("CONFIG/hardware",            ("*.json",),               False),
    ("CONFIG/claude",              ("*.json",),               False),
    ("ENGINE/kernels/cuda/src",    ("**/*",),                 True),
    ("ENGINE/kernels/cuda/verify", ("**/*",),                 True),
    ("UI/abrasax-ui/web",          ("**/*",),                 True),
    ("AGENTS/ROLES",               ("**/*",),                 True),
    ("RUST/abrasax_rs/src",        ("**/*",),                 True),
    ("RUST/abrasax_rs",            ("Cargo.toml",),           False),
    (".",                          ("pyproject.toml", ".gitignore", "*.md"), False),
]

# ---------------------------------------------------------------- exclude rules
EXCLUDE_DIRS = {
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "node_modules", "target", "dist", "build", ".git", ".hg", ".svn",
    ".venv", "venv", "site-packages", "ARCHIVE", "VENDORS", "_VENDORS",
    ".loki", "logs", "LOGS", ".next", ".turbo", "coverage",
}

BINARY_EXT = {
    ".exe", ".dll", ".so", ".dylib", ".bin", ".sys", ".msi", ".pyd", ".obj",
    ".lib", ".o", ".a", ".class", ".jar", ".wasm",
    ".gguf", ".safetensors", ".cubin", ".ptx", ".pt", ".pth", ".onnx",
    ".npz", ".npy", ".pkl", ".h5", ".feather", ".parquet", ".db", ".sqlite",
    ".sqlite3", ".pyc", ".pyo", ".zip", ".7z", ".gz", ".tgz", ".tar", ".xz",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tif", ".tiff",
    ".mp3", ".mp4", ".wav", ".flac", ".ogg", ".webm", ".mov", ".avi", ".mkv",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".iso", ".img", ".log",
}

# Name rules target files that *hold* secrets (env/keys/credentials), not prose.
# Markdown that merely discusses secrets is left to the content scan below.
SECRET_NAME_GLOBS = (
    ".env", ".env.*", "*.env", "*.pem", "*.key", "*.pfx", "*.p12", "*.kdbx",
    "credentials*.json", "*credential*.json", "*secret*.json", "*secret*.env",
    "*token*.txt", "*secret*.toml", "*secret*.ini", "*secret*.cfg",
    "secrets.*", "id_rsa*", "id_ed25519*", ".npmrc", ".netrc", ".pgpass",
    "combined_env_files*", "*.jks", "*.keystore",
)

# Placeholder values in tests/docs must not silently drop a real source file.
PLACEHOLDER_HINTS = ("...", "xxx", "your", "example", "dummy", "placeholder",
                     "fake", "redact", "abcd", "changeme", "sample")

SECRET_CONTENT = (
    re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(rb"\bsk-[A-Za-z0-9_\-]{20,}"),
    re.compile(rb"\bsk-ant-[A-Za-z0-9_\-]{20,}"),
    re.compile(rb"\bghp_[A-Za-z0-9]{30,}"),
    re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{30,}"),
    re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(rb"\bxox[baprs]-[A-Za-z0-9\-]{10,}"),
    re.compile(rb"\bAIza[0-9A-Za-z_\-]{35}\b"),
)

MAX_FILE_BYTES = 4 * 1024 * 1024          # single-file cap
MAX_TOTAL_BYTES = 1_500_000_000           # hard guard: 1.5 GB unpressed
BINARY_SNIFF_BYTES = 8192


# ---------------------------------------------------------------- helpers
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest_digest(pairs) -> str:
    """sha256 over the sorted '<path>\\t<sha256>' list -- the manifest's identity."""
    body = "\n".join(f"{p}\t{h}" for p, h in sorted(pairs))
    return sha256_bytes(body.encode("utf-8"))


def is_binary(blob: bytes) -> bool:
    return b"\x00" in blob[:BINARY_SNIFF_BYTES]


def secret_name(name: str) -> bool:
    low = name.lower()
    return any(fnmatch.fnmatch(low, g.lower()) for g in SECRET_NAME_GLOBS)


def secret_content(blob: bytes) -> str | None:
    """Return the matched credential-looking token, or None."""
    head = blob[:65536]
    for pat in SECRET_CONTENT:
        m = pat.search(head)
        if m:
            return m.group(0).decode("utf-8", "replace")
    return None


def is_placeholder(token: str) -> bool:
    low = token.lower()
    return any(h in low for h in PLACEHOLDER_HINTS)


def skip_reason(path: Path) -> str | None:
    name = path.name
    low_name = name.lower()
    if any(part in EXCLUDE_DIRS for part in path.parts):
        return "excluded-dir"
    if low_name.startswith(".hermes-tmp") or low_name.startswith("~$") \
            or low_name.endswith((".tmp", ".part", ".crdownload", ".swp")):
        return "transient-file"
    if secret_name(name):
        return "secret-filename"
    if path.suffix.lower() in BINARY_EXT:
        return "binary-or-artifact"
    return None


def collect():
    """Return (files: list[Path], skipped: list[(relpath, reason)]) under ROOT."""
    files, skipped = [], []
    seen = set()
    for base, globs, recursive in INCLUDE:
        bdir = ROOT / base
        if not bdir.exists():
            skipped.append((base + "/", "missing-in-tree"))
            continue
        for g in globs:
            pattern = g
            it = bdir.rglob(pattern[3:]) if (recursive and pattern.startswith("**/")) else bdir.glob(pattern)
            for p in it:
                if not p.is_file():
                    continue
                rel = p.relative_to(ROOT)
                if rel in seen:
                    continue
                reason = skip_reason(rel)
                if reason:
                    skipped.append((rel.as_posix(), reason))
                    continue
                seen.add(rel)
                files.append(p)
    return files, skipped


# ---------------------------------------------------------------- build
def build(dry_run: bool = False) -> int:
    t0 = time.time()
    files, skipped = collect()
    entries, skipped_entries, warnings = [], [], []
    payload = {}                     # rel -> bytes
    total = 0

    for p in sorted(files, key=lambda x: x.relative_to(ROOT).as_posix().lower()):
        rel = p.relative_to(ROOT).as_posix()
        try:
            size = p.stat().st_size
        except OSError as exc:
            skipped_entries.append({"path": rel, "reason": f"stat-failed: {exc}"})
            continue
        if size > MAX_FILE_BYTES:
            skipped_entries.append({"path": rel, "reason": f"oversize {size} > {MAX_FILE_BYTES}"})
            continue
        try:
            blob = p.read_bytes()
        except OSError as exc:
            skipped_entries.append({"path": rel, "reason": f"read-failed: {exc}"})
            continue
        if is_binary(blob):
            skipped_entries.append({"path": rel, "reason": "binary-content"})
            continue
        hit = secret_content(blob)
        if hit:
            if is_placeholder(hit):
                warnings.append({"path": rel, "reason": "placeholder-credential-pattern",
                                 "sample": hit[:12] + "..."})
            else:
                skipped_entries.append({"path": rel, "reason": "secret-content-pattern"})
                continue
        total += len(blob)
        if total > MAX_TOTAL_BYTES:
            print(f"REFUSED: snapshot would exceed {MAX_TOTAL_BYTES} bytes", file=sys.stderr)
            return 2
        payload[rel] = blob
        entries.append({"path": rel, "sha256": sha256_bytes(blob), "size": len(blob),
                        "mtime": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)
                                         .isoformat(timespec="seconds")})

    for rel, reason in skipped:
        skipped_entries.append({"path": rel, "reason": reason})

    digest = manifest_digest((e["path"], e["sha256"]) for e in entries)
    by_dir = {}
    for e in entries:
        top = e["path"].split("/")[0] if "/" in e["path"] else "(root)"
        d = by_dir.setdefault(top, {"files": 0, "bytes": 0})
        d["files"] += 1
        d["bytes"] += e["size"]

    print(f"root:            {ROOT}")
    print(f"files:           {len(entries)}")
    print(f"source bytes:    {total:,}")
    print(f"manifest_sha256: {digest}")
    print("by area:")
    for top in sorted(by_dir, key=lambda k: -by_dir[k]["bytes"]):
        d = by_dir[top]
        print(f"  {top:<24} {d['files']:>4} files  {d['bytes']:>12,} B")
    if skipped_entries:
        reasons = {}
        for s in skipped_entries:
            reasons[s["reason"]] = reasons.get(s["reason"], 0) + 1
        print(f"skipped:         {len(skipped_entries)} ({', '.join(f'{k}={v}' for k, v in sorted(reasons.items()))})")
    if warnings:
        print(f"warnings:        {len(warnings)} placeholder credential pattern(s) retained "
              f"({', '.join(w['path'] for w in warnings[:3])})")

    if dry_run:
        print("dry-run: nothing written")
        return 0
    if not entries:
        print("REFUSED: nothing to snapshot", file=sys.stderr)
        return 2

    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    zip_path = SNAP_DIR / f"{ZIP_PREFIX}{stamp}.zip"
    n = 1
    while zip_path.exists():                       # never overwrite an existing snapshot
        n += 1
        zip_path = SNAP_DIR / f"{ZIP_PREFIX}{stamp}-{n}.zip"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in sorted(payload):
            zi = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            zf.writestr(zi, payload[rel])

    zip_bytes = zip_path.stat().st_size
    zip_hash = sha256_file(zip_path)
    manifest = {
        "schema": SCHEMA,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "created_local": datetime.now().isoformat(timespec="seconds"),
        "root": str(ROOT),
        "zip": {"name": zip_path.name, "bytes": zip_bytes, "sha256": zip_hash},
        "counts": {"files": len(entries), "source_bytes": total,
                   "zip_bytes": zip_bytes,
                   "ratio": round(total / zip_bytes, 2) if zip_bytes else None},
        "rules": {
            "include": [{"base": b, "globs": list(g), "recursive": r} for b, g, r in INCLUDE],
            "exclude_dirs": sorted(EXCLUDE_DIRS),
            "max_file_bytes": MAX_FILE_BYTES,
            "max_total_bytes": MAX_TOTAL_BYTES,
            "secret_name_globs": list(SECRET_NAME_GLOBS),
        },
        "manifest_sha256": digest,
        "files": entries,
        "skipped": sorted(skipped_entries, key=lambda s: s["path"]),
        "warnings": sorted(warnings, key=lambda w: w["path"]),
    }
    man_path = zip_path.with_suffix(".MANIFEST.json")
    man_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")

    print(f"zip:             {zip_path}  ({zip_bytes:,} B)")
    print(f"manifest:        {man_path}  ({man_path.stat().st_size:,} B)")
    print(f"compression:     {total / zip_bytes:.2f} : 1" if zip_bytes else "")
    print(f"elapsed:         {time.time() - t0:.2f}s")
    return 0


# ---------------------------------------------------------------- verify
def load_manifest(zip_path: Path) -> dict:
    man_path = zip_path.with_suffix(".MANIFEST.json")
    if not man_path.exists():
        raise SystemExit(f"manifest not found beside zip: {man_path}")
    return json.loads(man_path.read_text(encoding="utf-8"))


def verify_zip(zip_path: Path, sample: int = 0, seed: int | None = None) -> int:
    man = load_manifest(zip_path)
    entries = man["files"]
    print(f"zip:             {zip_path}")
    print(f"manifest:        {zip_path.with_suffix('.MANIFEST.json').name}")
    print(f"manifest entries:{len(entries)}")

    stored = man["manifest_sha256"]
    recomputed = manifest_digest((e["path"], e["sha256"]) for e in entries)
    if stored != recomputed:
        print(f"FAIL manifest_sha256 stored={stored} recomputed={recomputed}")
        return 1
    print(f"manifest_sha256: {stored}  (recomputed from entries: match)")

    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        expected = {e["path"] for e in entries}
        missing = sorted(expected - names)
        extra = sorted(names - expected)
        bad = zf.testzip()

    if missing or extra or bad:
        print(f"FAIL archive structure: missing={len(missing)} extra={len(extra)} corrupt={bad}")
        for p in (missing + extra)[:10]:
            print(f"  {p}")
        return 1
    print(f"archive entries: {len(names)}  (matches manifest, CRC ok)")

    targets = entries
    if sample and sample < len(entries):
        rnd = random.Random(seed if seed is not None else 0)
        targets = rnd.sample(entries, sample)
        print(f"sample:          {len(targets)} random files (seed={seed if seed is not None else 0})")

    mismatches = 0
    with zipfile.ZipFile(zip_path) as zf:
        for e in targets:
            got = sha256_bytes(zf.read(e["path"]))
            if sample and sample < len(entries):
                print(f"  {'ok ' if got == e['sha256'] else 'BAD'} {e['sha256'][:12]}  {e['path']}")
            if got != e["sha256"]:
                mismatches += 1
                print(f"  MISMATCH {e['path']}\n    manifest {e['sha256']}\n    actual   {got}")
    print(f"hashes checked:  {len(targets)}  mismatches: {mismatches}")
    print("RESULT:          " + ("PASS" if mismatches == 0 else "FAIL"))
    return 0 if mismatches == 0 else 1


def verify_tree(tree: Path, man_path: Path) -> int:
    man = json.loads(man_path.read_text(encoding="utf-8"))
    entries = {e["path"]: e for e in man["files"]}
    ok = missing = extra = bad = 0
    on_disk = set()
    for p in tree.rglob("*"):
        if p.is_file():
            on_disk.add(p.relative_to(tree).as_posix())
    for rel, e in entries.items():
        if rel not in on_disk:
            missing += 1
            continue
        if sha256_file(tree / rel) == e["sha256"]:
            ok += 1
        else:
            bad += 1
            print(f"  MISMATCH {rel}")
    extra = len(on_disk - set(entries))
    print(f"tree:      {tree}")
    print(f"expected:  {len(entries)}  ok: {ok}  missing: {missing}  mismatch: {bad}  extra: {extra}")
    print("RESULT:    " + ("PASS" if (missing or bad) == 0 else "FAIL"))
    return 0 if (missing or bad) == 0 else 1


def list_snapshots() -> int:
    if not SNAP_DIR.exists():
        print(f"no snapshot dir: {SNAP_DIR}")
        return 0
    zips = sorted(SNAP_DIR.glob(f"{ZIP_PREFIX}*.zip"))
    if not zips:
        print("no snapshots")
        return 0
    for z in zips:
        man = z.with_suffix(".MANIFEST.json")
        n = "-"
        d = "-"
        if man.exists():
            try:
                m = json.loads(man.read_text(encoding="utf-8"))
                n = m["counts"]["files"]
                d = m["created_local"]
            except Exception:
                pass
        print(f"{z.name:<38} {z.stat().st_size:>12,} B  files={n:<5} {d}")
    return 0


def prune(keep: int, confirm: bool = False) -> int:
    zips = sorted(SNAP_DIR.glob(f"{ZIP_PREFIX}*.zip"), key=lambda p: p.stat().st_mtime)
    drop = zips[:-keep] if keep > 0 else []
    for z in drop:
        side = z.with_suffix(".MANIFEST.json")
        if confirm:
            z.unlink()
            if side.exists():
                side.unlink()
            print(f"deleted {z.name} (+ manifest={side.exists()})")
        else:
            print(f"would delete {z.name} (+ manifest={side.exists()})  [re-run with --yes]")
    if not drop:
        print(f"nothing to prune (keeping newest {keep}, found {len(zips)})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="abrasax manifest-hashed code snapshot")
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    ap.add_argument("--verify", metavar="ZIP", help="verify a built snapshot")
    ap.add_argument("--sample", type=int, default=0, help="verify N random files only")
    ap.add_argument("--seed", type=int, default=None, help="RNG seed for --sample")
    ap.add_argument("--verify-tree", metavar="DIR", help="verify an extracted tree")
    ap.add_argument("--manifest", metavar="JSON", help="manifest for --verify-tree")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--prune-keep", type=int, default=0)
    ap.add_argument("--yes", action="store_true", help="with --prune-keep: actually delete")
    a = ap.parse_args()

    if a.list:
        return list_snapshots()
    if a.verify:
        return verify_zip(Path(a.verify), a.sample, a.seed)
    if a.verify_tree:
        mp = Path(a.manifest) if a.manifest else None
        if mp is None:
            cands = sorted(SNAP_DIR.glob(f"{ZIP_PREFIX}*.MANIFEST.json"))
            if not cands:
                print("no manifest found; pass --manifest", file=sys.stderr)
                return 2
            mp = cands[-1]
        return verify_tree(Path(a.verify_tree), mp)
    if a.prune_keep:
        return prune(a.prune_keep, a.yes)
    return build(dry_run=a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
