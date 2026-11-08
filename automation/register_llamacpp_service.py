"""Register llama.cpp as a supervised, zero-cost inference service on :8083.

Phase 1 requires local serving that survives a reboot, not a manual launch.
This adds:
  * a services.py catalog entry (so `abrasax services` probes it over HTTP)
  * a supervisor AUTOSTART entry (so it is restarted when down)
  * a health path of /health, which llama-server actually serves

Idempotent. Backs up first.
"""
import ast
import shutil
import sys
from pathlib import Path

SERVICES = Path("C:/ABRASAX/abrasax/services.py")
SUPERVISOR = Path("C:/ABRASAX/SCRIPTS/automation/supervisor.py")

SVC_ENTRY = '''    {
        "id": "llamacpp-local", "name": "llama.cpp local inference (zero cost)",
        "category": "llm", "host": "127.0.0.1", "port": 8083, "protocol": "http",
        "entry": "BUILD/llamacpp/build/bin/llama-server.exe",
        "launch": "llama-server.exe --model <gguf> --port 8083 --host 127.0.0.1 -ngl 99 -c 4096",
        "notes": "Zero-cost, keyless, GPU-resident. Verified 2026-10-25: /health 200, "
                 "19.7 tok/s on LFM2.5-1.2B-Q6_K, load 3.9 s. Primary of the local route.",
    },
'''

SUP_ENTRY = '''    "llamacpp-local": {
        "cmd": [_LLAMA, "--model", _LLAMA_MODEL, "--port", "8083",
                "--host", "127.0.0.1", "-ngl", "99", "-c", "4096"],
        "cwd": _LLAMA_HOME,
    },
'''

CONSTS = '''_LLAMA_HOME = ROOT / "BUILD" / "llamacpp" / "build" / "bin"
_LLAMA = _LLAMA_HOME / "llama-server.exe"
_LLAMA_MODEL = Path(r"C:\\Users\\lucar\\.lmstudio\\models\\lmstudio-community\\LFM2.5-1.2B-Instruct-GGUF\\LFM2.5-1.2B-Instruct-Q6_K.gguf")
'''

HEALTH_ANCHOR = '    "routerfail": "/health",'


def patch_services() -> str:
    src = SERVICES.read_text(encoding="utf-8")
    if '"id": "llamacpp-local"' in src:
        return "services: already present"
    anchor = '    {\n        "id": "routerfail"'
    if anchor not in src:
        return "services: FAIL anchor missing"
    src = src.replace(anchor, SVC_ENTRY + anchor, 1)
    # health path map
    if '"llamacpp-local": "/health"' not in src:
        src = src.replace(HEALTH_ANCHOR,
                          HEALTH_ANCHOR + '\n    "llamacpp-local": "/health",', 1)
    ast.parse(src)
    SERVICES.write_text(src, encoding="utf-8")
    return "services: patched"


def patch_supervisor() -> str:
    src = SUPERVISOR.read_text(encoding="utf-8")
    if '"llamacpp-local": {' in src:
        return "supervisor: already present"
    anchor = '    "harvest-helper": {'
    if anchor not in src:
        return "supervisor: FAIL anchor missing"
    src = src.replace(anchor, SUP_ENTRY + anchor, 1)
    # constants go right after the ROOT definition
    root_line = "ROOT = "
    idx = src.find(root_line)
    if idx == -1:
        return "supervisor: FAIL ROOT not found"
    line_end = src.find("\n", idx) + 1
    src = src[:line_end] + CONSTS + src[line_end:]
    ast.parse(src)
    SUPERVISOR.write_text(src, encoding="utf-8")
    return "supervisor: patched"


def main() -> int:
    for target in (SERVICES, SUPERVISOR):
        bak = target.with_suffix(".py.bak-llamacpp")
        if not bak.exists():
            shutil.copy2(target, bak)
            print(f"backup: {bak}")

    print(patch_services())
    print(patch_supervisor())
    return 0


if __name__ == "__main__":
    sys.exit(main())
