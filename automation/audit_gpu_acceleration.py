"""Measure what hardware acceleration actually works, per pipeline, per device.

The directive asks for "full hardware acceleration across both NVIDIA and AMD compute
pipelines". Measured hardware:

    NVIDIA GeForce GTX 1660 Ti   617.14   sm_75   6144 MiB   (discrete)
    AMD Radeon(TM) Graphics      31.x     --      512 MiB    (integrated, shared RAM)

    CUDA 13.4.59 toolkit, torch 2.6.0+cu124 with cuda available
    AMD-OpenCL User Mode Driver present
    NO hipcc, NO ROCm  (ROCm has no official Windows support)

So "both pipelines" means: CUDA on NVIDIA (real), OpenCL on AMD (the only portable
route on Windows), and CPU. Anything else would be invented.

This measures each, with numbers:
  1  CUDA: a real kernel launch + a torch matmul, timed
  2  OpenCL: enumerate devices, run a kernel on the AMD iGPU, timed
  3  the renderer's own CUDA kernels (fb_kernels.cubin) already built for sm_75
  4  the actual bottleneck: VRAM headroom shared between LLM and renderer

Nothing is configured until it is known to work.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

ROOT = r"C:\ABRASAX"
PY = os.path.join(ROOT, "PYTHON", ".venv_gui", "Scripts", "python.exe")
CREATE_NO_WINDOW = 0x08000000


def run(cmd, timeout=120, cwd=ROOT):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, stdin=subprocess.DEVNULL,
                          creationflags=CREATE_NO_WINDOW)


print("=== 1. CUDA (NVIDIA) ===")
code_cuda = r'''
import torch, time
print("torch      :", torch.__version__)
print("cuda avail :", torch.cuda.is_available())
print("cuda ver   :", torch.version.cuda)
if torch.cuda.is_available():
    print("device     :", torch.cuda.get_device_name(0))
    print("capability :", torch.cuda.get_device_capability(0))
    p = torch.cuda.get_device_properties(0)
    print("sm count   :", p.multi_processor_count)
    print("vram total :", round(p.total_memory/1024**2), "MiB")
    # warm up
    a = torch.randn(1024, 1024, device="cuda")
    b = torch.randn(1024, 1024, device="cuda")
    torch.cuda.synchronize()
    # timed run
    n = 50
    t0 = time.perf_counter()
    for _ in range(n):
        c = a @ b
    torch.cuda.synchronize()
    dt = time.perf_counter() - t0
    tflops = (2 * 1024**3 * n) / dt / 1e12
    print(f"matmul     : {n} x 1024^3 in {dt:.3f}s  = {tflops:.2f} TFLOP/s")
    print("vram used  :", round(torch.cuda.memory_allocated(0)/1024**2), "MiB")
'''
r = run([PY, "-c", code_cuda], timeout=180)
print(r.stdout.rstrip() or r.stderr.rstrip()[:400])

print("\n=== 2. OpenCL (AMD iGPU) ===")
code_cl = r'''
try:
    import pyopencl as cl
except ImportError:
    print("pyopencl   : NOT INSTALLED")
    raise SystemExit(0)
import numpy as np, time
found = False
for plat in cl.get_platforms():
    print(f"platform   : {plat.name}")
    for dev in plat.get_devices():
        found = True
        print(f"  device   : {dev.name}")
        print(f"  type     : {cl.device_type.to_string(dev.type)}")
        print(f"  compute  : {dev.max_compute_units} CU, "
              f"{dev.max_clock_frequency} MHz")
        try:
            print(f"  global   : {dev.global_mem_size/1024**2:.0f} MiB")
        except Exception:
            pass
if not found:
    print("no OpenCL devices found")
    raise SystemExit(0)
ctx = cl.create_some_context(interactive=False)
queue = cl.CommandQueue(ctx)
prg = cl.Program(ctx, """
__kernel void axpy(const float a, __global const float* x,
                   __global float* y) {
    int i = get_global_id(0);
    y[i] = a * x[i] + y[i];
}
""").build()
N = 1 << 20
x = np.ones(N, dtype=np.float32)
y = np.zeros(N, dtype=np.float32)
mf = cl.mem_flags
xb = cl.Buffer(ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=x)
yb = cl.Buffer(ctx, mf.WRITE_ONLY, y.nbytes)
N_ITERS = 50
queue.finish()
t0 = time.perf_counter()
for _ in range(N_ITERS):
    prg.axpy(queue, (N,), None, np.float32(2.0), xb, yb)
queue.finish()
dt = time.perf_counter() - t0
gb = (N * 4 * 2 * N_ITERS) / dt / 1e9
out = np.empty_like(y)
cl.enqueue_copy(queue, out, yb).wait()
print(f"kernel     : axpy {N_ITERS}x N={N}  {dt:.3f}s  = {gb:.1f} GB/s")
print(f"verified   : {np.allclose(out, 2.0)}")
'''
r = run([PY, "-c", code_cl], timeout=180)
print(r.stdout.rstrip() or r.stderr.rstrip()[:400])

print("\n=== 3. the renderer's own CUDA kernels ===")
cubin = os.path.join(ROOT, "ENGINE", "floating_brain", "cuda", "bin", "fb_kernels.cubin")
if os.path.exists(cubin):
    print(f"  {cubin}  {os.path.getsize(cubin):,} bytes")
    cuobjdump = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.4\bin\cuobjdump.exe"
    if os.path.exists(cuobjdump):
        r = run([cuobjdump, "-symbols", cubin], timeout=60)
        funcs = [ln.split()[-1] for ln in r.stdout.splitlines() if "fb_" in ln and "STT_FUNC" in ln]
        print(f"  kernels: {len(funcs)} -> {', '.join(sorted(set(funcs)))}")
else:
    print("  cubin missing")

print("\n=== 4. VRAM headroom (the real constraint) ===")
r = run(["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free",
         "--format=csv,noheader,nounits"], timeout=30)
if r.returncode == 0:
    tot, used, free = [int(x) for x in r.stdout.strip().split(",")]
    print(f"  {used}/{tot} MiB used, {free} MiB free")
    print(f"  {free/tot*100:.1f}% headroom")

print("\nRESULT: measurement only")
sys.exit(0)
