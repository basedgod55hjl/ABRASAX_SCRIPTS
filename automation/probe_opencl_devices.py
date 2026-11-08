"""Enumerate OpenCL devices and actually run a kernel, now that pyopencl is installed.

Installed: pyopencl 2026.1.4 (+ pytools, siphash24, platformdirs), 0.7 MB wheel,
prebuilt for cp311 win_amd64 so no compiler was needed.

What must be proven:
  1  the AMD OpenCL platform is visible at all
  2  a kernel compiles and runs on the AMD device
  3  the result is numerically correct
  4  a throughput number, comparable to the CUDA number measured earlier
     (CUDA: 0.32 TFLOP/s for 1024^3 matmul; OpenCL here: memory bandwidth on axpy)

If the AMD iGPU cannot run a kernel, that is the honest answer and it is reported
with the exact OpenCL error.
"""
import json
import sys
import time

try:
    import pyopencl as cl
    import numpy as np
except ImportError as e:
    print(f"import failed: {e}")
    sys.exit(1)

print(f"pyopencl: {cl.VERSION_TEXT if hasattr(cl, 'VERSION_TEXT') else cl.version.VERSION_TEXT}")

print("\n=== platforms and devices ===")
platforms = cl.get_platforms()
print(f"{len(platforms)} platform(s)")
targets = []
for pi, plat in enumerate(platforms):
    print(f"\n[{pi}] {plat.name}")
    print(f"    vendor : {plat.vendor}")
    print(f"    version: {plat.version}")
    try:
        devs = plat.get_devices()
    except Exception as e:  # noqa: BLE001
        print(f"    get_devices failed: {type(e).__name__}: {e}")
        continue
    for di, dev in enumerate(devs):
        dtype = cl.device_type.to_string(dev.type)
        print(f"    [{di}] {dev.name}")
        print(f"         type   : {dtype}")
        print(f"         CU/MHz : {dev.max_compute_units} / {dev.max_clock_frequency}")
        try:
            print(f"         global : {dev.global_mem_size / 1024**2:.0f} MiB")
            print(f"         local  : {dev.local_mem_size / 1024:.0f} KiB")
        except Exception:
            pass
        targets.append((pi, di, dev.name, dtype))

print(f"\n=== running a kernel on each device ===")
SRC = """
__kernel void axpy(const float a, __global const float* x, __global float* y) {
    int i = get_global_id(0);
    y[i] = a * x[i] + y[i];
}
"""

N = 1 << 20            # 1M floats = 4 MiB per vector
ITERS = 100

results = []
for pi, di, dname, dtype in targets:
    print(f"\n--- [{pi}:{di}] {dname} ({dtype}) ---")
    try:
        dev = platforms[pi].get_devices()[di]
        ctx = cl.Context(devices=[dev])
        queue = cl.CommandQueue(ctx)
        prog = cl.Program(ctx, SRC).build()
    except Exception as e:  # noqa: BLE001
        print(f"  setup failed: {type(e).__name__}: {str(e)[:300]}")
        results.append({"device": dname, "ok": False, "error": str(e)[:200]})
        continue

    x = np.ones(N, dtype=np.float32)
    y = np.zeros(N, dtype=np.float32)
    mf = cl.mem_flags
    try:
        xb = cl.Buffer(ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=x)
        yb = cl.Buffer(ctx, mf.WRITE_ONLY, y.nbytes)
        # warm up
        prog.axpy(queue, (N,), None, np.float32(2.0), xb, yb)
        queue.finish()

        t0 = time.perf_counter()
        for _ in range(ITERS):
            prog.axpy(queue, (N,), None, np.float32(2.0), xb, yb)
        queue.finish()
        dt = time.perf_counter() - t0

        out = np.empty_like(y)
        cl.enqueue_copy(queue, out, yb).wait()

        # axpy moves read x + write y = 2 vectors per iteration
        gbs = (N * 4 * 2 * ITERS) / dt / 1e9
        correct = bool(np.allclose(out, 2.0))
        print(f"  axpy {ITERS}x N={N}: {dt:.3f}s  = {gbs:.1f} GB/s")
        print(f"  verified          : {correct}")
        results.append({"device": dname, "ok": correct, "gbs": round(gbs, 1)})
    except Exception as e:  # noqa: BLE001
        print(f"  kernel failed: {type(e).__name__}: {str(e)[:300]}")
        results.append({"device": dname, "ok": False, "error": str(e)[:200]})

print("\n=== SUMMARY ===")
for r in results:
    if r.get("ok"):
        print(f"  {r['device']:44s} OK  {r['gbs']} GB/s")
    else:
        print(f"  {r['device']:44s} FAIL  {r.get('error', '')[:60]}")

out_path = r"C:\ABRASAX\LOGS\opencl-devices.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump({"platforms": len(platforms), "results": results}, f, indent=2)
print(f"\nwrote {out_path}")
