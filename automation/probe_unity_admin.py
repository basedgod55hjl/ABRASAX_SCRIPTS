"""Find where Unity actually emits an Administrator requirement, and what
Unity.DataStore.exe does.

The directive asks to "bypass and suppress Unity Administrator privilege warnings"
and to stop Unity.DataStore.exe / upm.log / unity_status.py from hanging. Before
changing anything, establish:

  1. Does the editor actually demand elevation? Unity historically warns when run
     as Administrator, the OPPOSITE of requiring it, and the warning is a dialog
     that blocks batch mode.
  2. Where is that check in the editor? (grep the install for the message text)
  3. What does DataStore do, what memory does it request, and can it be disabled?
  4. Which Unity command-line flags suppress dialogs?

Reading, not modifying. Every answer below becomes evidence for the fix.
"""
import os
import re
import subprocess
import sys

EDITOR = r"J:\Unity\7000.0.0a10\Editor"

print("=== 1. editor binary presence ===")
exe = os.path.join(EDITOR, "Unity.exe")
print(f"  {exe}: {'exists' if os.path.exists(exe) else 'MISSING'}")

print("\n=== 2. strings in the editor that mention Administrator ===")
# search the EXE for the human-readable message; UTF-16LE is how .NET stores them
targets = [
    os.path.join(EDITOR, "Unity.exe"),
    os.path.join(EDITOR, "Data", "Managed", "UnityEditor.dll"),
    os.path.join(EDITOR, "Data", "Resources", "PackageManager", "Server", "UnityPackageManager.exe"),
]
needles = [
    "Administrator",
    "elevated",
    "Run as administrator",
    "administrative",
]
for t in targets:
    if not os.path.exists(t):
        print(f"  skip (missing): {t}")
        continue
    try:
        data = open(t, "rb").read()
    except OSError as e:
        print(f"  cannot read {t}: {e}")
        continue
    print(f"  {os.path.basename(t)} ({len(data):,} bytes)")
    for n in needles:
        a = n.encode("ascii") in data
        u = n.encode("utf-16-le") in data
        if a or u:
            print(f"      '{n}': ascii={a} utf16={u}")
    for m in re.finditer(rb"[ -~]{18,90}", data):
        s = m.group(0).decode("ascii", "ignore")
        if "dministrator" in s or "levated" in s:
            print(f"      string: {s[:88]}")
            break

print("\n=== 3. DataStore binary and its flags ===")
ds = os.path.join(EDITOR, "Data", "Tools", "Unity.DataStore.exe")
print(f"  {ds}: {'exists' if os.path.exists(ds) else 'MISSING'}")
if os.path.exists(ds):
    print(f"  size: {os.path.getsize(ds):,} bytes")
    r = subprocess.run(
        [ds, "--help"],
        capture_output=True, text=True, timeout=20,
        stdin=subprocess.DEVNULL,
        creationflags=0x08000000 if os.name == "nt" else 0,
    )
    out = (r.stdout or "") + (r.stderr or "")
    print(f"  --help rc={r.returncode}")
    for line in out.splitlines()[:30]:
        print("    " + line.strip()[:100])

print("\n=== 4. documented batch-mode flags in this editor ===")
# Unity documents these in the manual; list what we can prove exists by grep
flags = ["-batchmode", "-nographics", "-quit", "-ignoreCompilerErrors",
         "-logFile", "-projectPath", "-createProject", "-upmIpcPath",
         "-disableManagedDebugger", "-noUpm", "-accept-apiupdate"]
for f in flags:
    hit = False
    for t in targets:
        if not os.path.exists(t):
            continue
        try:
            data = open(t, "rb").read()
        except OSError:
            continue
        if f.encode("ascii") in data:
            hit = True
            break
    print(f"  {f:26s} {'present in editor binaries' if hit else '(not found)'}")

print("\n=== 5. batch-mode settings that control the dialog/DataStore ===")
settings = os.path.join(EDITOR, "Data", "Resources", "PackageManager", "Editor", "manifest.json")
if os.path.exists(settings):
    print(f"  {settings} exists ({os.path.getsize(settings):,} bytes)")
else:
    print("  no UPM editor manifest")

# is there a prefs/env that disables the data store?
for cand in ("Unity.DataStore", "UDS", "ABRASAX_UNITY"):
    v = os.environ.get(cand)
    print(f"  env {cand}: {v!r}")

sys.exit(0)
