"""Capture the overlay window by HWND, printing the window title it used.

snap_desktop.py filters titles with "FLOATING BRAIN" not in title after
requiring 'ABRASAX' in title -- the live title is 'ABRASAX \u00b7 FLOATING BRAIN',
which contains 'ABRASAX' but the filter is `"FLOATING BRAIN" in w[1]`... it
should pass. Prove it rather than argue: enumerate, print, then capture.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys

from PIL import ImageGrab

user32 = ctypes.windll.user32
OUT = r"C:\ABRASAX\LOGS\overlay_live.png"
TARGET = "FLOATING BRAIN"


def enumerate_windows() -> list[tuple[int, str, bool]]:
    out: list[tuple[int, str, bool]] = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            b = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, b, n + 1)
            out.append((hwnd, b.value, bool(user32.IsWindowVisible(hwnd))))
        return True

    user32.EnumWindows(cb, 0)
    return out


wins = enumerate_windows()
hits = [w for w in wins if TARGET in w[1]]
print(f"windows enumerated: {len(wins)}   title matches {TARGET!r}: {len(hits)}")
for hwnd, title, vis in hits:
    print(f"  hwnd={hwnd:#x} visible={vis} title={title!r}")

live = [w for w in hits if w[2] and not user32.IsIconic(w[0])]
if not live:
    print("NO VISIBLE MATCH -- nothing captured")
    sys.exit(1)

hwnd, title, _ = live[0]
user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
user32.SetForegroundWindow(hwnd)
import time
time.sleep(0.7)

rect = wt.RECT()
user32.GetWindowRect(hwnd, ctypes.byref(rect))
box = (rect.left, rect.top, rect.right, rect.bottom)
print(f"capturing title={title!r} box={box}")
img = ImageGrab.grab(bbox=box, all_screens=True)
img.save(OUT)
colors = img.convert("RGB").getcolors(maxcolors=1_000_000) or []
print(f"saved {OUT} size={img.size} distinct_colors={len(colors)}")
if len(colors) <= 2:
    print("WARNING: image looks blank (<=2 distinct colors)")
sys.exit(0)
