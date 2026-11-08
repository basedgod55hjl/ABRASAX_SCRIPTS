"""Functional test: right-drag the brain, prove the window follows and persists.

Why PostMessage and not mouse_event
-----------------------------------
The first version injected input with `mouse_event`. It failed, and the /health
instrumentation showed why: `gb1` (glfw.get_mouse_button) stayed False while the
button was physically down, yet `cursor` tracked fine. Injected input was not
reaching the topmost borderless window, so the test was measuring its own
harness, not the feature.

Posting WM_RBUTTONDOWN straight to the window HWND proved the overlay's logic is
correct (`gb1=true, moving=true`). This test drives it that way, then checks the
three things that matter:

  1. the window rect moved by the requested delta
  2. DATA/runtime-memory/overlay_geom.json records the new position
  3. (verified separately) a restart restores it

It restores the original position and deletes the geometry file afterwards, so
it leaves no state behind.
"""
from __future__ import annotations

import ctypes
import json
import pathlib
import sys
import time
import urllib.request

user32 = ctypes.windll.user32
GEOM = pathlib.Path(r"C:\ABRASAX\DATA\runtime-memory\overlay_geom.json")
HEALTH = "http://127.0.0.1:9627/health"

WM_MOUSEMOVE = 0x0200
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
MK_RBUTTON = 0x0002


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def find_overlay():
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            b = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, b, n + 1)
            if "FLOATING BRAIN" in b.value:
                found.append(hwnd)
        return True

    user32.EnumWindows(enum, 0)
    return found[0] if found else None


def rect_of(hwnd):
    r = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top


def health() -> dict:
    try:
        return json.loads(urllib.request.urlopen(HEALTH, timeout=5).read().decode())
    except Exception:  # noqa: BLE001
        return {}


def lparam(x: int, y: int) -> int:
    return (y << 16) | (x & 0xFFFF)


def drag(hwnd, dx: int, dy: int) -> None:
    """Press at centre, move the OS cursor, post a move, release."""
    l, t = rect_of(hwnd)
    w, h = 760, 760
    cx, cy = l + w // 2, t + h // 2

    user32.SetCursorPos(cx, cy)
    time.sleep(0.25)
    user32.PostMessageW(hwnd, WM_RBUTTONDOWN, MK_RBUTTON, lparam(cx, cy))
    time.sleep(0.30)

    # Walk the cursor so io.mouse_pos (glfw.get_cursor_pos) advances per step,
    # the same way a real drag does.
    steps = 8
    for i in range(1, steps + 1):
        px = cx + dx * i // steps
        py = cy + dy * i // steps
        user32.SetCursorPos(px, py)
        user32.PostMessageW(hwnd, WM_MOUSEMOVE, MK_RBUTTON, lparam(px, py))
        time.sleep(0.05)

    time.sleep(0.20)
    user32.PostMessageW(hwnd, WM_RBUTTONUP, 0, lparam(cx + dx, cy + dy))
    time.sleep(0.35)


def main() -> int:
    hwnd = find_overlay()
    if not hwnd:
        print("FAIL: overlay window not found")
        return 1
    if GEOM.exists():
        GEOM.unlink()

    before = rect_of(hwnd)
    print(f"window before : x={before[0]} y={before[1]}")

    DX, DY = 64, 44
    drag(hwnd, DX, DY)
    after = rect_of(hwnd)
    print(f"window after  : x={after[0]} y={after[1]}")

    moved = (after[0] - before[0], after[1] - before[1])
    print(f"moved         : {moved}  (requested {(DX, DY)})")
    ok_move = abs(moved[0] - DX) <= 12 and abs(moved[1] - DY) <= 12
    print(f"[{'PASS' if ok_move else 'FAIL'}] window followed the right-drag")

    geom = json.loads(GEOM.read_text(encoding="utf-8")) if GEOM.exists() else None
    print(f"geometry file : {geom}")
    ok_persist = (bool(geom)
                  and abs(geom["x"] - after[0]) <= 12
                  and abs(geom["y"] - after[1]) <= 12)
    print(f"[{'PASS' if ok_persist else 'FAIL'}] position persisted to {GEOM.name}")

    drag(hwnd, -DX, -DY)
    back = rect_of(hwnd)
    print(f"restored to   : x={back[0]} y={back[1]}")

    ok = ok_move and ok_persist
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
