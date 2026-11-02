#!/usr/bin/env python3
"""
rife_vulkan_pipeline.py
ABRASAX media stack — RIFE frame interpolation via rife-ncnn-vulkan.
Source: NotebookLM "vlc-7d-cuda-kernels" script + research corrections (2026-10-03).

CORRECTED per upstream source check: rife-ncnn-vulkan has NO --scale flag
(-s is TIMESTEP, -n is target frame count). The real 4K OOM mitigations are:
  -j 2:2:2 thread caps and the "lite" models (TNTwise fork: rife-v4.26-lite).
Portable binary (no CUDA/PyTorch needed — ncnn/Vulkan):
  nihui:   https://github.com/nihui/rife-ncnn-vulkan/releases   (20221029, 411 MB)
  TNTwise: https://github.com/TNTwise/rife-ncnn-vulkan/releases (20250112, 788 MB, newer models)

VRAM budgeting (grounded):
  - Vulkan path can target CPU or the AMD Vega iGPU  -> ~0 MB of dGPU VRAM.
  - On the GTX 1660 Ti: ~1.2 GB VRAM for 1080p; use -j 2:2:2 + lite models for 4K.
"""
import subprocess
import sys
import os
try:  # ABRASAX_JEV
    from abrasax_jev import decide as jev_decide, yesno as jev_yesno  # noqa: F401
except Exception:
    jev_decide = jev_yesno = None


def run_rife_interpolation(
    input_path: str,
    output_path: str,
    model_dir: str = "rife-v4.6",
    num_frames: int = 0,          # 0 = auto (2x target); else target total frames
    timestep: float = 0.5,        # -s: interpolation time-step (NOT scale)
    threads_spec: str = "2:2:2",  # load:proc:save — caps GPU memory on large frames
    gpu_id: int = -1,             # -1 auto, or comma list e.g. "0,-1,1" (multi-GPU+CPU)
):
    binary = "rife-ncnn-vulkan.exe" if sys.platform == "win32" else "rife-ncnn-vulkan"

    if not os.path.exists(input_path):
        print(f"[Error] Input path '{input_path}' not found.", file=sys.stderr)
        return False

    cmd = [binary, "-i", input_path, "-o", output_path, "-m", model_dir,
           "-s", str(timestep), "-j", threads_spec]
    if num_frames > 0:
        cmd.extend(["-n", str(num_frames)])
    if gpu_id >= 0:
        cmd.extend(["-g", str(gpu_id)])

    print(f"[Exec] {' '.join(cmd)}")
    print(f"[VRAM Budget] threads={threads_spec} (4K OOM mitigation), timestep={timestep}")

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   universal_newlines=True)
        for line in process.stdout:
            print(line, end="")
        process.wait()
        if process.returncode == 0:
            print("[Success] RIFE frame interpolation complete.")
            return True
        print(f"[Error] exit code {process.returncode}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print(f"[Error] '{binary}' not found. Download from the releases link above.", file=sys.stderr)
        return False


def video_2x(input_dir: str, output_dir: str, gpu_id: int = -1):
    """Interpolate an image sequence 2x (extract frames first, re-mux with ffmpeg after)."""
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    return run_rife_interpolation(input_dir, output_dir, scale=0.5, threads_spec="2:2:2", gpu_id=gpu_id)


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        ok = run_rife_interpolation(sys.argv[1], sys.argv[2])
    else:
        print("usage: rife_vulkan_pipeline.py <input_frames_dir> <output_frames_dir> [model_dir]")
        print("       extract:  ffmpeg -i in.mp4 frames/%08d.png")
        print("       remux:    ffmpeg -framerate 120 -i frames_out/%08d.png -c:v hevc_nvenc ... out.mp4")
        ok = True
    sys.exit(0 if ok else 1)
