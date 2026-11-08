"""Float the overlay: transparent field, readable glowing strings, more HUD.

Three changes, each tied to an observed problem:

1. REMOVE THE WINDOW RECTANGLE ("let it float").
   glClearColor is already (0,0,0,0) and TRANSPARENT_FRAMEBUFFER is already
   hinted, so the window itself was never the dark box. The box is the brain
   field PNG from fb_server: it renders on a near-black background, and
   measured captures are dominated by (12,12,12). Keying luminance to alpha
   leaves the neurons and edges opaque and drops the black field to fully
   transparent, so only the graphics sit on the desktop.

2. ENHANCE THE STRINGS.
   Once the background is transparent, thin 13px text over an arbitrary desktop
   is unreadable. Two fixes: a 1px drop shadow (black at 80%) so text survives
   any wallpaper, and set_window_font_scale for size. This binding has no
   add_font_from_file_ttf, so a custom TTF is not available -- scale + shadow is
   what the API actually offers.

3. ADD MORE.
   New readouts: crash-free uptime, total frames, an fps sparkline drawn as
   bars, and a VRAM bar from the live activity feed. All values come from
   existing state; nothing is invented.

Every anchor is asserted; the patch aborts loudly rather than silently no-oping.
"""
from __future__ import annotations

import pathlib
import sys

P = pathlib.Path(r"C:\ABRASAX\ENGINE\floating_brain\imgui_overlay.py")
src = P.read_text(encoding="utf-8")
orig = len(src)


def sub(old: str, new: str, label: str) -> None:
    global src
    n = src.count(old)
    if n != 1:
        sys.exit(f"ABORT [{label}]: expected 1, found {n}")
    src = src.replace(old, new, 1)
    print(f"  ok  {label}")


# ---------------------------------------------------------------- helpers ---
HELPERS = '''
# --- float / legibility helpers ---------------------------------------------
def _float_alpha(arr):
    """Key the field's near-black background to transparent, in place.

    The renderer draws on a dark field; the window is already configured for a
    transparent framebuffer, so dropping the field leaves only the neurons and
    edges floating. Luminance ramp keeps antialiased edges soft instead of
    cutting them with a hard threshold.
    """
    try:
        lum = arr[..., :3].max(axis=2).astype(np.float32)
        lo, hi = 10.0, 52.0
        t = np.clip((lum - lo) / (hi - lo), 0.0, 1.0)
        arr[..., 3] = (t * 255.0).astype(np.uint8)
    except Exception:  # noqa: BLE001
        pass
    return arr


def _txt(pos, s, color, scale=None, shadow=True):
    """Draw text with a drop shadow so it stays readable on any wallpaper.

    A transparent window means the background is whatever the user is looking
    at; unstroked 13px text disappears against light desktops.
    """
    if shadow:
        imgui.set_cursor_position((float(pos[0]) + 1.0, float(pos[1]) + 1.0))
        imgui.text_colored(s, 0.0, 0.0, 0.0, 0.80)
    imgui.set_cursor_position((float(pos[0]), float(pos[1])))
    if scale is not None:
        imgui.set_window_font_scale(scale)
        imgui.text_colored(s, *color)
        imgui.set_window_font_scale(1.0)
    else:
        imgui.text_colored(s, *color)


def _spark(dl, x, y, w, h, values, color):
    """FPS sparkline: one filled bar per sample, scaled to 100 fps."""
    try:
        n = len(values)
        if not n:
            return
        step = w / float(n)
        for i, v in enumerate(values):
            bh = max(1.0, h * min(1.0, float(v) / 100.0))
            dl.add_rect_filled(x + i * step, y + h - bh,
                               x + i * step + max(1.0, step - 1.0), y + h, *color)
    except Exception:  # noqa: BLE001
        pass


def _bar(dl, x, y, w, h, frac, fg, bg):
    """Horizontal meter with a dim track, used for VRAM."""
    try:
        dl.add_rect_filled(x, y, x + w, y + h, *bg)
        f = max(0.0, min(1.0, float(frac)))
        if f > 0.0:
            dl.add_rect_filled(x, y, x + w * f, y + h, *fg)
    except Exception:  # noqa: BLE001
        pass


'''
sub("def _handle_input(window, io, state):", HELPERS.lstrip("\n") + "def _handle_input(window, io, state):",
    "helpers inserted")

# ------------------------------------------------------- 1. float the field -
sub(
    "                with _CTX:\n"
    "                    img = Image.open(io.BytesIO(raw)).convert(\"RGBA\")\n"
    "                    arr = np.array(img, dtype=np.uint8)",
    "                with _CTX:\n"
    "                    img = Image.open(io.BytesIO(raw)).convert(\"RGBA\")\n"
    "                    arr = np.array(img, dtype=np.uint8)\n"
    "                    # window is already alpha-capable; keying the dark\n"
    "                    # field makes only the neurons float on the desktop\n"
    "                    _float_alpha(arr)",
    "field alpha-keyed in FrameFeed")

# ------------------------------------------------- 2. fps history / uptime ---
sub(
    '        "fps": 0.0,',
    '        "fps": 0.0,\n        "fps_hist": [],\n        "t_start": time.time(),',
    "state gains fps_hist + t_start")

sub(
    "            state[\"fps\"] = fps_display\n",
    "            state[\"fps\"] = fps_display\n"
    "            _h = state.setdefault(\"fps_hist\", [])\n"
    "            _h.append(fps_display)\n"
    "            if len(_h) > 48:\n"
    "                del _h[:-48]\n",
    "fps history recorded")

