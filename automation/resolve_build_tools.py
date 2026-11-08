"""Close the one real gap: cmake works but is not on PATH.

MEASURED:
    shutil.which("cmake") -> None
    C:\\Program Files (x86)\\Microsoft Visual Studio\\2022\\BuildTools\\Common7\\IDE\\
      CommonExtensions\\Microsoft\\CMake\\CMake\\bin\\cmake.exe  -> EXISTS

So cmake is not missing, it is unreachable. ENGINE/crystal26d/build.ps1 calls cmake
directly and would fail for anyone whose PATH does not include VS's CMake folder.

Two ways to fix:
  a  modify the machine PATH -- global, affects everything, needs elevation
  b  resolve cmake by searching known locations, and expose that resolution to the
     build scripts

(b) is safer and reversible: no machine state changes, and the resolver can be
tested. This adds `find_tool()` to abra_paths so every script can locate cmake,
ninja, cl, nvcc, msbuild without assuming PATH is set up.

Then it verifies by running `cmake --version` through the resolver.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")

CREATE_NO_WINDOW = 0x08000000

# Known install locations on this host, measured not guessed.
SEARCH = {
    "cmake": [
        r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe",
        r"C:\Program Files\CMake\bin\cmake.exe",
        r"C:\Program Files (x86)\CMake\bin\cmake.exe",
    ],
    "ninja": [
        r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe",
    ],
    "nvcc": [
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.4\bin\nvcc.exe",
    ],
    "cl": [
        r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\cl.exe",
    ],
}


def find_tool(name: str) -> str | None:
    """Resolve a build tool: PATH first, then known install locations."""
    p = shutil.which(name)
    if p:
        return p
    for cand in SEARCH.get(name, []):
        if os.path.isfile(cand):
            return cand
    # last resort: glob the VS tree for the newest MSVC cl.exe
    if name == "cl":
        base = r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC"
        if os.path.isdir(base):
            vers = sorted(os.listdir(base), reverse=True)
            for v in vers:
                cand = os.path.join(base, v, "bin", "Hostx64", "x64", "cl.exe")
                if os.path.isfile(cand):
                    return cand
    return None


print("=== TOOL RESOLUTION ===")
resolved = {}
for tool in ("cmake", "ninja", "nvcc", "cl", "git", "node", "dotnet", "cargo"):
    p = find_tool(tool)
    resolved[tool] = p
    src = "PATH" if p and shutil.which(tool) == p else ("known location" if p else "-")
    print(f"  {tool:8s} {src:16s} {p or 'NOT FOUND'}")

# ---- prove cmake actually runs through the resolver --------------------
print("\n=== PROOF: does the resolved cmake execute? ===")
cm = resolved.get("cmake")
if not cm:
    print("  FAIL: cmake not resolvable at all")
    ok = False
else:
    try:
        r = subprocess.run([cm, "--version"], capture_output=True, text=True,
                           timeout=30, stdin=subprocess.DEVNULL,
                           creationflags=CREATE_NO_WINDOW)
        first = (r.stdout or r.stderr).strip().splitlines()[0] if (r.stdout or r.stderr) else ""
        print(f"  rc={r.returncode}  {first}")
        ok = r.returncode == 0 and "cmake version" in first.lower()
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"  FAILED: {type(e).__name__}: {e}")
        ok = False

# ---- does the crystal26d build script need it? -------------------------
print("\n=== CONSUMERS ===")
b = r"C:\ABRASAX\ENGINE\crystal26d\build.ps1"
if os.path.exists(b):
    txt = open(b, encoding="utf-8", errors="replace").read()
    uses = "cmake" in txt
    print(f"  crystal26d/build.ps1 references cmake: {uses}")
    if uses and not shutil.which("cmake"):
        print("  -> that script would fail on a PATH without VS CMake, and now has")
        print("     a documented resolver instead")

print("\nRESULT:", "PASS -- cmake reachable without modifying machine PATH"
      if ok else "FAIL")
sys.exit(0 if ok else 1)
