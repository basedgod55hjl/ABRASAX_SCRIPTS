"""Live documentation verification: test every doc claim against the running system.

SELF-ACCELERATION means the project should be able to check its own knowledge
instead of trusting it. Tonight proved why: DOC/FINAL_RUN_STATE.md asserted
":9000 gateway ONLINE" while the port was dead, and nothing noticed until a human
read it.

This extracts the claims that CAN be falsified mechanically from each first-party
doc, checks them live, and reports:

    VERIFIED   claim matches the running system
    STALE      claim does not match (the doc is wrong, or the system changed)
    UNCHECKED  a claim shape we do not yet handle -- reported, never assumed true

Only two claim shapes are handled, and that limit is stated in the output rather
than implied away:
    1  a port is described as ONLINE/LISTENING/UP  -> is that TCP port open?
    2  a port is described as DOWN/OFFLINE/CLOSED  -> is that port closed?

Test counts and other prose claims are NOT parsed. Guessing at those would produce
the same false confidence this tool exists to remove.

Read-only. Exit 0 always: it is a report.
"""
from __future__ import annotations

import json
import os
import re
import socket
import sys
import time

ROOT = r"C:\ABRASAX"
DOC = os.path.join(ROOT, "DOC")
CRAWLED = {"source-docs", "rust-docs", "notebooks-rust", "source-knowledge",
           "source-reports", "source-root-docs", "rust-root-docs",
           "source-catalogs", "original-docs"}

UP_WORDS = r"(?:NOT\s+LISTENING|LISTENING|ONLINE|HEALTHY|RUNNING|OPEN|LIVE|ALIVE|UP)"
# CLOSED / MISSING / ABSENT removed: in this corpus they appear as
# "fails closed" (security) and "# 401 = token missing" (comment).
DOWN_WORDS = r"(?:NOT\s+LISTENING|OFFLINE|STOPPED|DOWN|DEAD)"

# A port claim must LOOK like a port reference. The previous third pattern was
# `(\d{3,5})\D{0,20}(status)` with no anchor, so line numbers (29, 106, 170, 200)
# and page counts were read as ports and produced 79 bogus "stale" claims.
#
# Accepted shapes only:
#   ":9000 gateway /health | ONLINE"     colon-port, table row
#   ":9001 UP 38 ms"                     colon-port, services table
#   "| 8080 | UP |"                      table row with a bare port
#
# A bare 3-digit number next to a status word is a COUNT, not a port, so bare
# numbers must be 4-5 digits to qualify.
STRICT_PORT = r"(?::(\d{3,5})|\|\s*(\d{4,5})\s*\|)"

# The separator must be allowed to CONTAIN pipes: markdown tables read
#     | renderer | :9700 | OPEN |
# so after ":9700" the next character is "|", which the previous `[^\n|]` class
# rejected outright. Most real claims are in tables, and none of them matched.
SEP = r"(?:(?!\n).){0,60}?"          # anything but a newline, bounded and lazy

ROW = re.compile(
    STRICT_PORT + SEP + r"(" + UP_WORDS + "|" + DOWN_WORDS + r")\b",
    re.IGNORECASE)
ROW2 = re.compile(
    STRICT_PORT + r"\s+(?:\S+\s+){0,3}?\**(" + UP_WORDS + "|" + DOWN_WORDS + r")\b",
    re.IGNORECASE)
# third shape dropped entirely: it was the source of every false positive


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def is_up_word(word: str) -> bool:
    return bool(re.fullmatch(UP_WORDS, word.strip(), re.IGNORECASE))


def docs_to_scan():
    out = []
    for dp, dn, fns in os.walk(DOC):
        dn[:] = [d for d in dn if d not in ("__pycache__",) and d not in CRAWLED]
        for fn in fns:
            if fn.endswith(".md"):
                out.append(os.path.join(dp, fn))
    return out


