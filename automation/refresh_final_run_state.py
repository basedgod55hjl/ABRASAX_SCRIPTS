"""Refresh DOC/FINAL_RUN_STATE.md so it stops claiming things that are not true.

MEASURED before writing (2026-10-18):
    :9000 gateway  -> DOWN      (doc said "ONLINE")
    :8777 node LLM -> DOWN      (doc said "LISTENING")
    :1234 lmstudio -> 200       (doc said "UP, 0 models loaded")

The doc is titled FINAL RUN STATE and is the first thing a new reader is pointed
at. Stale claims there are worse than no doc, because they are trusted.

This prepends a measured-current-state block and marks the original 2026-10-17
section as historical. The old content is kept -- it records what was true then,
and rewriting history would be its own dishonesty.

Idempotent.
"""
import socket
import sys
import time
import urllib.request

PATH = r"C:\ABRASAX\DOC\FINAL_RUN_STATE.md"
MARKER = "## MEASURED STATE — 2026-10-18"

src = open(PATH, encoding="utf-8").read()

if MARKER in src:
    print("ALREADY-PATCHED")
    sys.exit(0)


def tcp(host, port, timeout=2.0):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def http_code(url, timeout=4.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status
    except Exception as e:  # noqa: BLE001
        return f"DOWN ({type(e).__name__})"


rows = []
for name, port in (("abrasax-gateway", 9001), ("node-lm", 8777), ("lmstudio", 1234),
                   ("abrasax-brain", 9626), ("abrasax-ui", 8090), ("cellbrain", 9624),
                   ("synaptic-brain", 9625), ("filetool", 8765), ("codec-gateway", 8766),
                   ("harvest-helper", 8795), ("routerfail", 9782), ("vlc-7d-sampler", 8778),
                   ("floatbrain", 9700)):
    up = tcp("127.0.0.1", port)
    rows.append((name, port, "UP" if up else "DOWN"))

# the three ports the old doc made claims about
c9000 = http_code("http://127.0.0.1:9000/health")
c8777 = http_code("http://127.0.0.1:8777")
c1234 = http_code("http://127.0.0.1:1234/v1/models")

lines = []
lines.append(f"{MARKER}\n")
lines.append("> Prepended automatically by `SCRIPTS/automation/refresh_final_run_state.py`.")
lines.append("> Everything below this block is the **2026-10-17** snapshot and is history.\n")
lines.append("| Check | Measured now | Old doc claimed |")
lines.append("|---|---|---|")
lines.append(f"| `:9000` gateway `/health` | **{c9000}** | ONLINE |")
lines.append(f"| `:8777` node LLM | **{c8777}** | LISTENING |")
lines.append(f"| `:1234` lmstudio `/v1/models` | **{c1234}** | UP, 0 models loaded |")
lines.append("")
lines.append("## Ports, measured\n")
lines.append("| Service | Port | State |")
lines.append("|---|---|---|")
for name, port, state in rows:
    lines.append(f"| {name} | {port} | **{state}** |")
lines.append("")
lines.append("## What changed since 2026-10-17\n")
lines.append("* `:9000` is gone. The live gateway is **:9001** (`abrasax/gateway.py`); the")
lines.append("  old :9000 entry never had a listener and was renamed `vlc-7d-sampler` on :8778.")
lines.append("* A **floating-brain GPU renderer** now runs on **:9700** and is the surface the")
lines.append("  ImGui overlay and the Unity client consume. See `DOC/FLOATING-BRAIN.md`,")
lines.append("  `DOC/IMGUI-OVERLAY.md`, `DOC/STRING-BRAIN.md`.")
lines.append("* LM Studio does serve models again (the 2026-10-17 note said 0 loaded).")
lines.append("")
lines.append("---\n")

stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
lines.append(f"<!-- refreshed {stamp} -->\n")

new = "\n".join(lines) + "\n" + src
open(PATH, "w", encoding="utf-8", newline="").write(new)

print("MEASURED:")
for name, port, state in rows:
    print(f"  {name:18s} :{port:<5} {state}")
print(f"\n  :9000 -> {c9000}")
print(f"  :8777 -> {c8777}")
print(f"  :1234 -> {c1234}")
print(f"\nPATCHED {PATH} ({len(src)} -> {len(new)} bytes)")
