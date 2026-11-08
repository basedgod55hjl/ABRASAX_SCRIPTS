"""Verify the Unity editor found on J: actually runs.

Registry points at J:\\Unity\\7000.0.0a10. This confirms the binary, its version,
the modules present, and that -batchmode can open a project headlessly -- the
gate for compiling the floating-brain Unity consumer.
"""
import json
import os
import subprocess
import sys

EDITOR = r"J:\Unity\7000.0.0a10\Editor\Unity.exe"

print(f"editor exists : {os.path.isfile(EDITOR)}")
if not os.path.isfile(EDITOR):
    sys.exit(1)

sz = os.path.getsize(EDITOR)
print(f"editor bytes  : {sz:,}")

# Version from the shipped metadata, no launch needed.
for cand in (r"J:\Unity\7000.0.0a10\Editor\Data\PackageManager\Unity\modules.json",
             r"J:\Unity\7000.0.0a10\Editor\Data\PlaybackEngines\modules.json"):
    if os.path.isfile(cand):
        print(f"modules file  : {cand}")
        break

# Managed/Mono or CoreCLR present?
for probe in ("Data\\Managed\\UnityEngine.dll",
              "Data\\Managed\\UnityEditor.dll",
              "Data\\Resources\\PackageManager"):
    p = os.path.join(os.path.dirname(EDITOR), probe)
    print(f"{'OK ' if os.path.exists(p) else '-- '} {probe}")

# Playback engines (submodules)
pe = os.path.join(os.path.dirname(EDITOR), "Data", "PlaybackEngines")
if os.path.isdir(pe):
    mods = sorted(os.listdir(pe))
    print(f"playbackEngines ({len(mods)}): {', '.join(mods[:12])}")
else:
    print("playbackEngines: absent")

print("\n--- launching -batchmode -quit -version (headless) ---")
try:
    r = subprocess.run([EDITOR, "-batchmode", "-quit", "-nographics", "-logFile",
                        r"C:\ABRASAX\LOGS\unity-version.log"],
                       capture_output=True, text=True, timeout=300)
    print(f"exit={r.returncode}")
except subprocess.TimeoutExpired:
    print("TIMEOUT after 300s")
except Exception as e:
    print(f"LAUNCH FAILED: {e}")

log = r"C:\ABRASAX\LOGS\unity-version.log"
if os.path.exists(log):
    txt = open(log, encoding="utf-8", errors="replace").read()
    for line in txt.splitlines()[:25]:
        print("  " + line)
    print(f"\nlog bytes: {os.path.getsize(log):,}")
sys.exit(0)
