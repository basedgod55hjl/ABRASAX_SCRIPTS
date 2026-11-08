"""Add the floating-brain renderer to the supervisor's AUTOSTART allowlist.

MEASURED DEFECT
  During the full test run, fb_server.exe died and nothing restarted it:

      Get-NetTCPConnection -LocalPort 9700 -State Listen  ->  0
      Get-Process fb_server                                ->  0
      LOGS/ops-state.json: signature healthy, services_down {}   <- not noticed

  Cause: the renderer is not in `abrasax.services.SERVICES`, so the ops monitor
  never probes it, and it is not in `supervisor.AUTOSTART`, so the supervisor never
  restarts it. Two of the three live surfaces (the ImGui overlay and the Unity
  client) depend on :9700, and neither notices it is gone until it asks.

  Consequence for the test suite: ten test_floating_brain.py tests skipped because
  the server was down, and the skip looks like an environment condition rather than
  the outage it was.

THE FIX
  Add "floating-brain" to AUTOSTART with the exact command the docs give:
      fb_server.exe 9700 fb_kernels.cubin index.html   (cwd = cuda/bin)

  The supervisor's existing contract then applies: probe every 30 s, restart when
  down, 180 s cooldown, port bind is the mutex (a second copy fails with
  EADDRINUSE, so no pid file is needed).

  This edits supervisor.py in the one branch the package needs, per the ownership
  rule, and backs the file up first.
"""
import os
import shutil
import sys
import time

PATH = r"C:\ABRASAX\SCRIPTS\automation\supervisor.py"
BAK = PATH + ".bak-" + time.strftime("%Y%m%d-%H%M")

src = open(PATH, encoding="utf-8").read()

if '"floating-brain"' in src:
    print("ALREADY-PATCHED: floating-brain is in AUTOSTART")
    sys.exit(0)

# insert right after the AUTOSTART opening brace so it is grouped with the rest
anchor = 'AUTOSTART: dict[str, dict] = {\n'
if anchor not in src:
    print("ANCHOR-NOT-FOUND: AUTOSTART declaration")
    sys.exit(1)

entry = (
    '    "floating-brain": {\n'
    '        # The GPU renderer that the ImGui overlay and the Unity client consume.\n'
    '        # Measured 2026-10-18: it died during a test run and nothing noticed,\n'
    '        # because it was in neither SERVICES nor AUTOSTART. Port bind is the\n'
    '        # mutex, so no pid file is needed.\n'
    '        "cmd": [str(_FB_BIN / "fb_server.exe"), "9700", "fb_kernels.cubin",\n'
    '                "index.html"],\n'
    '        "cwd": _FB_BIN,\n'
    '    },\n'
)

# _FB_BIN must exist; add it beside the other path constants if absent
if "_FB_BIN" not in src:
    const_anchor = "AUTOSTART: dict[str, dict] = {\n"
    const_def = (
        '_FB_BIN = ROOT / "ENGINE" / "floating_brain" / "cuda" / "bin"\n\n'
    )
    src = src.replace(const_anchor, const_def + const_anchor, 1)

src = src.replace(anchor, anchor + entry, 1)

shutil.copy2(PATH, BAK)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print(f"PATCHED supervisor.py (backup {os.path.basename(BAK)})")

# verify the file still parses and the key is present
import py_compile
try:
    py_compile.compile(PATH, doraise=True)
    print("py_compile: OK")
except py_compile.PyCompileError as e:
    print("py_compile FAILED:", e)
    sys.exit(1)

for i, line in enumerate(open(PATH, encoding="utf-8").read().splitlines(), 1):
    if "_FB_BIN" in line or "floating-brain" in line:
        print(f"  {i:4d}: {line.rstrip()[:88]}")
