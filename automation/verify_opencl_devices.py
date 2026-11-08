"""The kernel is correct; my assertion was wrong. 202 is exactly right.

MEASURED
    NVIDIA GTX 1660 Ti : axpy 100x  = 107.2 GB/s   out[:5] = [202, 202, ...]
    AMD gfx90c         : axpy 100x  =  16.4 GB/s   out[:5] = [202, 202, ...]

Both devices produced identical, correct output. The arithmetic:

    y starts at 0
    each iteration: y += 2.0 * x, where x is all ones  ->  y += 2.0
    100 iterations                                     ->  y = 200
    plus the warm-up iteration                         ->  y = 202

So 202 is the CORRECT result and my `np.allclose(out, 2.0)` was the bug. Both GPUs
work.

This is the fourth time tonight that a failing check was my error rather than the
system's, and the pattern is identical every time: I asserted a value I assumed
instead of simulating the kernel for one iteration.

Fixed assertion: after `warmup + ITERS` applications of `y += 2.0`, y must equal
2.0 * (ITERS + 1). Verify against that, and also verify a single-iteration case so
the check cannot pass by coincidence.
"""
import json
import time

import numpy as np
import pyopencl as cl

SRC = """
__kernel void axpy(const float a, __global const float* x, __global float* y) {
    int i = get_global_id(0);
    y[i] = a * x[i] + y[i];
}
"""

N = 1 << 20


def bench(dev, iters):
    ctx = cl.Context(devices=[dev])
    queue = cl.CommandQueue(ctx)
    prog = cl.Program(ctx, SRC).build()
    kernel = cl.Kernel(prog, "axpy")

    x = np.ones(N, dtype=np.float32)
    y = np.zeros(N, dtype=np.float32)
    mf = cl.mem_flags
    xb = cl.Buffer(ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=x)
    yb = cl.Buffer(ctx, mf.READ_WRITE | mf.COPY_HOST_PTR, hostbuf=y)

    kernel.set_arg(0, np.float32(2.0))
    kernel.set_arg(1, xb)
    kernel.set_arg(2, yb)

    # one warm-up application is part of the expected sum
    cl.enqueue_nd_range_kernel(queue, kernel, (N,), None).wait()

    t0 = time.perf_counter()
    for _ in range(iters):
        cl.enqueue_nd_range_kernel(queue, kernel, (N,), None)
    queue.finish()
    dt = time.perf_counter() - t0

    out = np.empty_like(y)
    cl.enqueue_copy(queue, out, yb).wait()

    expected = 2.0 * (iters + 1)          # warm-up + iters
    gbs = (N * 4 * 2 * iters) / dt / 1e9
    return {
        "elapsed_s": round(dt, 4),
        "gbs": round(gbs, 1),
        "expected": expected,
        "observed": float(out[0]),
        "ok": bool(np.allclose(out, expected)),
    }


results = []
for plat in cl.get_platforms():
    for dev in plat.get_devices():
        name = dev.name.strip()
        print("=" * 74)
        print(f"{name}   [{plat.name}]")
        print("=" * 74)

        # a single iteration: expected 4.0. If this passes and 100 passes, the
        # check cannot be satisfied by coincidence.
        one = bench(dev, 1)
        print(f"  1 iteration : expected {one['expected']}  observed {one['observed']}"
              f"  ok={one['ok']}")

        many = bench(dev, 100)
        print(f"  100 iterations: {many['elapsed_s']}s = {many['gbs']} GB/s"
              f"  expected {many['expected']}  observed {many['observed']}"
              f"  ok={many['ok']}")

        results.append({"device": name, "platform": plat.name,
                        "one_iter_ok": one["ok"], "bench_ok": many["ok"],
                        "gbs": many["gbs"], "observed": many["observed"],
                        "expected": many["expected"]})
        print()

print("=" * 74)
print("SUMMARY")
print("=" * 74)
for r in results:
    ok = r["one_iter_ok"] and r["bench_ok"]
    print(f"  {'OK  ' if ok else 'FAIL'} {r['device']:40s} {r['gbs']:6.1f} GB/s  "
          f"(y={r['observed']:.0f}, expected {r['expected']:.0f})")

allok = all(r["one_iter_ok"] and r["bench_ok"] for r in results) and bool(results)
with open(r"C:\ABRASAX\LOGS\opencl-verified.json", "w", encoding="utf-8") as f:
    json.dump({"all_ok": allok, "results": results}, f, indent=2)

print("\nRESULT:", "PASS -- both GPUs run correct OpenCL kernels"
      if allok else "FAIL")
