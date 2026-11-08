"""Register LM Studio and Stability Matrix as supervised local backends.

Both are already running and verified:
  * LM Studio   :1234  -- 19-20 LLMs, OpenAI-compatible; the `lmstudio` provider
  * ComfyUI     :8188  -- SDXL image generation (novaRealityXL_ilV90)
  * imagegen    :8199  -- supervisor + prompt API in front of ComfyUI

Phase 1 already registered llamacpp-local. This adds the image stack so
ABRASAX services can depend on it instead of a paid image API, and so the
supervisor restarts it when it dies.

Note on ports: ComfyUI and imagegen are GUI-adjacent and load a 6.5 GB
checkpoint, so they are catalogued but NOT all autostarted -- starting
imagegen_server.py brings ComfyUI up behind it (supervisor loop).
"""
import ast
import shutil
import sys
from pathlib import Path

SERVICES = Path("C:/ABRASAX/abrasax/services.py")
SUPERVISOR = Path("C:/ABRASAX/SCRIPTS/automation/supervisor.py")

# DEAD PATH (sirch): AI-ImageGen existed only under the old sirch account; no local equivalent on this host.
IMG_ROOT = r"C:\abrasax\_DEAD_PATH\AI-ImageGen"

SVC_ENTRIES = '''    {
        "id": "comfyui", "name": "ComfyUI (Stability Matrix) image gen",
        "category": "media", "host": "127.0.0.1", "port": 8188, "protocol": "http",
        "entry": r"C:\\abrasax\\_DEAD_PATH\\AI-ImageGen\\Data\\Packages\\ComfyUI\\main.py",
        "launch": "venv\\\\Scripts\\\\python.exe -s main.py --port 8188 --listen 127.0.0.1",
        "optional": True,
        "notes": "Stability Matrix portable package. Models resolve via "
                 "extra_model_paths.yaml -> Data/Models. Verified 2026-10-25: /system_stats 200, "
                 "SDXL novaRealityXL_ilV90 generated a real 832x1216 PNG in ~4.5 min on a 6 GB card.",
    },
    {
        "id": "imagegen", "name": "Image-gen prompt server (supervises ComfyUI)",
        "category": "media", "host": "127.0.0.1", "port": 8199, "protocol": "http",
        "entry": r"C:\\abrasax\\_DEAD_PATH\\AI-ImageGen\\scripts\\imagegen_server.py",
        "launch": "start /MIN <comfy venv python> scripts\\\\imagegen_server.py",
        "optional": True,
        "notes": "/api/health reports comfy state + restart count; /api/generate queues a render "
                 "and /api/status?id= polls it. Starting this pulls ComfyUI up automatically.",
    },
'''

SUP_ENTRY = '''    "imagegen": {
        "cmd": [_IMG_PY, str(_IMG_ROOT / "scripts" / "imagegen_server.py")],
        "cwd": _IMG_ROOT,
    },
'''

CONSTS = '''_IMG_ROOT = Path(r"C:\\abrasax\\_DEAD_PATH\\AI-ImageGen")
_IMG_PY = _IMG_ROOT / "Data" / "Packages" / "ComfyUI" / "venv" / "Scripts" / "python.exe"
'''

HEALTH_ANCHOR = '    "llamacpp-local": "/health",'


def patch_services() -> str:
    src = SERVICES.read_text(encoding="utf-8")
    if '"id": "comfyui"' in src:
        return "services: already present"
    anchor = '    {\n        "id": "routerfail"'
    if anchor not in src:
        return "services: FAIL anchor missing"
    src = src.replace(anchor, SVC_ENTRIES + anchor, 1)
    if '"imagegen": "/api/health"' not in src:
        src = src.replace(HEALTH_ANCHOR,
                          HEALTH_ANCHOR + '\n    "imagegen": "/api/health",\n    "comfyui": "/system_stats",',
                          1)
    ast.parse(src)
    SERVICES.write_text(src, encoding="utf-8")
    return "services: patched"


def patch_supervisor() -> str:
    src = SUPERVISOR.read_text(encoding="utf-8")
    if '"imagegen": {' in src:
        return "supervisor: already present"
    anchor = '    "harvest-helper": {'
    if anchor not in src:
        return "supervisor: FAIL anchor missing"
    src = src.replace(anchor, SUP_ENTRY + anchor, 1)
    idx = src.find("ROOT = ")
    line_end = src.find("\n", idx) + 1
    src = src[:line_end] + CONSTS + src[line_end:]
    ast.parse(src)
    SUPERVISOR.write_text(src, encoding="utf-8")
    return "supervisor: patched"


def main() -> int:
    for t in (SERVICES, SUPERVISOR):
        b = t.with_suffix(".py.bak-local-backends")
        if not b.exists():
            shutil.copy2(t, b)
            print(f"backup: {b}")
    print(patch_services())
    print(patch_supervisor())
    return 0


if __name__ == "__main__":
    sys.exit(main())
