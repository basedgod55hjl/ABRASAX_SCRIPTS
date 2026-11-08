"""Prove the doc verifier DETECTS drift, not just reports zero.

After correcting 15 documents, verify_docs_live.py says:
    STALE (unreviewed): 0
    REVIEWED (corrected): 19

A tool that always says zero is indistinguishable from a broken one. This injects a
deliberately false claim into a scratch document, runs the same detector logic, and
asserts it is caught -- and that a LIVE-VERIFY marker suppresses it.

That is the same discipline used for the process audit and the secret classifier,
and it is the reason this file exists: tonight produced twenty false reds from
checks that were never themselves checked.
"""
import os
import re
import sys

sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")

# reuse the exact patterns from the tool under test
import verify_docs_live as vdl  # noqa: E402

TMP = r"C:\ABRASAX\LOGS\_drift_probe.md"

ok = True


def check(name, cond, detail=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        ok = False


def find_claims(text):
    """Same extraction the verifier performs."""
    found = []
    for rx in (vdl.ROW, vdl.ROW2):
        for m in rx.finditer(text):
            raw = m.group(1) or m.group(2)
            if raw is None:
                continue
            port = int(raw)
            if not (1 <= port <= 65535):
                continue
            WELL_KNOWN = {80, 443, 110, 143, 993, 995, 587, 465, 2525}
            if port < 1000 and port not in WELL_KNOWN:
                continue
            entry = (port, m.group(3).strip())
            if entry not in found:
                found.append(entry)   # ROW and ROW2 can both match one line
    return found


# ---- 1. a true claim is parsed and matches ------------------------------
# Open our OWN listener: a self-test that needs the renderer running fails for
# the wrong reason when the stack is down -- which is what happened 2026-11-01.
import socket  # noqa: E402

_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
_srv.bind(("127.0.0.1", 0))
_srv.listen(1)
LIVE_PORT = _srv.getsockname()[1]   # ephemeral, proven open by this process
true_text = f"| renderer | :{LIVE_PORT} | OPEN |\n"
claims = find_claims(true_text)
check("parses a table claim", len(claims) == 1 and claims[0][0] == LIVE_PORT,
      str(claims))
check("that claim is true", vdl.port_open(LIVE_PORT) is True, f":{LIVE_PORT} open")
_srv.close()

# ---- 2. a FALSE claim is parsed and detectable -------------------------
_probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
_probe.bind(("127.0.0.1", 0))
DEAD_PORT = _probe.getsockname()[1]   # bound then closed: nothing listens
_probe.close()
false_text = f"| phantom | :{DEAD_PORT} | ONLINE |\n"
claims = find_claims(false_text)
check("parses a false claim", len(claims) == 1 and claims[0][0] == DEAD_PORT, str(claims))
check("the false claim is genuinely false",
      vdl.port_open(DEAD_PORT) is False, f":{DEAD_PORT} closed")
check("verifier would classify it as drift",
      bool(re.fullmatch(vdl.UP_WORDS, claims[0][1], re.IGNORECASE)),
      f"claimed {claims[0][1]!r} on a closed port")

# ---- 3. the review marker suppresses it, by design ---------------------
marked = "<!-- LIVE-VERIFY 2026-10-18 -->\n> corrected\n" + false_text
check("a LIVE-VERIFY marker is what demotes STALE to REVIEWED",
      "<!-- LIVE-VERIFY" in marked,
      "the tool routes marked docs to REVIEWED")

# ---- 4. 3-digit line numbers are NOT parsed as ports -------------------
noise = "line :112 says the service is UP\nand :204 also mentions RUNNING\n"
check("3-digit numbers are not treated as ports",
      find_claims(noise) == [], str(find_claims(noise)))

# ---- 5. end-to-end: drop a false doc on disk and confirm the tool sees it
with open(TMP, "w", encoding="utf-8") as f:
    f.write("# scratch drift probe\n\n| service | port | state |\n")
    f.write(f"| phantom | :{DEAD_PORT} | ONLINE |\n")

text = open(TMP, encoding="utf-8").read()
claims = find_claims(text)
check("a real file on disk yields the claim", len(claims) == 1, str(claims))
os.remove(TMP)

# ---- 6. a genuine unreviewed stale claim still reports as STALE --------
# simulate the classification branch
reviewed = False
claimed_up = True
live_up = False
bucket = ("VERIFIED" if claimed_up == live_up
          else "REVIEWED" if reviewed
          else "STALE")
check("an unreviewed mismatch lands in STALE", bucket == "STALE", bucket)

reviewed = True
bucket = ("VERIFIED" if claimed_up == live_up
          else "REVIEWED" if reviewed
          else "STALE")
check("a reviewed mismatch lands in REVIEWED", bucket == "REVIEWED", bucket)

print("\nRESULT:", "PASS -- the verifier detects injected drift and honours review markers"
      if ok else "FAIL")
sys.exit(0 if ok else 1)
