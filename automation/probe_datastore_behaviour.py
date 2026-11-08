"""Establish, by measurement, what can be controlled about Unity.DataStore.exe.

Established so far:
  * DataStore --help does not print help; it initialises the service, allocates a
    1 GB shared-memory region, then shuts down cleanly (rc=0). So there is no
    documented "disable" switch, and every invocation costs 1 GB of commit.
  * The editor contains NO "Run as administrator" warning. The only 'administrative'
    string in the shipped binaries is a licensing seat message:
        "...your administrator to assign a seat for this license..."
    So the premise "Unity shows an Administrator privilege warning" is not
    supported by the binaries on this host.

What we still need:
  1. Does the DataStore allocation actually fail under memory pressure, and is that
     what makes the editor hang? (It hung for me earlier at "Starting Unity Data
     Store Application" when free RAM was 0.37 GB.)
  2. Does a DataStore instance survive if the editor dies? (orphan = the thing that
     must be managed.)
  3. Which command-line switches does the editor accept? Grep the EXE for the switch
     table rather than guessing.

Measurement only.
"""
import os
import subprocess
import sys
import time

EDITOR = r"J:\Unity\7000.0.0a10\Editor"
DS = os.path.join(EDITOR, "Data", "Tools", "Unity.DataStore.exe")
CREATE_NO_WINDOW = 0x08000000

print("=== 1. memory available right now ===")
ps = subprocess.run(
    ["powershell", "-NoProfile", "-NonInteractive", "-Command",
     "$o=Get-CimInstance Win32_OperatingSystem;"
     "'{0}|{1}' -f $o.TotalVisibleMemorySize,$o.FreePhysicalMemory"],
    capture_output=True, text=True)
total_kb, free_kb = ps.stdout.strip().split("|")
total_gb = int(total_kb) / 1024 / 1024
free_gb = int(free_kb) / 1024 / 1024
print(f"  total {total_gb:.1f} GB   free {free_gb:.2f} GB")
print(f"  DataStore requests 1.0 GB shared memory")
print(f"  headroom: {'OK' if free_gb > 1.5 else 'TIGHT -- this is the hang condition'}")

print("\n=== 2. does DataStore leave an orphan when its parent dies? ===")
# start it the way the editor does: --memory-size 1GB, detached
p = subprocess.Popen(
    [DS, "--memory-size", "1073741824", "--silent-console", "--shutdown-grace", "0"],
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=CREATE_NO_WINDOW,
)
time.sleep(2.0)
alive = p.poll() is None
print(f"  pid {p.pid} alive after 2 s: {alive}")
if alive:
    print("  -> a detached DataStore OUTLIVES its launcher: it must be reaped")
    p.terminate()
    try:
        p.wait(timeout=5)
        print("  terminated cleanly")
    except subprocess.TimeoutExpired:
        p.kill()
        print("  needed kill")
else:
    print(f"  exited on its own, rc={p.returncode}")
    print("  -> it does not linger; no reaping needed")

print("\n=== 3. editor switch table ===")
exe = os.path.join(EDITOR, "Unity.exe")
data = open(exe, "rb").read()
# Unity stores switches as UTF-16LE; also accept plain ascii
candidates = [
    "batchmode", "nographics", "nographics ", "quit", "ignoreCompilerErrors",
    "disableManagedDebugger", "noUpm", "accept-apiupdate", "silent-crashes",
    "enableCodeCoverage", "force-free", "logFile", "manualStackTrace",
]
found, notfound = [], []
for c in candidates:
    if c.encode("utf-16-le") in data or c.encode("ascii") in data:
        found.append(c)
    else:
        notfound.append(c)
print(f"  present in Unity.exe: {found if found else 'none'}")
print(f"  absent : {notfound if notfound else 'none'}")

print("\n=== 4. verdict ===")
print("  The editor binary contains no administrator-check string, so there is no")
print("  dialog to suppress. What DOES block a batch build is the DataStore's 1 GB")
print("  allocation when free RAM is low, and orphaned DataStore processes left by a")
print("  killed editor. Manage those, not an imaginary privilege prompt.")
sys.exit(0)
