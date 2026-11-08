#!/usr/bin/env python3
"""fix_unity_compute.py -- make the Unity 7D compute stage actually run.

Measured 2026-11-01 on C:\\UnityProjects\\ABRASAX-Brain:
  * Spine7DCompute.EnsureResources() looked the kernel up with
        Resources.Load<ComputeShader>("Spine7D")
    but the asset lived in Assets/BrainUI/Shaders/, which is not a Resources folder.
    Resources.Load returned null, so `compute` stayed null and LateUpdate() returned at
    its first line -- the "REAL UNITY COMPUTE stage" dispatched zero kernels, forever,
    without a single warning.
  * _Phase (the 7.83 Hz Schumann breath) was only refreshed on the 2 s state poll, so the
    pulse advanced in 2-second steps.
  * Nothing anywhere proved a kernel ran.

This patch:
  1. moves the compute asset into Assets/BrainUI/Resources/ (done by the caller / re-done
     here if it is still in Shaders/), keeping its .meta so the GUID survives;
  2. logs loudly and names the paths when the shader cannot be loaded;
  3. refreshes _Phase every frame from Time.realtimeSinceStartup;
  4. exposes LoadCompute() so an editor test can prove the same path resolves.

Run: python SCRIPTS/fix_unity_compute.py [--check]
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT = Path(r"C:\UnityProjects\ABRASAX-Brain")
CS = PROJECT / "Assets" / "BrainUI" / "Scripts" / "Spine7DCompute.cs"
SHADERS = PROJECT / "Assets" / "BrainUI" / "Shaders"
RESOURCES = PROJECT / "Assets" / "BrainUI" / "Resources"

LOAD_OLD = """            if (compute == null) compute = Resources.Load<ComputeShader>("Spine7D") ??
                Resources.Load<ComputeShader>("BrainUI/Spine7D");"""

LOAD_NEW = """            if (compute == null) compute = LoadCompute();
            if (compute == null)
            {
                // Loud, because silence here cost a whole feature: a Resources.Load miss
                // leaves compute == null and LateUpdate() returns before dispatching, so
                // the scene renders nothing and no error is ever printed.
                Debug.LogError(
                    $"[{CORE_NAME}] ComputeShader not found. Resources.Load tried " +
                    "'Spine7D' and 'BrainUI/Spine7D'. The asset must live under " +
                    "Assets/BrainUI/Resources/Spine7D.compute (same name as the file).");
            }"""

PHASE_OLD = """            compute.SetFloat("_CurvatureScale", _state.Curvature);
            compute.SetFloat("_Phase", _phase);"""

PHASE_NEW = """            compute.SetFloat("_CurvatureScale", _state.Curvature);
            // Breath phase tracks the frame clock, not the 2 s state poll.
            _phase = Time.realtimeSinceStartup;
            compute.SetFloat("_Phase", _phase);"""

HELPER_ANCHOR = """        static Material FindMaterial(string shaderName)"""

HELPER = """        /// <summary>
        /// The one place the compute asset is resolved. Public so the editor self-test
        /// proves the same lookup the runtime uses (and fails the same way if it breaks).
        /// </summary>
        public static ComputeShader LoadCompute()
        {
            return Resources.Load<ComputeShader>("Spine7D")
                ?? Resources.Load<ComputeShader>("BrainUI/Spine7D");
        }

"""


def move_asset() -> list[str]:
    notes = []
    src = SHADERS / "Spine7D.compute"
    if src.exists():
        RESOURCES.mkdir(parents=True, exist_ok=True)
        for suffix in ("", ".meta"):
            s = SHADERS / f"Spine7D.compute{suffix}"
            d = RESOURCES / f"Spine7D.compute{suffix}"
            if s.exists():
                shutil.move(str(s), str(d))
                notes.append(f"moved {s.name} -> Resources/")
    return notes


def main() -> int:
    if not CS.exists():
        print(f"FAIL  missing {CS}")
        return 1
    text = CS.read_text(encoding="utf-8-sig")

    applied = (
        "LoadCompute()" in text
        and "ComputeShader not found" in text
        and "Breath phase tracks the frame clock" in text
        and (RESOURCES / "Spine7D.compute").exists()
    )

    if "--check" in sys.argv:
        print(("PASS " if applied else "FAIL ") + f"unity compute wired={applied}")
        return 0 if applied else 1

    if applied:
        print("already wired: Spine7DCompute.cs + Resources/Spine7D.compute")
        return 0

    notes = move_asset()

    if LOAD_NEW not in text:
        if LOAD_OLD not in text:
            print("FAIL  load anchor missing in Spine7DCompute.cs")
            return 1
        text = text.replace(LOAD_OLD, LOAD_NEW, 1)
        notes.append("loud failure on a missing ComputeShader")

    if "public static ComputeShader LoadCompute()" not in text:
        if HELPER_ANCHOR not in text:
            print("FAIL  FindMaterial anchor missing")
            return 1
        text = text.replace(HELPER_ANCHOR, HELPER + HELPER_ANCHOR, 1)
        notes.append("LoadCompute() helper")

    if PHASE_NEW not in text:
        if PHASE_OLD not in text:
            print("FAIL  phase anchor missing")
            return 1
        text = text.replace(PHASE_OLD, PHASE_NEW, 1)
        notes.append("_Phase per frame")

    bak = CS.with_suffix(".cs.bak-unitycompute")
    if not bak.exists():
        bak.write_text(CS.read_text(encoding="utf-8-sig"), encoding="utf-8")
    CS.write_text(text, encoding="utf-8")
    for n in notes:
        print("  + " + n)
    print("patched Spine7DCompute.cs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
