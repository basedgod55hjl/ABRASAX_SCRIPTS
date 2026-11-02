"""
cuda_load.py — sustained NVIDIA CUDA load, used to identify which GPU-engine LUID is NVIDIA.

Runs the crystal kernels in a loop for N seconds so the GPU Engine performance counters show
this process on the NVIDIA adapter. Comparing its LUID with VLC's LUID then tells us which
adapter VLC is actually rendering on, without needing registry LUID mapping.

Usage: cuda_load.py [seconds]
"""
import ctypes as C
import math
import os
import sys
import time

DLL = r"C:\Users\sirch\Desktop\ABRASAX_GOD_OS\build\crystal_dll\crystal_kernels.dll"
SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 25

lib = C.CDLL(DLL)
f32 = C.c_float
P = C.POINTER(f32)
N = 4096

lib.cuda_crystal_resonance.restype = C.c_int
lib.cuda_crystal_resonance.argtypes = [P, P, P, C.c_int]
lib.cuda_quantum_evolution_2d.restype = C.c_int
lib.cuda_quantum_evolution_2d.argtypes = [P, P, C.c_int, C.c_int, f32, f32]

buf = (f32 * N)()
for i in range(N):
    buf[i] = math.sin(i * 0.01)
align = (f32 * N)()
coh = (f32 * N)()
q_out = (f32 * N)()

t0 = time.time()
iters = 0
while time.time() - t0 < SECONDS:
    lib.cuda_crystal_resonance(buf, align, coh, N)
    lib.cuda_quantum_evolution_2d(buf, q_out, 64, 64, f32(math.pi / 4), f32(0.01))
    iters += 1

dt = time.time() - t0
print("CUDA load done: %d iterations in %.1fs (%.1f iter/s) on the NVIDIA device" % (iters, dt, iters / dt))