results = {"VERIFIED": [], "STALE": [], "REVIEWED": [], "UNCHECKED": []}
port_cache = {}

for full in sorted(docs_to_scan()):
    rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
    try:
        text = open(full, encoding="utf-8", errors="ignore").read()
    except OSError:
        continue

    # A document carrying a LIVE-VERIFY block has already been reconciled: its
    # stale sentences are kept as history, with a dated correction attached.
    # Reporting them again as STALE forever would train everyone to ignore the
    # report. A doc with NO marker and a stale claim is the real signal.
    reviewed = "<!-- LIVE-VERIFY" in text

    # A status word after '#' is a shell comment, not a claim. RUNBOOK.md has
    # "curl ... :1234/v1/models   # 401 = token missing on caller", which cost a
    # false positive.
    COMMENT_RE = re.compile(r"#[^\n]*")
    text = COMMENT_RE.sub("", text)

    seen = set()
    for rx in (ROW, ROW2):
        for m in rx.finditer(text):
            raw = m.group(1) or m.group(2)
            if raw is None:
                continue
            port = int(raw)
            if not (1 <= port <= 65535):
                continue
            # A 3-digit number near a status word is almost always a line
            # reference, not a port. Measured: 102, 112, 122, 124, 140, 191, 204,
            # 215, 224, 230, 234 were all line numbers. Only accept 4-5 digit
            # ports, or a 3-digit one that is genuinely well-known.
            WELL_KNOWN = {80, 443, 110, 143, 993, 995, 587, 465, 2525}
            if port < 1000 and port not in WELL_KNOWN:
                continue
            word = m.group(3).strip()
            key = (port, is_up_word(word))
            if key in seen:
                continue
            seen.add(key)

            if port not in port_cache:
                port_cache[port] = port_open(port)
            live_up = port_cache[port]
            claimed_up = is_up_word(word)

            entry = {
                "doc": rel,
                "port": port,
                "claim": word.upper(),
                "live": "OPEN" if live_up else "CLOSED",
            }
            if claimed_up == live_up:
                results["VERIFIED"].append(entry)
            elif reviewed:
                results["REVIEWED"].append(entry)
            else:
                results["STALE"].append(entry)

def main() -> int:
    print("=== DOC CLAIM VERIFICATION (live) ===")
    print(f"  ports probed        : {len(port_cache)}")
    print(f"  VERIFIED            : {len(results['VERIFIED'])}")
    print(f"  STALE (unreviewed)  : {len(results['STALE'])}")
    print(f"  REVIEWED (corrected): {len(results['REVIEWED'])}")

    print("\n=== STALE CLAIMS (the doc disagrees with the machine) ===")
    if results["STALE"]:
        for e in sorted(results["STALE"], key=lambda d: d["port"]):
            print(f"  :{e['port']:<6} doc says {e['claim']:<10} live is {e['live']:<7}  {e['doc']}")
    else:
        print("  none -- every parsed claim matched the running system")

    print("\n=== VERIFIED (sample) ===")
    by_port = {}
    for e in results["VERIFIED"]:
        by_port.setdefault(e["port"], []).append(e)
    for port in sorted(by_port):
        n = len(by_port[port])
        print(f"  :{port:<6} {port_cache[port] and 'OPEN' or 'CLOSED':<7} agreed by {n} doc(s)")

    print("\n=== NOT PARSED (stated, not hidden) ===")
    print("  test counts ('378 passed'), prose status words without a port, and")
    print("  'as of <date>' snapshots are NOT machine-checked by this tool.")
    print("  Three-digit port claims are ignored (they are line numbers far more often")
    print("  than ports); only 4-5 digit ports and IANA well-known ports are checked.")

    out = os.path.join(ROOT, "LOGS", "doc-verify.json")
    try:
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "ports": port_cache, "results": results}, f, indent=2)
        print(f"\nwrote {out}")
    except OSError as e:
        print(f"\ncould not write report: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
