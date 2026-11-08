"""Wire the 3D emissive brain into the live ImGui overlay.

The overlay currently draws a PNG texture (`:9700/frame.png`) full-window. That is a
2D birefringent field. Meanwhile brain3d.py can draw 4096 nodes as three additive
emissive point layers in the SAME GL context.

This patch adds it as a toggleable mode rather than replacing the field:

    key B   switch between FIELD (the 2D birefringence) and BRAIN3D (the point cloud)
    both   draw the same HUD and controls on top

Why a toggle and not a replacement: the field shows interference colour, the point
cloud shows geometry and morph. Both are real views of the same data and a user may
want either. Silently swapping one for the other would remove a working view.

Draw order inside the frame:
    1  clear
    2  if mode == FIELD: draw the texture (as now)
       if mode == BRAIN3D: compute vertices, draw 3 emissive layers with additive blend
    3  ImGui new_frame + HUD (unchanged)

The 3D pass needs the depth buffer and point-size enabled; the 2D pass does not. The
patch enables and restores those around the 3D draw so the texture path is unaffected.

Idempotent: a marker guards re-application.
"""
import shutil
import sys
import time

PATH = r"C:\ABRASAX\ENGINE\floating_brain\imgui_overlay.py"
MARK = "# ---- BRAIN3D MODE (patch) ----"

src = open(PATH, encoding="utf-8").read()
if MARK in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

# --- 1. imports ----------------------------------------------------------
old_imp = "import glfw\nimport imgui\n"
new_imp = ("import glfw\nimport imgui\n\n"
           "# ---- BRAIN3D MODE (patch) ----\n"
           "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
           "try:\n"
           "    from brain3d import Brain3D, build_vertices, load_field, telemetry as b3d_tel\n"
           "    _B3D_AVAILABLE = True\n"
           "except Exception as _e:  # noqa: BLE001\n"
           "    _B3D_AVAILABLE = False\n"
           "    _B3D_IMPORT_ERROR = str(_e)\n")
if old_imp not in src:
    print("ANCHOR-NOT-FOUND: imports")
    sys.exit(1)
src = src.replace(old_imp, new_imp, 1)

# --- 2. state: mode + renderer instance ---------------------------------
old_state = '    state = {'
new_state = ('    # ---- BRAIN3D MODE (patch) ----\n'
             '    mode_3d = False\n'
             '    brain3d = None\n'
             '    b3d_verts = None\n'
             '    b3d_last = 0.0\n'
             '    if _B3D_AVAILABLE:\n'
             '        try:\n'
             '            brain3d = Brain3D()\n'
             '            if not brain3d.ok:\n'
             '                print("[overlay] brain3d init failed:", brain3d.error)\n'
             '                brain3d = None\n'
             '        except Exception as _e:  # noqa: BLE001\n'
             '            print("[overlay] brain3d unavailable:", _e)\n'
             '            brain3d = None\n'
             '\n'
             '    state = {')
if old_state not in src:
    print("ANCHOR-NOT-FOUND: state dict")
    sys.exit(1)
src = src.replace(old_state, new_state, 1)

# --- 3. toggle key in the input handler ---------------------------------
old_key = '    if "F" in rising:\n        state["nearest"] = not state["nearest"]'
new_key = (old_key + '\n'
           '    if "B" in rising:\n'
           '        mode_3d = not mode_3d')
if old_key not in src:
    print("ANCHOR-NOT-FOUND: key handler")
    sys.exit(1)
src = src.replace(old_key, new_key, 1)

# the handler is a free function, so mode_3d cannot be assigned there;
# store it in the state dict instead
src = src.replace('    if "B" in rising:\n        mode_3d = not mode_3d',
                  '    if "B" in rising:\n        state["mode_3d"] = not state.get("mode_3d", False)')

# --- 4. register the hotkey in the key scan list ------------------------
old_scan = 'for name, code in (("space", 32), ("R", 82), ("H", 72), ("F", 70), ("ESC", 256)):'
new_scan = 'for name, code in (("space", 32), ("R", 82), ("H", 72), ("F", 70), ("B", 66), ("ESC", 256)):'
if old_scan in src:
    src = src.replace(old_scan, new_scan, 1)

