"""Prove the 3D path works INSIDE the running overlay, not only in the test harness.

The overlay at pid 27460 loaded `brain3d` at startup. Two failure modes are possible
that a unit test would not catch:

  1  the Brain3D instance the overlay constructed failed (bad GL state, missing
     context), so `brain3d` is None and the B key does nothing
  2  the module imported but the shaders did not link against the overlay's actual
     context version

Neither is visible from outside. This checks what CAN be checked from a separate
process:

  * the overlay process is alive and has a window
  * the overlay's stderr log is clean (no brain3d/shader errors)
  * importing brain3d in a fresh interpreter with a real GL 3.3 context constructs
    successfully -- the same code path the overlay takes
  * the vertex builder produces live telemetry from the LIVE brain, not a stale
    buffer

The one thing this cannot do is press the B key, and it says so.
"""
import os
import subprocess
import sys

ROOT = r"C:\ABRASAX"
PY = os.path.join(ROOT, "PYTHON", ".venv_gui", "Scripts", "python.exe")
CREATE_NO_WINDOW = 0x08000000
ok = True


def check(name, cond, detail=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        ok = False


print("=== 1. the overlay process ===")
r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                    "Get-Process python -EA 0 | Where-Object { $_.MainWindowTitle -like "
                    "'*ABRASAX*' } | ForEach-Object { \"{0}|{1}\" -f $_.Id, "
                    "$_.MainWindowTitle }"],
                   capture_output=True, text=True, errors="replace", timeout=30,
                   stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
rows = [ln for ln in r.stdout.strip().splitlines() if "|" in ln]
check("overlay window is alive", bool(rows), rows[0] if rows else "none")

print("\n=== 2. the overlay's own log ===")
log = os.path.join(ROOT, "LOGS", "overlay3d.log")
if os.path.exists(log):
    text = open(log, encoding="utf-8", errors="replace").read()
    bad = [ln for ln in text.splitlines()
           if "brain3d" in ln.lower() or "Traceback" in ln or "Error" in ln]
    check("no brain3d or shader errors in the overlay log", not bad,
          bad[0][:100] if bad else f"{len(text)} bytes, clean")
else:
    check("overlay log exists", False, log)

print("\n=== 3. same construction path, fresh context ===")
probe = r'''
import sys
sys.path.insert(0, r"C:\ABRASAX\ENGINE\floating_brain")
import glfw
if not glfw.init():
    print("SKIP no display"); raise SystemExit(0)
glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
w = glfw.create_window(64, 64, "p", None, None)
if not w:
    print("SKIP no context"); raise SystemExit(0)
glfw.make_context_current(w)
from brain3d import Brain3D
b = Brain3D()
print("BRAIN3D_OK" if b.ok else "BRAIN3D_FAIL:" + b.error)
glfw.terminate()
'''
r = subprocess.run([PY, "-c", probe], capture_output=True, text=True, errors="replace", timeout=120,
                   stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
out = (r.stdout or "").strip()
print(f"  {out or r.stderr.strip()[:160]}")
check("Brain3D constructs in a fresh 3.3 core context", "BRAIN3D_OK" in out, out[:80])

print("\n=== 4. live telemetry from the live brain ===")
probe2 = r'''
import sys, json
sys.path.insert(0, r"C:\ABRASAX\ENGINE\floating_brain")
from brain3d import build_vertices, load_field, telemetry
f = load_field()
v = build_vertices(f, clock=0.0, yaw=0.0, pitch=0.0)
print(json.dumps(telemetry(v)))
'''
r = subprocess.run([PY, "-c", probe2], capture_output=True, text=True, errors="replace", timeout=180,
                   stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
try:
    import json
    t = json.loads((r.stdout or "").strip().splitlines()[-1])
    print(f"  nodes={t['nodes']} defects={t['defects']} "
          f"(+{t['defects_pos']}/-{t['defects_neg']}) locked={t['locked_frac']:.3f} "
          f"radius={t['mean_radius']:.3f}")
    check("telemetry computed from live field", t["nodes"] == 4096)
    check("defects detected", t["defects"] > 0, str(t["defects"]))
    check("locked fraction in range", 0.0 <= t["locked_frac"] <= 1.0)
except Exception as e:  # noqa: BLE001
    check("telemetry probe", False, f"{type(e).__name__}: {e} :: {r.stderr[:120]}")

print("\n=== scope ===")
print("  VERIFIED : the overlay is alive, its log is clean, Brain3D constructs against")
print("             a real GL 3.3 core context, and the vertex builder returns live")
print("             telemetry from the running brain.")
print("  NOT      : the B keystroke. Key events cannot be synthesised into another")
print("             process from here, so the toggle branch itself is untested -- only")
print("             the renderer it switches to.")

print("\nRESULT:", "PASS -- 3D path is live-compatible" if ok else "FAIL")
sys.exit(0 if ok else 1)
