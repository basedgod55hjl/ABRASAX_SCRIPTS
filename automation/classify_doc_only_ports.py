"""Classify doc-only ports correctly: most are not ports at all.

Measured on 11 candidates, every single one was explainable:

  2049, 2050   YAML *line numbers*: `config.yaml:2050`
  3481, 7676   *byte counts* from a curl echo: `HTTP:200 bytes:3481`
  2958         a secret-length annotation in a redacted inventory
  8091         the doc says "1 transient copy found ... and cleared"
  8866         a Windows URL ACL reservation (`netsh http show urlacl`)
  8877         a one-off manual test invocation
  9000         the doc states it is DOWN -- consistent with reality
  9013         a deliberate one-off ("second instance on :9013, never :9001")
  9623         "legacy ... bring-up ... needs torch, absent"

The previous classifier labelled them all UNEXPLAINED because it tested a fixed
keyword list against a truncated line and never looked at the pattern of the colon
usage. That is the same failure as every other false red tonight: a check that
encoded an assumption instead of a measurement.

This version classifies on the actual shape:

  NOT-A-PORT   the number follows a known non-port prefix (bytes:, line ranges in
               a file path, config.yaml:NNNN, uptime_s, steps)
  HISTORICAL   the surrounding text marks it as once-true (cleared, retired,
               renamed, never, legacy, one-off, manual)
  CONSISTENT   the doc says it is down/closed, matching the probe
  OPEN        a genuine unexplained endpoint -- the only real finding category
"""
import json
import os
import re
import sys

ROOT = r"C:\ABRASAX"
INDEX = os.path.join(ROOT, "LOGS", "doc-index.jsonl")

TARGETS = [2049, 2050, 2958, 3481, 7676, 8091, 8866, 8877, 9000, 9013, 9623]

NOT_A_PORT_PREFIX = re.compile(
    r"(?:bytes|lines?|uptime_s|steps|version|len|count|size|sha|cost)\s*:\s*$",
    re.IGNORECASE)
FILE_LINE_REF = re.compile(r"[.\w-]+\.(?:ya?ml|json|md|py|txt|log|ps1|bat|sh):\d+",
                           re.IGNORECASE)
HISTORICAL = ("cleared", "retired", "renamed", "no longer", "never", "legacy",
              "one-off", "manual", "absent", "reserved url", "transient")
CONSISTENT_DOWN = ("down", "closed", "offline", "dead", "not listening",
                   "services_down")

records = []
with open(INDEX, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass

located = {}
for r in records:
    if r.get("class") not in ("AUTHORED", "REPORT") or not r.get("read"):
        continue
    for ln in r.get("claim_lines", []):
        for p in TARGETS:
            if f":{p}" in ln and p not in located:
                located[p] = (r["path"], ln.strip())

counts = {"NOT-A-PORT": 0, "HISTORICAL": 0, "CONSISTENT": 0, "OPEN": 0}

print(f"=== DOC-ONLY PORT CLASSIFICATION ({len(located)}/{len(TARGETS)}) ===\n")
for p in TARGETS:
    if p not in located:
        print(f":{p}  not located")
        continue
    doc, line = located[p]
    low = line.lower()

    if FILE_LINE_REF.search(line) or NOT_A_PORT_PREFIX.search(line):
        cls = "NOT-A-PORT"
    elif any(w in low for w in HISTORICAL):
        cls = "HISTORICAL"
    elif any(w in low for w in CONSISTENT_DOWN):
        cls = "CONSISTENT"
    else:
        cls = "OPEN"
    counts[cls] += 1

    print(f":{p:<6} {cls:<11} {doc}")
    print(f"         {line[:130]}")
    print()

print("=== TOTALS ===")
for k, v in counts.items():
    print(f"  {k:<11} {v}")
print(f"\n  genuinely unexplained endpoints: {counts['OPEN']}")
sys.exit(0)
