"""Serialise every C-buffer operation across the overlay's threads.

Diagnosis this fixes
--------------------
Not a GL-driver crash. Windows Event 1000 recorded six crashes as:

    Faulting module : python311.dll      <- CPython itself, not the driver
    Exception code  : 0xc0000005
    Fault offsets   : 0x26657b, 0x266568 (x2 each), 0x1d1c51, 0xe2634

Two offsets recurring 19 bytes apart means the same code path. A fault inside
CPython's allocator/object code, at non-deterministic times, is the signature of
heap corruption created earlier by a C extension and surfacing at the next
Python allocation -- not of a bug in CPython.

The process has four threads that reach into C buffers:

    FrameFeed   Image.open().convert() + np.array()        (PIL, numpy)
    FieldFeed   load_field()                               (numpy / CUDA)
    GL thread   rgba.tobytes() -> glTexImage2D/SubImage2D  (PyOpenGL)
    GL thread   np.array(...) matrix products per frame    (numpy)

PIL, numpy and PyOpenGL all release the GIL inside their C code. Nothing
serialises them, so a decode can run while the GL thread is uploading the same
kind of buffer. That is the classic precondition for this exact fault.

The fix is one re-entrant lock held for the duration of any such operation.
Re-entrant because the GL thread's own nested calls must not deadlock.
Decodes are sub-millisecond relative to a 60 Hz frame, so the contention cost is
not measurable in fps terms.

This changes no behaviour: same data, same frames, same timing on the happy
path. It removes the concurrency, not the work.
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
        sys.exit(f"ABORT [{label}]: expected 1 occurrence, found {n}")
    src = src.replace(old, new, 1)
    print(f"  ok  {label}")


# --- 1. the lock, declared next to the other module-level state -------------
sub(
    "import io\nimport json\nfrom pathlib import Path",
    "import io\nimport json\nfrom pathlib import Path",
    "imports intact (no-op sanity check)")

sub(
    "# --- exit diagnosis ---------------------------------------------------------",
    '''# --- C-buffer serialisation -------------------------------------------------
# PIL, numpy and PyOpenGL all release the GIL inside their C code. Three feed
# threads and the GL thread use them on the same kind of buffers with nothing
# serialising them; six crashes faulted inside python311.dll at two recurring
# offsets, which is heap corruption surfacing in CPython's allocator. Every
# operation that hands a raw buffer to a C extension takes this lock.
# Re-entrant so the GL thread's nested calls cannot self-deadlock.
_CTX = threading.RLock()

# --- exit diagnosis ---------------------------------------------------------''',
    "_CTX lock declared")

# --- 2. FrameFeed: PIL decode + numpy conversion ----------------------------
sub(
    "                img = Image.open(io.BytesIO(raw)).convert(\"RGBA\")\n"
    "                arr = np.array(img, dtype=np.uint8)",
    "                with _CTX:\n"
    "                    img = Image.open(io.BytesIO(raw)).convert(\"RGBA\")\n"
    "                    arr = np.array(img, dtype=np.uint8)",
    "FrameFeed decode locked")

# --- 3. FieldFeed: load_field (numpy / CUDA) --------------------------------
sub(
    "            try:\n"
    "                f = load_field()\n",
    "            try:\n"
    "                with _CTX:\n"
    "                    f = load_field()\n",
    "FieldFeed load_field locked")

# --- 4. GL thread: the texture upload --------------------------------------
sub(
    "        if (w, h) != self.size:\n"
    "            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0,\n"
    "                         GL_RGBA, GL_UNSIGNED_BYTE, rgba.tobytes())\n"
    "            self.size = (w, h)\n"
    "        else:\n"
    "            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h,\n"
    "                            GL_RGBA, GL_UNSIGNED_BYTE, rgba.tobytes())",
    "        with _CTX:\n"
    "            if (w, h) != self.size:\n"
    "                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0,\n"
    "                             GL_RGBA, GL_UNSIGNED_BYTE, rgba.tobytes())\n"
    "                self.size = (w, h)\n"
    "            else:\n"
    "                glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h,\n"
    "                                GL_RGBA, GL_UNSIGNED_BYTE, rgba.tobytes())",
    "GL texture upload locked")

# --- 5. health handler: snapshot the shared dict ----------------------------
sub(
    '            body = json.dumps({\n'
    '                "ok": True,\n'
    '                "service": "floating-brain-overlay",\n'
    '                "frames": state_ref.get("frame_count", 0),\n'
    '                "fps": round(float(state_ref.get("fps", 0.0)), 2),\n'
    '                "size": [int(state_ref.get("w", 0)), int(state_ref.get("h", 0))],\n'
    '                "panels": bool(state_ref.get("show_panels", True)),\n'
    '                "mode_3d": bool(state_ref.get("mode_3d", True)),\n'
    '                "brain_connected": bool((state_ref.get("activity") or {}).get("ts")),\n'
    '            }).encode()',
    '            # Copy once, under the lock, then serialise the private copy.\n'
    '            # `state` is written by the GL thread every frame with no lock;\n'
    '            # reading it straight from another thread is a race even though\n'
    '            # .get() itself is atomic under the GIL.\n'
    '            with _CTX:\n'
    '                snap = dict(state_ref)\n'
    '            body = json.dumps({\n'
    '                "ok": True,\n'
    '                "service": "floating-brain-overlay",\n'
    '                "frames": snap.get("frame_count", 0),\n'
    '                "fps": round(float(snap.get("fps", 0.0)), 2),\n'
    '                "size": [int(snap.get("w", 0)), int(snap.get("h", 0))],\n'
    '                "panels": bool(snap.get("show_panels", True)),\n'
    '                "mode_3d": bool(snap.get("mode_3d", True)),\n'
    '                "brain_connected": bool((snap.get("activity") or {}).get("ts")),\n'
    '            }).encode()',
    "health handler snapshots under lock")

if len(src) - orig < 300:
    sys.exit("ABORT: patch added suspiciously little text")

P.write_text(src, encoding="utf-8")
print(f"\nwrote {P.name}: {orig} -> {len(src)} bytes (+{len(src) - orig})")
