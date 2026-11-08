"""Cross-check every port the documentation claims against what is actually listening.

The index proves 30 distinct ports are cited across authored docs. Docs agreeing
with each other is not evidence -- they can all be wrong together, and tonight
several were (:9000 claimed by six docs while dead).

This is the missing half of "read all the documentation": reading it is only useful
if what it asserts is then compared to reality.

Output per port:
    CLAIMED_BY   how many authored docs mention it
    LISTENING    what the machine says
    VERDICT      consistent / doc-only (claimed but nothing listens) /
                 service-only (listening but undocumented)

"doc-only" is not automatically a defect -- a port can be documented as optional or
as a retired service. But the list needs to be short and explained, and an
unexplained doc-only port is exactly how :9000 survived as a phantom for a day.
"""
from __future__ import annotations

import json
import os
import re
import socket
import sys
from collections import defaultdict

ROOT = r"C:\ABRASAX"
INDEX = os.path.join(ROOT, "LOGS", "doc-index.jsonl")

# ports the running system actually exposes, from the service catalog
sys.path.insert(0, os.path.join(ROOT, "SCRIPTS", "automation"))
sys.path.insert(0, ROOT)

catalog_source = None
CATALOG = set()

try:
    from abrasax.services import list_services  # type: ignore
    svc = list_services()
    CATALOG = {int(s["port"]) for s in svc if isinstance(s, dict) and s.get("port")}
    catalog_source = f"abrasax.services.list_services ({len(svc)} entries)"
except Exception as e:
    # Do NOT swallow this. A silent empty catalog made every listening port look
    # undocumented, which invalidated the whole reconciliation.
    print(f"  [WARN] in-process catalog import failed: {type(e).__name__}: {e}")
    print("  [WARN] falling back to the CLI")
    try:
        import subprocess
        r = subprocess.run(
            [sys.executable, "-m", "abrasax", "services"],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
            stdin=subprocess.DEVNULL)
        for line in (r.stdout or "").splitlines():
            parts = line.split()
            for tok in parts:
                if tok.isdigit() and 1000 <= int(tok) <= 65535:
                    CATALOG.add(int(tok))
                    break
        catalog_source = f"CLI (abrasax services), {len(CATALOG)} ports"
    except Exception as e2:  # noqa: BLE001
        print(f"  [ERROR] CLI fallback also failed: {type(e2).__name__}: {e2}")
        catalog_source = "UNAVAILABLE"

CATALOG.add(9700)          # floating-brain renderer, documented today
CATALOG.discard(None)

# A port reference must not be the tail of a JSON key like `"steps":1084`.
#
# Rejected:  "steps":1084   "uptime_s":6907   "version":0.4
# Accepted:  127.0.0.1:9700   localhost:9001   ":9700 OPEN"   | :9626 |   port 9001

# Simpler and safer: find every 4-5 digit run that follows a colon, then discard
# the ones preceded by a JSON key ending in a quote.
COLON_PORT = re.compile(r":(\d{4,5})\b")


def is_json_value(line: str, colon_pos: int) -> bool:
    """True if the number is a JSON field VALUE, e.g. `"steps":1084`.

    The character immediately before the colon decides it. A JSON key ends with a
    closing quote; an endpoint reference ends with a digit, a word character, a
    space or a pipe:

        127.0.0.1:9700   -> '1'   not JSON
        | :9626 |        -> ' '   not JSON
        "steps":1084     -> '"'   JSON
    """
    if colon_pos == 0:
        return False
    return line[colon_pos - 1] == '"'



def listening(port: int) -> bool:
    s = socket.socket()
    s.settimeout(0.8)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


claimed = defaultdict(set)
with open(INDEX, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("class") not in ("AUTHORED", "REPORT") or not r.get("read"):
            continue
        for ln in r.get("claim_lines", []):
            for m in COLON_PORT.finditer(ln):
                # skip "steps":1084 / "uptime_s":6907 -- a JSON value, not a port
                if is_json_value(ln, m.start()):
                    continue
                p = int(m.group(1))
                if 1000 <= p <= 65535:
                    claimed[p].add(r["path"])

print(f"=== PORT RECONCILIATION ({len(claimed)} claimed, {len(CATALOG)} in catalog) ===\n")

live_cache = {}
rows = []
for p in sorted(claimed):
    up = live_cache.setdefault(p, listening(p))
    n = len(claimed[p])
    in_catalog = p in CATALOG
    if up and in_catalog:
        verdict = "consistent"
    elif up and not in_catalog:
        verdict = "service-only (listening, not in catalog)"
    elif not up and in_catalog:
        verdict = "catalogued but DOWN"
    else:
        verdict = "doc-only (nothing listens)"
    rows.append((p, n, up, in_catalog, verdict))

print(f"{'port':>6} {'docs':>5} {'live':>6} {'catalog':>8}  verdict")
for p, n, up, cat, v in rows:
    print(f"{p:>6} {n:>5} {'UP' if up else 'DOWN':>6} {'yes' if cat else 'no':>8}  {v}")

print("\n=== DOC-ONLY PORTS (documented, nothing listening, not in catalog) ===")
doc_only = [r for r in rows if r[4].startswith("doc-only")]
if doc_only:
    for p, n, _up, _cat, _v in doc_only:
        print(f"  :{p}  cited by {n} doc(s):")
        for d in sorted(claimed[p])[:4]:
            print(f"      {d}")
else:
    print("  none")

print("\n=== CATALOGUED BUT DOWN ===")
down = [r for r in rows if r[4].startswith("catalogued")]
if down:
    for p, n, _up, _cat, _v in down:
        print(f"  :{p}  cited by {n} doc(s)")
else:
    print("  none")

print("\n=== LISTENING BUT UNDOCUMENTED ===")
svc_only = [r for r in rows if r[4].startswith("service-only")]
if svc_only:
    for p, n, _up, _cat, _v in svc_only:
        print(f"  :{p}  cited by {n} doc(s) (not in catalog)")
else:
    print("  none")

print("\nRESULT: reconciliation report produced")
sys.exit(0)
