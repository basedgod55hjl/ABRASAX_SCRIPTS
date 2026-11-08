"""Get the FULL fallback error chain, passing data through a file not stdout.

The previous attempt crashed with
    json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
because the child process's stdout contained extra lines (warnings, prints from the
router module) before my JSON payload. Parsing raw[3:] assumed a clean single line.

Fix: the child writes its result to a JSON file; the parent reads that file. No
stdout parsing, no truncation, no ambiguity about whether nvidia/xpl appear in the
error chain.
"""
import json
import os
import shutil
import subprocess
import sys

ROOT = r"C:\ABRASAX"
REAL = os.path.join(ROOT, "CONFIG", "llm", "providers.json")
BAK = REAL + ".fullerr2-bak"
OUTJ = os.path.join(ROOT, "LOGS", "_fallback_result.json")
PY = os.path.join(ROOT, "PYTHON", ".venv_gui", "Scripts", "python.exe")
CREATE_NO_WINDOW = 0x08000000

CHILD = r'''
import json, sys
sys.path.insert(0, r"C:\ABRASAX")
out_path = r"C:\ABRASAX\LOGS\_fallback_result.json"
result = {}
try:
    from agents.agents_hub import llm_router as R
    r = R.chat([{"role": "user", "content": "Reply with exactly: FALLBACK-OK"}],
               route="auto", max_tokens=12, timeout=40)
    result = {"ok": True,
              "routed_via": (r or {}).get("routed_via"),
              "content": ((r or {}).get("content") or "")[:40]}
except Exception as e:
    result = {"ok": False, "type": type(e).__name__, "msg": str(e)}
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(result, f)
'''

original = open(REAL, encoding="utf-8").read()
shutil.copy2(REAL, BAK)
if os.path.exists(OUTJ):
    os.remove(OUTJ)

ok = False
try:
    cfg = json.loads(original)
    cfg["providers"]["lmstudio"]["base_url"] = "http://127.0.0.1:9/v1"
    with open(REAL, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    subprocess.run([PY, "-c", CHILD], cwd=ROOT, capture_output=True, text=True,
                   timeout=200, stdin=subprocess.DEVNULL,
                   creationflags=CREATE_NO_WINDOW)

    if not os.path.exists(OUTJ):
        print("child produced no result file")
        ok = False
    else:
        d = json.load(open(OUTJ, encoding="utf-8"))
        if d.get("ok"):
            via = d.get("routed_via")
            print(f"SUCCEEDED via {via}: {d.get('content')!r}")
            ok = via != "lmstudio"
        else:
            msg = d.get("msg", "")
            print(f"{d.get('type')} ({len(msg)} chars)\n")
            for i in range(0, len(msg), 96):
                print("  " + msg[i:i + 96])
            print()
            seen = [p for p in ("lmstudio", "nvidia", "xpl") if p in msg]
            print(f"  providers appearing in the chain: {seen}")
            print(f"  nvidia attempted : {'nvidia' in msg}")
            print(f"  xpl attempted    : {'xpl' in msg}")
            ok = ("nvidia" in msg) or ("xpl" in msg)
finally:
    shutil.move(BAK, REAL)
    restored = open(REAL, encoding="utf-8").read() == original
    print(f"\nconfig restored byte-for-byte: {restored}")
    if os.path.exists(OUTJ):
        os.remove(OUTJ)
    if not restored:
        ok = False

print("\nVERDICT:")
print("  PASS -- later providers WERE attempted; earlier truncation hid it"
      if ok else
      "  FAIL -- later providers genuinely never appear in the error chain")
print("\nRESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
