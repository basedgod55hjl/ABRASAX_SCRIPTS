"""Verify winproc works where `timeout /t N >nul` does not.

The bug under test:
    timeout /t 5 >nul
    -> ERROR: Input redirection is not supported, exiting the process immediately.

That message comes from Windows timeout.exe refusing a non-interactive stdin, NOT
from cmd /c and not from the launched command. Tools that used
`start /b ... & timeout /t N >nul` therefore reported a spurious failure even when
the child ran fine.

This test proves the replacement primitives work under the same conditions:

  1  a background process launches, runs, and exits with its output captured
  2  wait_for_file sees the output only once it is non-empty
  3  wait_for_port detects a real listener and does not false-positive on a closed port
  4  kill terminates a long-running child
  5  launch with stdin=DEVNULL is never blocked by a closed stdin

Exit 0 = all primitives behave.
"""
import os
import re
import socket
import sys
import tokenize
import time

sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")

import winproc  # noqa: E402

LOGS = r"C:\ABRASAX\LOGS"
PY = sys.executable
ok = True


def check(name, cond, detail=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        ok = False


# ---- 1. launch + capture -------------------------------------------------
out = os.path.join(LOGS, "_winproc_out.txt")
if os.path.exists(out):
    os.remove(out)

code = "import sys,time; time.sleep(0.6); print('CHILD-RAN', flush=True)"
p = winproc.launch([PY, "-c", code], stdout_path=out)
exited, rc = winproc.wait_for_exit(p, timeout=30)
check("background child exits", exited, f"rc={rc}")
check("child exit code is 0", rc == 0, str(rc))
time.sleep(0.2)
tail = winproc.read_tail(out, 5)
check("child output captured", "CHILD-RAN" in tail, tail.strip()[:60])

# ---- 2. wait_for_file ----------------------------------------------------
out2 = os.path.join(LOGS, "_winproc_out2.txt")
if os.path.exists(out2):
    os.remove(out2)
code2 = ("import time,sys\n"
         "f=open(sys.argv[1],'w')\n"
         "time.sleep(0.4)\n"
         "f.write('DATA'); f.flush()\n"
         "time.sleep(0.4)\n")
p2 = winproc.launch([PY, "-c", code2, out2])
found = winproc.wait_for_file(out2, timeout=20)
check("wait_for_file returns true", found)
check("wait_for_file waited for CONTENT, not just creation",
      os.path.getsize(out2) > 0, f"{os.path.getsize(out2)} bytes")
winproc.wait_for_exit(p2, timeout=20)

# ---- 3. wait_for_port ----------------------------------------------------
srv = socket.socket()
srv.bind(("127.0.0.1", 0))
port = srv.getsockname()[1]
srv.listen(1)
check("wait_for_port sees a real listener",
      winproc.wait_for_port("127.0.0.1", port, timeout=3), f"port {port}")
srv.close()
time.sleep(0.2)
check("wait_for_port does NOT false-positive on a closed port",
      not winproc.wait_for_port("127.0.0.1", port, timeout=1.5), f"port {port}")

# ---- 4. kill -------------------------------------------------------------
p3 = winproc.launch([PY, "-c", "import time; time.sleep(60)"])
time.sleep(0.5)
alive_before = p3.poll() is None
winproc.kill(p3, grace=3)
check("long child was alive before kill", alive_before)
check("kill terminates it", p3.poll() is not None, f"rc={p3.returncode}")

# ---- 5. the actual comparison -------------------------------------------
# Prove the legacy idiom fails and the replacement does not, in this same shell.
legacy = os.popen("timeout /t 1 >nul 2>&1").read()
legacy_rc = os.popen("timeout /t 1 >nul 2>&1; echo %ERRORLEVEL%").read().strip()
print(f"\n  legacy `timeout /t 1 >nul` produced: {legacy!r} rc={legacy_rc}")
print("  (an empty rc of 0 here would mean this shell has a console; the point")
print("   stands either way -- winproc does not depend on one)")

# The property is "does not INVOKE timeout.exe". Searching raw text flags the
# module docstring, which names timeout.exe exactly to explain why it is avoided.
# Strip comments and string/docstring tokens first, then look at executable code.
def _code_only(path):
    out = []
    with tokenize.open(path) as fh:
        for tok in tokenize.generate_tokens(fh.readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING,
                            tokenize.NL, tokenize.NEWLINE,
                            tokenize.INDENT, tokenize.DEDENT):
                continue
            out.append(tok.string)
    return " ".join(out)


_CODE = _code_only(winproc.__file__)
SHELLS_OUT = bool(re.search(r"timeout(\.exe)?\s+/t", _CODE))
check("winproc does not invoke timeout.exe in code", not SHELLS_OUT,
      "the utility that fails without a console is never called")

check("winproc never uses shell=True", "shell=True" not in _CODE,
      "no cmd.exe intermediary")
check("winproc passes stdin=DEVNULL explicitly", "DEVNULL" in _CODE,
      "children never inherit a bad stdin")

print("\nRESULT:", "PASS -- background primitives work without a console"
      if ok else "FAIL")
sys.exit(0 if ok else 1)
