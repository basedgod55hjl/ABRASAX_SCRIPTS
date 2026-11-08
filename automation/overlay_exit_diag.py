"""Make the overlay explain why it exits.

The defect this addresses is not "the overlay dies". It is that the overlay
dies *silently and unattributably*: across 10 restarts in
LOGS/svc-floating-brain-overlay.log the runs end at arbitrary frame counts
(1140, 3210, 4770, 5970, 8310, 20190) with no traceback at all.

Two exit paths produce exactly that signature, and neither logs anything:

    if "ESC" in rising: return True                  -> break -> clean shutdown
    while not glfw.window_should_close(window):      -> WM_CLOSE -> clean shutdown

So a clean break is indistinguishable from a crash. This patch records the
cause to LOGS/overlay-exit.log for every exit path: ESC, WM_CLOSE, escaped
exception, and normal return. It changes NO behaviour -- same exits, same
timing, same rendering -- it only makes them legible.

Every anchor is asserted. A silent no-op replacement is how earlier attempts in
this file went wrong.
"""
from __future__ import annotations

import pathlib
import sys

P = pathlib.Path(r"C:\ABRASAX\ENGINE\floating_brain\imgui_overlay.py")
src = P.read_text(encoding="utf-8")
orig_len = len(src)


def sub(old: str, new: str, label: str) -> str:
    global src
    n = src.count(old)
    if n != 1:
        sys.exit(f"ABORT [{label}]: expected 1 occurrence, found {n}")
    src = src.replace(old, new, 1)
    print(f"  ok  {label}")
    return src


# --- 1. diagnostic helper + exit hooks, inserted before the health server -----
HELPER = '''
# --- exit diagnosis ---------------------------------------------------------
# Silently-exiting runs are unattributable. Every exit path below writes one
# line here so a restart always has a recorded cause.
_EXIT_LOG = Path(r"C:\\ABRASAX\\LOGS\\overlay-exit.log")


def _diag(msg: str) -> None:
    """Append one timestamped line to the exit log. Never raises."""
    try:
        _EXIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(_EXIT_LOG, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} pid={os.getpid()} {msg}\\n")
            fh.flush()
    except Exception:  # noqa: BLE001
        pass


def _install_exit_hooks() -> None:
    """Record uncaught exceptions even if stderr has been closed/redirected."""
    import threading as _th
    import traceback as _tb

    def _hook(exc_type, exc, tb):
        _diag("UNCAUGHT main-thread exception: " + "".join(
            _tb.format_exception(exc_type, exc, tb)).replace("\\n", " | "))
        sys.__excepthook__(exc_type, exc, tb)

    def _thook(a):
        _diag(f"UNCAUGHT thread {getattr(a.thread, 'name', '?')}: " + "".join(
            _tb.format_exception(a.exc_type, a.exc_value, a.exc_traceback)
        ).replace("\\n", " | "))

    sys.excepthook = _hook
    _th.excepthook = _thook

'''
src = sub("def _start_health_server(state_ref: dict, port: int = 9627):",
          HELPER.lstrip("\n") + "\ndef _start_health_server(state_ref: dict, port: int = 9627):",
          "helper inserted before health server")

# --- 2. install hooks at the top of main() -----------------------------------
src = sub(
    "    faulthandler.dump_traceback_later(10, repeat=True)",
    "    faulthandler.dump_traceback_later(10, repeat=True)\n"
    "    _install_exit_hooks()\n"
    "    _diag(f\"main() start argv={' '.join(sys.argv[1:])}\")",
    "hooks installed in main()")

# --- 3. log WM_CLOSE from the OS --------------------------------------------
src = sub(
    '    print("[overlay] window created", flush=True)\n'
    "    if not window:\n"
    "        glfw.terminate()\n"
    '        print("could not create GLFW window", file=sys.stderr)\n'
    "        return 2\n",
    '    print("[overlay] window created", flush=True)\n'
    "    if not window:\n"
    "        glfw.terminate()\n"
    '        print("could not create GLFW window", file=sys.stderr)\n'
    "        return 2\n"
    "\n"
    "    # WM_CLOSE makes window_should_close() true and the loop exits cleanly\n"
    "    # with no traceback -- historically indistinguishable from a crash.\n"
    "    def _on_window_close(_win):\n"
    '        _diag("WM_CLOSE received from the OS")\n'
    "\n"
    "    try:\n"
    "        glfw.set_window_close_callback(window, _on_window_close)\n"
    "    except Exception as _e:  # noqa: BLE001\n"
    '        _diag(f"could not install close callback: {_e!r}")\n',
    "close callback registered")

# --- 4. log ESC, which is the other clean-exit path --------------------------
src = sub(
    '    if "ESC" in rising:\n        return True',
    '    if "ESC" in rising:\n        _diag("ESC pressed -> requesting clean shutdown")\n        return True',
    "ESC logged")

# --- 5. log the exit reason after the loop ----------------------------------
src = sub(
    "    feed.stop()\n    activity_feed.stop()\n    field_feed.stop()",
    "    _diag(\n"
    '        f"loop exit: window_should_close={glfw.window_should_close(window)} "\n'
    "        f\"frames={state.get('frame_count')} fps={state.get('fps', 0.0):.2f} \"\n"
    "        f\"reason={'window_closed' if glfw.window_should_close(window) else 'esc_or_internal_break'}\")\n"
    "\n"
    "    feed.stop()\n    activity_feed.stop()\n    field_feed.stop()",
    "exit reason logged")

# --- 6. record the process exit code, including 0 ---------------------------
src = sub(
    'if __name__ == "__main__":\n    sys.exit(main())',
    'if __name__ == "__main__":\n'
    "    try:\n"
    "        _rc = main()\n"
    '        _diag(f"main() returned {_rc}")\n'
    "        sys.exit(_rc)\n"
    "    except SystemExit as _se:\n"
    '        _diag(f"SystemExit code={_se.code}")\n'
    "        raise\n"
    "    except BaseException:\n"
    "        import traceback as _tb2\n"
    '        _diag("FATAL escaped main(): " + _tb2.format_exc().replace("\\n", " | "))\n'
    "        raise",
    "process exit code recorded")

if len(src) - orig_len < 500:
    sys.exit("ABORT: patch added suspiciously little text")

P.write_text(src, encoding="utf-8")
print(f"\nwrote {P.name}: {orig_len} -> {len(src)} bytes (+{len(src) - orig_len})")
