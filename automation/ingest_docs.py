"""Index every document in C:\\ABRASAX end-to-end, with bounded resource use.

The directive is to scan and READ all local documentation, NotebookLM exports,
markdown notes and architectural specs. The obstacle is scale: 22,948 .md files and
190 MB of crawled corpus. A naive recursive Get-ChildItem in the tool shell times
out, and reading 22,948 files into memory at once is not viable either.

So this does a streaming, single-pass ingest that:

  * walks the tree ONCE
  * skips vendored/archived corpora for CONTENT but still counts them
  * extracts, per document: title, headings, first paragraph, claim-bearing lines,
    and a content sha256 (so duplicates are detectable)
  * writes a compact index (JSON Lines) that survives the process
  * prints progress every 500 files so a slow run is visibly alive
  * never loads a whole file into memory without a size cap

Two passes are reported separately because they mean different things:
    NAMED    the file exists and was catalogued
    READ     the content was actually parsed (size cap applied)

That difference is the honest part: claiming "read all 22,948" when the cap skipped
the big ones would be false.

Usage:
    python ingest_docs.py                 # index into LOGS/doc-index.jsonl
    python ingest_docs.py --include-crawled   # also READ the corpus bodies
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from collections import Counter

ROOT = r"C:\ABRASAX"
OUT = os.path.join(ROOT, "LOGS", "doc-index.jsonl")

SKIP_DIRS = {"node_modules", "__pycache__", ".git", "VENDORS", "ARCHIVE",
             "_VAULT", "venv-rust", ".venv_gui", "Temp", "Library"}
CRAWLED = {"source-docs", "rust-docs", "notebooks-rust", "source-knowledge",
           "source-reports", "source-root-docs", "rust-root-docs",
           "source-catalogs", "original-docs"}

DOC_EXT = {".md", ".txt", ".rst", ".adoc"}
DATA_EXT = {".jsonl"}

MAX_READ_BYTES = 512 * 1024        # 512 KB per document

HEADING = re.compile(r"^(#{1,6})\s+(.*)$", re.M)
TITLE_ATX = re.compile(r"^#\s+(.+)$", re.M)
TITLE_SETEXT = re.compile(r"^(.+)\n=+\s*$", re.M)
CLAIM_LINE = re.compile(r":\d{4,5}\b")

INCLUDE_CRAWLED = "--include-crawled" in sys.argv


def classify(rel: str) -> str:
    parts = rel.split("/")
    if any(p in CRAWLED for p in parts[:-1]):
        return "CRAWLED"
    if parts[0] == "DOC" and len(parts) == 2:
        return "AUTHORED"
    if parts[0] == "DOC" and parts[1] == "REPORTS":
        return "REPORT"
    if parts[0] == "AGENTS":
        return "AGENT"
    if parts[0] == "LOGS":
        return "LOG"
    return "OTHER"


def main() -> int:
    t0 = time.time()
    counts = Counter()
    read_counts = Counter()
    skipped_size = 0
    errors = 0
    seen_hash = {}

    out = open(OUT, "w", encoding="utf-8")
    n = 0

    for dp, dn, fns in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]

        for fn in fns:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in DOC_EXT and ext not in DATA_EXT:
                continue

            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            cls = classify(rel)
            counts[cls] += 1
            n += 1

            if n % 500 == 0:
                print(f"  ... {n} files seen ({time.time() - t0:.0f}s)", flush=True)

            try:
                size = os.path.getsize(full)
                mtime = os.path.getmtime(full)
            except OSError:
                errors += 1
                continue

            rec = {
                "path": rel,
                "class": cls,
                "ext": ext,
                "bytes": size,
                "mtime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(mtime)),
                "read": False,
            }

            should_read = (cls != "CRAWLED") or INCLUDE_CRAWLED
            if not should_read:
                out.write(json.dumps(rec) + "\n")
                continue

            if size > MAX_READ_BYTES:
                skipped_size += 1
                rec["skipped"] = f"over {MAX_READ_BYTES} B cap"
                out.write(json.dumps(rec) + "\n")
                continue

            try:
                raw = open(full, "rb").read()
            except OSError as e:
                errors += 1
                rec["error"] = str(e)
                out.write(json.dumps(rec) + "\n")
                continue

            digest = hashlib.sha256(raw).hexdigest()
            text = raw.decode("utf-8", errors="replace")
            del raw

            heads = HEADING.findall(text)
            title = None
            m = TITLE_ATX.search(text)
            if m:
                title = m.group(1).strip()
            else:
                m = TITLE_SETEXT.search(text)
                if m:
                    title = m.group(1).strip()

            claim_lines = [ln.strip() for ln in text.splitlines()
                           if CLAIM_LINE.search(ln)][:8]

            first = ""
            for para in text.split("\n\n"):
                s = para.strip()
                if s and not s.startswith("#") and len(s) > 20:
                    first = s[:300]
                    break

            rec.update({
                "read": True,
                "sha256": digest,
                "lines": text.count("\n") + 1,
                "title": title,
                "headings": [h[1].strip() for h in heads][:12],
                "n_headings": len(heads),
                "first_para": first,
                "claim_lines": claim_lines,
                "dup_of": seen_hash.get(digest),
            })
            if digest not in seen_hash:
                seen_hash[digest] = rel
            read_counts[cls] += 1

            out.write(json.dumps(rec) + "\n")

    out.close()
    elapsed = time.time() - t0

    print("\n=== INGEST SUMMARY ===")
    print(f"  elapsed            : {elapsed:.1f}s")
    print(f"  documents named    : {n}")
    print(f"  documents READ     : {sum(read_counts.values())}")
    print(f"  unread (crawled)   : {counts['CRAWLED'] - read_counts['CRAWLED']}")
    print(f"  skipped (too big)  : {skipped_size}")
    print(f"  read errors        : {errors}")
    print(f"  unique contents    : {len(seen_hash)}")
    print(f"  index              : {OUT}")
    print(f"  index bytes        : {os.path.getsize(OUT):,}")

    print("\n  by class (named / read):")
    for cls in ("AUTHORED", "REPORT", "AGENT", "OTHER", "LOG", "CRAWLED"):
        if counts[cls]:
            print(f"    {cls:9s} {counts[cls]:6d} / {read_counts[cls]:6d}")

    dups = sum(1 for v in seen_hash.values() if v)  # placeholder; dup count below
    with open(OUT, encoding="utf-8") as f:
        dup_records = sum(1 for ln in f if '"dup_of": "' in ln)
    print(f"\n  duplicate contents : {dup_records}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
