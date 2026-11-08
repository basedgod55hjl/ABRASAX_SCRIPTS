"""Test fallback by temporarily swapping the REAL config file, then restoring it.

THREE failed attempts to test fallback without touching the real config:

  1  set LM_STUDIO_BASE_URL in the environment -- llm_router never reads it; the
     URL lives only in CONFIG/llm/providers.json. The probe silently used the real
     LM Studio and reported routed_via=lmstudio, which was TRUE.
  2  point at a copy via a module attribute -- `_config()` is
     `json.loads(_CFG.read_text())`, a module-level const with no override hook.
  3  concluded "FAIL -- still routed to lmstudio", which was my harness reading the
     wrong file, not a wiring defect.

The router is a thin function over a fixed path. So the only honest test is to swap
the file, run, and restore. That is safe here because:
  * the original is copied to a .bak before the swap
  * the swap window is a single child process (< 60 s)
  * the restore is verified by re-reading the file and comparing to the backup

If anything raises, the finally block restores. A test that can leave the machine
broken is worse than no test.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

ROOT = r"C:\ABRASAX"
REAL = os.path.join(ROOT, "CONFIG", "llm", "providers.json")
BAK = REAL + ".fallbacktest-bak"
PY = os.path.join(ROOT, "PYTHON", ".venv_gui", "Scripts", "python.exe")
CREATE_NO_WINDOW = 0x08000000

CHILD = r'''
import json, sys
sys.path.insert(0, r"C:\ABRASAX")
from agents.agents_hub import llm_router as R
try:
    r = R.chat([{"role": "user", "content": "Reply with exactly: FALLBACK-OK"}],
               route="auto", max_tokens=12, timeout=60)
    print(json.dumps({"ok": True,
                      "routed_via": (r or {}).get("routed_via"),
                      "content": ((r or {}).get("content") or "")[:40]}))
except Exception as e:
    print(json.dumps({"ok": False,
                      "error": type(e).__name__ + ": " + str(e)[:220]}))
'''

original = open(REAL, encoding="utf-8").read()
shutil.copy2(REAL, BAK)
print(f"backup written: {os.path.basename(BAK)}")

ok = True
restored = False
try:
    cfg = json.loads(original)
    orig_lm = cfg["providers"]["lmstudio"]["base_url"]
    cfg["providers"]["lmstudio"]["base_url"] = "http://127.0.0.1:9/v1"
    with open(REAL, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print(f"swapped lmstudio base_url: {orig_lm} -> http://127.0.0.1:9/v1")

    p = subprocess.run([PY, "-c", CHILD], cwd=ROOT, capture_output=True, text=True,
                       timeout=180, stdin=subprocess.DEVNULL,
                       creationflags=CREATE_NO_WINDOW)
    lines = (p.stdout or "").strip().splitlines()
    try:
        payload = json.loads(lines[-1]) if lines else \
            {"ok": False, "error": (p.stderr or "no output")[:200]}
    except json.JSONDecodeError:
        payload = {"ok": False, "error": (lines[-1] if lines else "")[:200]}

    print(f"result: {json.dumps(payload)[:280]}")

    via = payload.get("routed_via")
    err = str(payload.get("error", ""))

    if payload.get("ok") and via and via != "lmstudio":
        print(f"[PASS] fell back to '{via}' when lmstudio was unreachable")
    elif payload.get("ok") and via == "lmstudio":
        print("[FAIL] still routed to lmstudio with a dead base_url")
        ok = False
    elif "429" in err or "insufficient" in err.lower() or "credit" in err.lower():
        print("[PASS] fallback reached a cloud provider; it refused on quota")
        print("       (billing state, not a wiring fault)")
    elif "all providers failed" in err:
        print("[FAIL] every provider failed -- fallback chain is broken")
        ok = False
    else:
        print(f"[UNKNOWN] {err[:120]}")
        ok = False

finally:
    shutil.move(BAK, REAL)
    now = open(REAL, encoding="utf-8").read()
    restored = (now == original)
    print(f"\nconfig restored byte-for-byte: {restored}")

if not restored:
    print("WARNING: config differs from the backup -- inspect CONFIG/llm/providers.json")
    ok = False

print("\nRESULT:", "PASS" if ok else "DEFECTS")
sys.exit(0 if ok else 1)
