"""Make unity_status.py hang-proof and read the RIGHT upm.log.

Two real defects in the current version:

1. It reads the whole file with a single unbounded read():
       txt = open(UPM, encoding="utf-8", errors="replace").read()
   upm.log grows during a resolve and the file lives on J: (a USB HDD). A
   multi-MB read there blocks long enough to look like a hang.

2. UPM points at the SOURCE tree:
       PROJ = str(paths.unity_source)   ->   J:\\UnityProjects\\ABRASAX-Brain
       UPM  = PROJ + "\\Logs\\upm.log"
   But the editor runs against the BUILD tree on C:, and that is where upm.log is
   written. Measured: J: has no Logs/upm.log for the current runs -- the tool was
   reporting on a file nobody writes any more.

Fix: delegate to unity_proc.read_upm (bounded, timed, distinguishes
missing/empty/stale) and prefer the BUILD tree's log, falling back to source.
"""
import os
import re
import sys
import time

sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")

from abra_paths import paths          # noqa: E402
import unity_proc                     # noqa: E402

# The editor writes upm.log beside the project it opened. That is the BUILD tree
# when a compile is running; the SOURCE tree only during an authoring session.
CANDIDATES = [
    os.path.join(str(paths.unity_build), "Logs", "upm.log"),
    os.path.join(str(paths.unity_source), "Logs", "upm.log"),
]

print("=== upm.log candidates ===")
chosen = None
for c in CANDIDATES:
    info = unity_proc.read_upm(c)
    state = ("absent" if not info["exists"]
             else f"{info['bytes']:,} bytes, mtime {info['mtime']}")
    stale = unity_proc.stale_upm(c, max_age_s=300)
    print(f"  {c}")
    print(f"      {state}" + ("  [STALE >5min]" if stale else ""))
    if info["exists"] and info["bytes"] > 0 and chosen is None:
        chosen = (c, info)

print()
if chosen is None:
    print("  no upm.log with content found.")
    print("  This is NOT a hang -- the editor truncates upm.log on every launch, and")
    print("  a batch run that has not reached the package phase leaves it empty.")
else:
    path, info = chosen
    print(f"=== reporting on {path} ===")
    txt = "\n".join(info["lines"])

    malformed = txt.count("malformed Unity Editor installation")
    print(f"  bytes           : {info['bytes']:,}"
          + ("  (read truncated)" if info["truncated"] else ""))
    print(f"  malformed errors: {malformed}")

    lists = re.findall(r"project:list-packages --> (\d+)", txt)
    print(f"  list-packages   : {lists if lists else 'never returned in the tail'}")

    for pat in ("config:project:get-registries", "project:resolve", "packages:add"):
        hits = re.findall(re.escape(pat) + r" --> (\d+)", txt)
        if hits:
            print(f"  {pat:32s}: {hits}")

    if unity_proc.stale_upm(path, max_age_s=300):
        print("  WARNING: not modified in over 5 minutes -- the resolver may be stuck")
        print("           (measured cause: Unity.DataStore needs 1 GB; check free RAM)")

print("\n=== library ===")
lib = os.path.join(str(paths.unity_build), "Library")
for sub in ("PackageCache", "ScriptAssemblies"):
    d = os.path.join(lib, sub)
    n = 0
    if os.path.isdir(d):
        for _dp, _dn, fns in os.walk(d):
            n += len(fns)
    print(f"  {sub:18s}: {n:,} file(s)")

dll = paths.unity_dll
if dll.exists():
    print(f"  Assembly-CSharp.dll: {dll.stat().st_size:,} bytes")

print("\n=== memory guard ===")
ok, msg = unity_proc.guard()
print(f"  {'ALLOWED' if ok else 'REFUSED'}: {msg}")

print("\n=== orphaned Unity helpers ===")
orphans = unity_proc.reap(dry_run=True)
if orphans:
    for o in orphans:
        print(f"  pid {o['pid']:7d} {o['name']:28s} (dead parent {o['ppid']})")
    print("  run `python -c \"import unity_proc; unity_proc.reap()\"` to clear them")
else:
    print("  none")

sys.exit(0)
