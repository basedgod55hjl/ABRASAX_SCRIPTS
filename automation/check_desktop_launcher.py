"""Verify the desktop launcher does what it claims, including the refusals.

A .bat that starts a window proves nothing. What can break is:
  * CRLF lost by an editor or a git checkout (cmd.exe then mis-parses labels)
  * a path that no longer exists (every legacy launcher in this repo did this)
  * the forbidden sleeps creeping back in (`timeout /t`, `<nul`)
  * the single-instance guard silently letting a second window through
  * the log never being written

Each check states a claim; the exit code is only 0 if every claim holds.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import overlay_ctl  # noqa: E402
from abra_paths import paths  # noqa: E402

NAME = "ABRASAX-FloatingBrain.bat"
CANON = paths.scripts / "launchers" / NAME
DESKTOP = Path.home() / "Desktop" / NAME
CTL = paths.automation / "overlay_ctl.py"
PY = paths.root / "PYTHON" / ".venv_gui" / "Scripts" / "python.exe"
OVERLAY = paths.floating_brain / "imgui_overlay.py"

CREATE_NO_WINDOW = 0x08000000
failures: list[str] = []


def check(claim: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {claim}" + (f" -- {detail}" if detail else ""))
    if not ok:
        failures.append(claim)


def run(args: list[str], timeout: float = 120.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
    )


def bat(*args: str, timeout: float = 120.0) -> subprocess.CompletedProcess:
    return run(["cmd", "/c", str(DESKTOP), *args], timeout=timeout)


def main() -> int:
    print("=== 1. copies ===")
    for t in (CANON, DESKTOP):
        exists = t.exists()
        check(f"{t} exists", exists, f"{t.stat().st_size:,} B" if exists else "missing")
    if not (CANON.exists() and DESKTOP.exists()):
        return 1

    raw = DESKTOP.read_bytes()
    crlf = raw.count(b"\r\n")
    bare_lf = raw.count(b"\n") - crlf
    check("desktop copy uses CRLF only", bare_lf == 0, f"crlf={crlf} bare_lf={bare_lf}")
    check("desktop and repo copies are identical", raw == CANON.read_bytes())

    print("\n=== 2. forbidden constructs ===")
    raw_text = raw.decode("ascii", "replace")
    # Strip REM comments first. A scan that includes comments matches the notes
    # that explain WHY timeout is avoided, which is exactly what happened here
    # the last time this check was written.
    code_lines = [
        ln for ln in raw_text.splitlines()
        if not ln.strip().lower().startswith("rem")
    ]
    code = "\n".join(code_lines).lower()
    check("no `timeout /t` in executable lines", "timeout /t" not in code)
    check("no `<nul` redirection", "<nul" not in code)
    check("no `start /b` (leaves unowned children)", "start /b" not in code)
    check("sleep uses ping, not timeout", "ping -n" in code)
    check("stop marker is honoured", ".floating-brain.stop" in code)
    # Two writers on one file corrupted the exit-code line in the first version
    # of this launcher: python's buffered output landed on top of it. Keep the
    # child's stream in a separate file and assert that here.
    check("child output goes to its own file, not the control log",
          '"%stream%"' in code and '>>"%log%" 2>&1' not in code)

    print("\n=== 3. referenced paths exist ===")
    # The .bat builds paths from %ROOT%, so the literal absolute path is not in
    # the file. Match the part after %ROOT% instead of demanding the full path.
    for label, p in (("python", PY), ("overlay", OVERLAY), ("controller", CTL)):
        tail = str(p)[len(str(paths.root)):]
        check(f"{label} resolves", p.exists(), str(p))
        check(f"{label} is referenced as %ROOT%{tail}",
              f"%root%{tail}".lower() in raw_text.lower(), f"%ROOT%{tail}")

    print("\n=== 4. controller primitives ===")
    ok, msg = overlay_ctl.probe()
    check("renderer probe succeeds", ok, msg)

    print("\n=== 5. live instance + guard ===")
    before = overlay_ctl.roots(overlay_ctl.processes())
    running = len(before) >= 1
    check("an overlay is running (start the .bat first)", running, f"{len(before)} instance(s)")
    if not running:
        print("\nRESULT: FAIL (no running instance to test the guard against)")
        return 1

    r = bat("status")
    check("`status` exits 0", r.returncode == 0, f"rc={r.returncode}")
    check("`status` names the instance", "instance" in r.stdout.lower())

    # The guard is the important one: a second window must NOT appear.
    r = bat(timeout=90)
    after = overlay_ctl.roots(overlay_ctl.processes())
    check("plain start refuses while one is running",
          "already running" in r.stdout.lower(), f"rc={r.returncode}")
    check("refusal did not spawn a second instance", len(after) == len(before),
          f"before={len(before)} after={len(after)}")

    print("\n=== 6. log ===")
    logs = sorted(paths.logs.glob("floating-brain-*.log"))
    control = [p for p in logs if not p.name.endswith(".stream.log")]
    logs = control
    check("a timestamped control log exists", bool(logs), logs[-1].name if logs else "none")
    if logs:
        body = logs[-1].read_text(encoding="utf-8", errors="replace")
        check("log records the run header", "ABRASAX floating brain" in body)
        args_line = next((ln for ln in body.splitlines() if ln.lstrip().startswith("args")), "<none>")
        check("log records the arguments", "--width" in args_line, args_line.strip())
        check("log records the run start", "run 1 started" in body)

    print()
    if failures:
        print(f"RESULT: FAIL -- {len(failures)} problem(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: PASS -- launcher installs, guards, refuses and logs correctly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