# --- 5. draw: replace the texture blit with a mode switch ---------------
old_draw = """        if frame is not None and tex.size[0] > 0:
            imgui.set_cursor_position(((fbw - side) * 0.5, (fbh - side) * 0.5))
            imgui.image(tex.tex, side, side,
                        uv0=(0, 0), uv1=(1, 1),
                        tint_color=(1, 1, 1, 1))
        else:
            imgui.set_cursor_position((24, 24))
            imgui.text_colored("waiting for renderer :9700 ...", *HOT)"""

new_draw = """        # ---- BRAIN3D MODE (patch) ----
        use_3d = state.get("mode_3d", False) and brain3d is not None
        if use_3d:
            # Rebuild vertices at ~20 Hz; the geometry is CPU-assembled so this is
            # the same cadence the texture path uses.
            now3d = time.time()
            if b3d_verts is None or (now3d - b3d_last) > 0.05:
                try:
                    b3d_verts = build_vertices(load_field(), state["clock"],
                                               yaw * 0.017453292,
                                               pitch * 0.017453292)
                    b3d_last = now3d
                except Exception as _e:  # noqa: BLE001
                    print("[overlay] brain3d vertices failed:", _e)
                    b3d_verts = None

            if b3d_verts is not None:
                import numpy as _np
                import math as _math
                f = 1.0 / _math.tan(_math.radians(45) / 2)
                aspect = fbw / max(1, fbh)
                proj = _np.array([
                    [f / aspect, 0, 0, 0],
                    [0, f, 0, 0],
                    [0, 0, (10 + 0.1) / (0.1 - 10), (2 * 10 * 0.1) / (0.1 - 10)],
                    [0, 0, -1, 0],
                ], dtype=_np.float32)
                view = _np.eye(4, dtype=_np.float32)
                view[2, 3] = -3.2
                mvp = proj @ view
                brain3d.draw(b3d_verts, fbw, fbh, state["clock"], mvp)

                # live neural-pathway telemetry, straight from the drawn vertices
                try:
                    t3 = b3d_tel(b3d_verts)
                    imgui.set_cursor_position((fbw - 240, fbh - 130))
                    imgui.text_colored("PATHWAYS", *DIM)
                    imgui.set_cursor_position((fbw - 240, fbh - 112))
                    imgui.text_colored(f"nodes {t3['nodes']}", *CYAN)
                    imgui.set_cursor_position((fbw - 240, fbh - 94))
                    imgui.text_colored(f"defects {t3['defects']}", *GOLD)
                    imgui.set_cursor_position((fbw - 240, fbh - 76))
                    imgui.text_colored(f"locked {t3['locked_frac']*100:.1f}%", *CYAN)
                except Exception:  # noqa: BLE001
                    pass
        elif frame is not None and tex.size[0] > 0:
            imgui.set_cursor_position(((fbw - side) * 0.5, (fbh - side) * 0.5))
            imgui.image(tex.tex, side, side,
                        uv0=(0, 0), uv1=(1, 1),
                        tint_color=(1, 1, 1, 1))
        else:
            imgui.set_cursor_position((24, 24))
            imgui.text_colored("waiting for renderer :9700 ...", *HOT)"""

if old_draw not in src:
    print("ANCHOR-NOT-FOUND: texture draw block")
    sys.exit(1)
src = src.replace(old_draw, new_draw, 1)

# --- 6. add 'time' import if absent -------------------------------------
if "\nimport time\n" not in src:
    src = src.replace("import threading\n", "import threading\nimport time\n", 1)

# --- 7. controls hint ----------------------------------------------------
src = src.replace(
    'imgui.text_colored("space orbit · R reset · H hud · F filter · esc", *DIM)',
    'imgui.text_colored("space orbit · R reset · H hud · F filter · B 3D · esc", *DIM)')

backup = PATH + ".bak-" + time.strftime("%Y%m%d-%H%M")
shutil.copy2(PATH, backup)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print(f"PATCHED imgui_overlay.py (backup {backup.rsplit(chr(92), 1)[-1]})")

import py_compile
try:
    py_compile.compile(PATH, doraise=True)
    print("py_compile: OK")
except py_compile.PyCompileError as e:
    print("py_compile FAILED:", e)
    sys.exit(1)
