"""Enumerate the overlay's real top-level windows via Win32.

snap_desktop.py greps titles for "FLOATING BRAIN"; this asks the OS directly
for every visible top-level window owned by the overlay PID, which is the
only definition that can't be fooled by a title change.
"""
import ctypes
import ctypes.wintypes as wt
import subprocess
import sys

user32 = ctypes.windll.user32


def overlay_pids() -> list[int]:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | "
         "Where-Object { $_.CommandLine -match 'imgui_overlay' } | "
         "ForEach-Object { $_.ProcessId }"],
        capture_output=True, text=True, timeout=30,
    )
    return [int(x) for x in out.stdout.split() if x.strip().isdigit()]


def windows_of(pid: int) -> list[dict]:
    found: list[dict] = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        owner = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value != pid:
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        rect = wt.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        ex = user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
        found.append({
            "hwnd": hwnd,
            "title": buf.value,
            "visible": bool(user32.IsWindowVisible(hwnd)),
            "rect": (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top),
            "layered": bool(ex & 0x00080000),
            "topmost": bool(ex & 0x00000008),
        })
        return True

    user32.EnumWindows(cb, 0)
    return found


def main() -> int:
    pids = overlay_pids()
    if not pids:
        print("NO OVERLAY PROCESS (no python running imgui_overlay.py)")
        return 1
    for pid in pids:
        print(f"PID {pid}")
        wins = windows_of(pid)
        if not wins:
            print("  (no top-level windows -- window may be on another desktop/session)")
        for w in wins:
            flags = ",".join(k for k in ("visible", "layered", "topmost") if w[k]) or "-"
            print(f"  hwnd={w['hwnd']:#x} rect={w['rect']} [{flags}] title={w['title']!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
