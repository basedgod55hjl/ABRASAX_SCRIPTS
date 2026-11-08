"""Give the overlay a health endpoint and register it with the supervisor.

Why this matters: supervisor.tick() skips any service whose `port` is None, and
the overlay had no port at all -- so the ImGui overlay was invisible to the
watchdog and died unnoticed. A /health port makes it monitorable and
auto-restartable, and doubles as a real runtime probe.

Idempotent.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\ABRASAX")
OV = ROOT / "ENGINE/floating_brain/imgui_overlay.py"
SV = ROOT / "abrasax/services.py"

# ---------------------------------------------------------------- 1. overlay
src = OV.read_text(encoding="utf-8")
if "_start_health_server" not in src:
    anchor = "# ---------------------------------------------------------------------------\n# GL texture wrapper"
    if anchor not in src:
        sys.exit("overlay anchor not found")
    health = '''# ---------------------------------------------------------------------------
# Health endpoint: makes the overlay visible to the supervisor
# ---------------------------------------------------------------------------
def _start_health_server(state_ref: dict, port: int = 9627):
    """Tiny stdlib HTTP server so supervisor.py can probe this process.

    supervisor.tick() only tracks services that declare a port; without this the
    overlay runs unmonitored and its death is never repaired.
    """
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path.split("?")[0] not in ("/health", "/"):
                self.send_response(404)
                self.end_headers()
                return
            body = json.dumps({
                "ok": True,
                "service": "floating-brain-overlay",
                "frames": state_ref.get("frame_count", 0),
                "fps": round(float(state_ref.get("fps", 0.0)), 2),
                "size": [int(state_ref.get("w", 0)), int(state_ref.get("h", 0))],
                "panels": bool(state_ref.get("show_panels", True)),
                "mode_3d": bool(state_ref.get("mode_3d", True)),
                "brain_connected": bool((state_ref.get("activity") or {}).get("ts")),
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):  # silence
            return

    try:
        srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        print(f"[overlay] health port {port} unavailable: {exc}", flush=True)
        return None
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    print(f"[overlay] health on 127.0.0.1:{port}", flush=True)
    return srv


'''
    src = src.replace(anchor, health + anchor, 1)
    OV.write_text(src, encoding="utf-8")
    print("overlay: health server added")
else:
    print("overlay: already has health server")

# hook it into main() right after the window exists
src = OV.read_text(encoding="utf-8")
if "_health_srv = _start_health_server" not in src:
    hook_anchor = '    feed.start()'
    if hook_anchor not in src:
        # fall back: hook after state dict creation
        hook_anchor = '        "h": float(args.height),'
        if hook_anchor not in src:
            sys.exit("overlay hook anchor not found")
        src = src.replace(hook_anchor, hook_anchor, 1)
    if "_health_srv = _start_health_server" not in src:
        # insert before the main render loop
        loop_anchor = "    while not glfw.window_should_close(window):"
        if loop_anchor not in src:
            sys.exit("render loop anchor not found")
        src = src.replace(
            loop_anchor,
            "    state[\"frame_count\"] = 0\n"
            "    _health_srv = _start_health_server(state)\n\n" + loop_anchor,
            1,
        )
    # keep frame_count current
    fc_anchor = "        frame_count += 1"
    if fc_anchor in src and 'state["frame_count"] = frame_count' not in src:
        src = src.replace(fc_anchor, fc_anchor + '\n        state["frame_count"] = frame_count', 1)
    OV.write_text(src, encoding="utf-8")
    print("overlay: health server hooked into main loop")

# ---------------------------------------------------------------- 2. services
sv = SV.read_text(encoding="utf-8")
if "floating-brain-overlay" not in sv:
    anchor = '        "notes": "Merged-proxy failover; watchdog docs also cite merged-proxy :8790",\n    },\n]'
    if anchor not in sv:
        sys.exit("services anchor not found")
    entries = anchor.replace("    },\n]", '''    },
    {
        "id": "floating-brain-overlay", "name": "ImGui floating brain overlay",
        "category": "ui", "host": "127.0.0.1", "port": 9627, "protocol": "http",
        "entry": "ENGINE/floating_brain/imgui_overlay.py",
        "launch": "python ENGINE/floating_brain/imgui_overlay.py --width 760 --height 760 --topmost",
        "notes": "Borderless topmost OpenGL HUD; /health reports frames/fps/panels",
    },
    {
        "id": "floating-brain", "name": "GPU frame renderer",
        "category": "ui", "host": "127.0.0.1", "port": 9700, "protocol": "http",
        "entry": "ENGINE/floating_brain/cuda/bin/fb_server.exe",
        "launch": "fb_server.exe 9700 fb_kernels.cubin index.html",
        "notes": "CUDA frame server that imgui_overlay polls for /frame.png",
    },
]''')
    sv = sv.replace(anchor, entries, 1)
    SV.write_text(sv, encoding="utf-8")
    print("services: overlay + frame server registered")
else:
    print("services: already registered")
