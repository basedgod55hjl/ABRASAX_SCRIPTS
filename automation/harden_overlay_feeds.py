"""Stop a slow local service from freezing the HUD.

Measured defect: the overlay died/stalled with the GL thread inside
urllib.request.urlopen (imgui_overlay.py:149, the frame feed, timeout=4). The
public feed cycles every ~7s while the model servers are saturating the GPU, so
a 4s blocking read plus lock contention starves the render loop and the window
stops answering /health.

Fix: shorten the blocking timeouts to something a 60fps UI can tolerate and
never let consecutive failures pile up. The feeds already run on their own
threads and publish under a lock, so a missed frame is harmless -- a blocked GL
thread is not.
"""
from __future__ import annotations

import sys
from pathlib import Path

P = Path(r"C:\ABRASAX\ENGINE\floating_brain\imgui_overlay.py")
src = P.read_text(encoding="utf-8")

if "SAFE_TIMEOUT" in src:
    sys.exit("already hardened")

# 1. tighten the frame feed timeout (line ~149)
old_frame = "with urllib.request.urlopen(url, timeout=4) as r:"
if old_frame not in src:
    sys.exit("frame feed timeout anchor not found")
new_frame = ("# SAFE_TIMEOUT: never block the GL thread longer than a few frames\n"
             "                with urllib.request.urlopen(url, timeout=SAFE_TIMEOUT) as r:")
src = src.replace(old_frame, new_frame, 1)

# 2. tighten the activity feed timeout
old_act = "with urllib.request.urlopen(url, timeout=1.0) as r:"
if old_act in src:
    src = src.replace(old_act,
                      "with urllib.request.urlopen(url, timeout=SAFE_TIMEOUT) as r:", 1)

# 3. define the constant near the top, after imports
anchor = "PHI ="
if anchor in src:
    src = src.replace(anchor, "SAFE_TIMEOUT = 1.5  # seconds; feeds are @property-guarded\nPHI =", 1)
else:
    # fall back: put it before the first class definition
    idx = src.find("\nclass ")
    if idx < 0:
        sys.exit("could not place SAFE_TIMEOUT")
    src = src[:idx] + "\nSAFE_TIMEOUT = 1.5  # seconds; a stalled service must not freeze the UI\n" + src[idx:]

# 4. a frame feed that fails repeatedly should back off instead of hammering
old_exc = """            except Exception as e:  # noqa: BLE001
                with self._lock:
                    self.connected = False
                    self.last_error = f"{type(e).__name__}: {e}\""""
if old_exc in src:
    new_exc = """            except Exception as e:  # noqa: BLE001
                with self._lock:
                    self.connected = False
                    self.last_error = f"{type(e).__name__}: {e}"
                    # back off so a dead renderer cannot spin the CPU at 60Hz
                    self._fail_streak = getattr(self, "_fail_streak", 0) + 1
                time.sleep(min(2.0, 0.05 * getattr(self, "_fail_streak", 1)))"""
    src = src.replace(old_exc, new_exc, 1)
    src = src.replace("""                    self.frames += 1
                    self.last_error = \"\"""",
                      """                    self.frames += 1
                    self.last_error = \"\"
                    self._fail_streak = 0""", 1)

P.write_text(src, encoding="utf-8")
print(f"hardened {P.name} ({len(src)} chars)")