# ------------------------------------------------------------- 3. new HUD ----
OLD_HUD = '''        if show_hud:
            imgui.set_cursor_position((18, 14))
            imgui.text_colored("ABRASAX", *GOLD)
            imgui.set_cursor_position((18, 32))
            imgui.text_colored("floating brain · chrono-lattice", *DIM)

            # right column
            rx = fbw - 210
            imgui.set_cursor_position((rx, 14))
            live_txt = "live :9700" if connected else "OFFLINE"
            imgui.text_colored(live_txt, *(CYAN if connected else HOT))
            imgui.set_cursor_position((rx, 72))
            brain_state = str(activity.get("state", "idle"))
            imgui.text_colored(f"state {brain_state}", *(GOLD if activity_live else DIM))
            tr = activity.get("transformer") or {}
            if tr:
                imgui.set_cursor_position((rx, 90))
                imgui.text_colored(
                    f"attn {float(tr.get('attention_entropy', 0.0)):.2f}", *CYAN)
                imgui.set_cursor_position((rx, 108))
                imgui.text_colored(
                    f"tok {tr.get('tokens', 0)}", *DIM)
            llm = activity.get("llm") or {}
            if llm:
                imgui.set_cursor_position((18, 68))
                imgui.text_colored(
                    f"{llm.get('route', '')} · {llm.get('model', '')}"[:38], *DIM)
            imgui.set_cursor_position((rx, 32))
            imgui.text_colored(f"steps {tel.get('steps', 0)}", *CYAN)
            imgui.set_cursor_position((rx, 50))
            imgui.text_colored(str(tel.get("gpu", "")).replace(
                "NVIDIA GeForce ", ""), *DIM)
'''

NEW_HUD = '''        if show_hud:
            dl = imgui.get_window_draw_list()
            now_h = time.time()
            up = max(0.0, now_h - float(state.get("t_start", now_h)))
            up_txt = (f"{int(up // 3600):02d}:{int(up % 3600 // 60):02d}:"
                      f"{int(up % 60):02d}")

            # title block, larger with a shadow so it reads over any desktop
            _txt((18, 12), "ABRASAX", GOLD, scale=1.45)
            _txt((19, 34), "floating brain · chrono-lattice", DIM, scale=1.05)

            # uptime / frames: the crash-free counter is the whole point of this
            # overlay after 10 unattributed deaths
            _txt((18, 56), f"uptime {up_txt}   frames {state.get('frame_count', 0)}",
                 CYAN, scale=1.0)

            # fps sparkline + meter
            _txt((18, 76), f"{float(state.get('fps', 0.0)):5.1f} fps", CYAN)
            _spark(dl, 96, 78, 150.0, 12.0, state.get("fps_hist") or [],
                   (0.42, 0.85, 1.0, 0.85))

            # right column
            rx = fbw - 214
            live_txt = "live :9700" if connected else "OFFLINE"
            _txt((rx, 12), live_txt, *(CYAN if connected else HOT), scale=1.05)
            _txt((rx, 32), f"steps {tel.get('steps', 0)}", CYAN)
            _txt((rx, 50), str(tel.get("gpu", "")).replace(
                "NVIDIA GeForce ", "")[:26], DIM)
            brain_state = str(activity.get("state", "idle"))
            _txt((rx, 72), f"state {brain_state}", *(GOLD if activity_live else DIM))

            # VRAM meter from the live feed (system section)
            sysd = activity.get("system") or {}
            vu = float(sysd.get("vram_used", 0.0))
            vt = float(sysd.get("vram_total", 0.0))
            if vt > 0.0:
                _txt((rx, 92), f"vram {vu:.0f}/{vt:.0f} MB", DIM)
                _bar(dl, rx, 108.0, 190.0, 6.0, vu / vt,
                     (0.95, 0.55, 0.20, 0.90), (0.25, 0.25, 0.25, 0.55))
                ram = float(sysd.get("ram", 0.0))
                if ram > 0.0:
                    _txt((rx, 118), f"ram {ram:.0f}%", DIM)
                    _bar(dl, rx, 134.0, 190.0, 6.0, ram / 100.0,
                         (0.35, 0.85, 0.55, 0.90), (0.25, 0.25, 0.25, 0.55))

            tr = activity.get("transformer") or {}
            if tr:
                _txt((rx, 146), f"attn {float(tr.get('attention_entropy', 0.0)):.2f}"
                     f"   tok {tr.get('tokens', 0)}", DIM)
            llm = activity.get("llm") or {}
            if llm:
                _txt((18, 96),
                     f"{llm.get('route', '')} · {llm.get('model', '')}"[:44], DIM)
                tps = float(llm.get("tokens_per_s", 0.0))
                if tps > 0.0:
                    _txt((18, 112), f"{tps:.1f} tok/s", GOLD)
'''

sub(OLD_HUD, NEW_HUD, "HUD rebuilt with shadow/scale/sparkline/VRAM")

# controls block: route through the shadowed helper too
sub(
    '            imgui.text_colored("CONTROLS", *DIM)',
    '            _txt((18, fbh - 150), "CONTROLS", GOLD, scale=1.05)',
    "controls header shadowed")

sub(
    '            imgui.text_colored("drag pilot · dbl-click reset · wheel exposure", *DIM)\n'
    '            imgui.text_colored("space orbit · R reset · H hud · P panels · B 3D · esc", *DIM)',
    '            _txt((18, fbh - 86), "drag pilot · dbl-click reset · wheel exposure", DIM)\n'
    '            _txt((18, fbh - 70), "space orbit · R reset · H hud · P panels · B 3D · esc", DIM)',
    "controls hints shadowed")

if len(src) - orig < 1500:
    sys.exit("ABORT: patch added suspiciously little text")

P.write_text(src, encoding="utf-8")
print(f"\nwrote {P.name}: {orig} -> {len(src)} bytes (+{len(src) - orig})")
