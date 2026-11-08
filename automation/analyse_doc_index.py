"""Analyse the document index produced by ingest_docs.py.

Answers the questions the ingest exists to serve:
  * what architectural specs actually exist, and are they current?
  * which documents are byte-identical duplicates?
  * which specs contradict each other on the same port?
  * what does the NotebookLM export corpus contain, by title?
  * which authored docs have never been reconciled with the live system?

Reads LOGS/doc-index.jsonl only. Does not rescan the tree.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = r"C:\ABRASAX"
INDEX = os.path.join(ROOT, "LOGS", "doc-index.jsonl")

if not os.path.exists(INDEX):
    print("no index yet -- run ingest_docs.py first")
    sys.exit(1)

records = []
with open(INDEX, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue

print(f"=== INDEX: {len(records):,} record(s) ===")

by_class = Counter(r["class"] for r in records)
read = [r for r in records if r.get("read")]
print(f"  read: {len(read):,}   catalogued-only: {len(records) - len(read):,}")
for cls, n in by_class.most_common():
    nread = sum(1 for r in records if r["class"] == cls and r.get("read"))
    print(f"    {cls:9s} {n:6d} named / {nread:6d} read")

# ---- duplicates ---------------------------------------------------------
print("\n=== DUPLICATE CONTENT ===")
by_hash = defaultdict(list)
for r in read:
    by_hash[r["sha256"]].append(r["path"])
dups = {h: p for h, p in by_hash.items() if len(p) > 1}
print(f"  {len(dups)} duplicate group(s) covering "
      f"{sum(len(p) for p in dups.values())} file(s)")
for h, paths in sorted(dups.items(), key=lambda t: -len(t[1]))[:10]:
    size = next(r["bytes"] for r in read if r["sha256"] == h)
    print(f"    {size:8d} B  x{len(paths)}")
    for p in paths[:4]:
        print(f"        {p}")
    if len(paths) > 4:
        print(f"        ... and {len(paths) - 4} more")

# ---- architectural specs ------------------------------------------------
print("\n=== ARCHITECTURAL / SPEC DOCUMENTS (authored) ===")
SPEC_HINT = re.compile(r"architect|spec|design|system|schema|contract|blueprint",
                       re.IGNORECASE)
specs = [r for r in read
         if r["class"] in ("AUTHORED", "REPORT")
         and (SPEC_HINT.search(r["path"]) or
              any(SPEC_HINT.search(h) for h in r.get("headings", [])))]
specs.sort(key=lambda r: r["path"])
print(f"  {len(specs)} document(s)")
for r in specs[:20]:
    print(f"    {r['bytes']:7d} B  {r['n_headings']:3d} headings  {r['path']}")

# ---- port contradictions among authored docs ---------------------------
print("\n=== PORT CLAIMS ACROSS AUTHORED DOCS ===")
PORT = re.compile(r":(\d{4,5})\b")
port_docs = defaultdict(list)
for r in read:
    if r["class"] not in ("AUTHORED", "REPORT"):
        continue
    for ln in r.get("claim_lines", []):
        for m in PORT.finditer(ln):
            p = int(m.group(1))
            if 1000 <= p <= 65535:
                port_docs[p].append(r["path"])
print(f"  {len(port_docs)} distinct ports claimed")
for p in sorted(port_docs):
    docs = sorted(set(port_docs[p]))
    if len(docs) > 1:
        print(f"    :{p}  cited by {len(docs)} docs")
        for d in docs[:5]:
            print(f"        {d}")

# ---- NotebookLM corpus --------------------------------------------------
print("\n=== NOTEBOOKLM / AI EXPORT CORPUS ===")
nlm = [r for r in records if "nlm" in r["path"].lower()
       or "notebook" in r["path"].lower()]
print(f"  {len(nlm)} file(s)")
for r in nlm[:12]:
    print(f"    {r['bytes']:9d} B  read={r.get('read')}  {r['path']}")

# ---- reconciliation status ---------------------------------------------
print("\n=== AUTHORED DOCS: RECONCILED WITH LIVE SYSTEM? ===")
unrecon = []
for r in read:
    if r["class"] != "AUTHORED":
        continue
    full = os.path.join(ROOT, r["path"].replace("/", os.sep))
    try:
        head = open(full, encoding="utf-8", errors="ignore").read(4096)
    except OSError:
        continue
    if "LIVE-VERIFY" not in head and "LIVE CORRECTION" not in head:
        unrecon += [r["path"]]
print(f"  {len(unrecon)} authored doc(s) carry no LIVE-VERIFY marker:")
for p in sorted(unrecon)[:20]:
    print(f"    {p}")

# ---- most-linked / most-used terms -------------------------------------
print("\n=== TOP HEADINGS ACROSS AUTHORED DOCS ===")
heads = Counter()
for r in read:
    if r["class"] in ("AUTHORED", "REPORT"):
        for h in r.get("headings", []):
            heads[h.strip()] += 1
for h, n in heads.most_common(15):
    print(f"  {n:3d}x  {h[:80]}")

sys.exit(0)
