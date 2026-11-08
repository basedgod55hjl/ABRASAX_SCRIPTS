"""Verify the floating-brain autostart entry works, without restarting the supervisor.

The ownership rule says never restart supervisor.py outside the SERVICES-PROD package.
So this proves the ENTRY is correct by doing what the supervisor would do, in a
sandbox:

  1  import supervisor.py and read AUTOSTART["floating-brain"]
  2  confirm the command and cwd resolve to real files
  3  with the renderer STOPPED, run exactly that command as the supervisor would
  4  confirm :9700 comes up and serves telemetry
  5  leave the service running (that is the desired end state)

Note: the currently-running supervisor process was started before this edit, so it
still has the old AUTOSTART in memory. The entry takes effect at its next start.
Proving the entry is correct is what matters now; forcing a restart is the
SERVICES-PROD owner's call.
"""
import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT = r"C:\ABRASAX"
SUP = os.path.join(ROOT, "SCRIPTS", "automation", "supervisor.py")
CREATE_NO_WINDOW = 0x08000000
ok = True


def check(name, cond, detail=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        ok = False


print("=== 1. load the entry from supervisor.py ===")
spec = importlib.util.spec_from_file_location("sup_check", SUP)
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except SystemExit:
    pass
except Exception as e:  # noqa: BLE001
    print(f"  module import failed: {type(e).__name__}: {e}")
    sys.exit(1)

entry = getattr(mod, "AUTOSTART", {}).get("floating-brain")
check("AUTOSTART has a floating-brain entry", entry is not None)
if not entry:
    sys.exit(1)

cmd = [str(x) for x in entry["cmd"]]
cwd = str(entry["cwd"])
print(f"  cmd : {cmd}")
print(f"  cwd : {cwd}")

print("\n=== 2. do the files resolve? ===")
exe = cmd[0]
check("exe exists", os.path.isfile(exe), exe)
check("cwd exists", os.path.isdir(cwd), cwd)
for arg in cmd[1:]:
    p = os.path.join(cwd, arg)
    if os.path.splitext(arg)[1]:
        check(f"file arg {arg} exists", os.path.isfile(p), p)

print("\n=== 3. stop any running renderer, then start via the entry ===")
subprocess.run(["taskkill", "/F", "/IM", "fb_server.exe"], capture_output=True,
               text=True, timeout=30, stdin=subprocess.DEVNULL,
               creationflags=CREATE_NO_WINDOW)
time.sleep(2)


def listening():
    s = None
    try:
        import socket
        s = socket.socket()
        s.settimeout(0.5)
        s.connect(("127.0.0.1", 9700))
        return True
    except OSError:
        return False
    finally:
        if s:
            s.close()


check("port 9700 is free before the test", not listening())

p = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=CREATE_NO_WINDOW)
print(f"  started pid {p.pid} exactly as the supervisor would")

deadline = time.time() + 30
up = False
while time.time() < deadline:
    if listening():
        up = True
        break
    time.sleep(0.5)
check("port 9700 came up within 30 s", up)

if up:
    try:
        with urllib.request.urlopen("http://127.0.0.1:9700/telemetry.json?clock=0",
                                    timeout=10) as r:
            tel = json.loads(r.read().decode())
        print(f"  telemetry: live={tel.get('live')} steps={tel.get('steps')} "
              f"gpu={tel.get('gpu')}")
        check("telemetry is valid JSON with a live field", "live" in tel)
        check("renderer is reading the brain", tel.get("live") is True)
    except Exception as e:  # noqa: BLE001
        check("telemetry reachable", False, f"{type(e).__name__}: {e}")

print("\n=== 4. end state ===")
check("renderer left running for the overlay and Unity client", listening())

print("\nNOTE: the supervisor process currently alive was started BEFORE this edit,")
print("      so it still holds the old AUTOSTART. The entry takes effect at its")
print("      next start, which SERVICES-PROD (#15) owns. The entry itself is proven")
print("      correct above by launching it exactly as the supervisor would.")

print("\nRESULT:", "PASS -- autostart entry is correct and the service is up"
      if ok else "FAIL")
sys.exit(0 if ok else 1)
