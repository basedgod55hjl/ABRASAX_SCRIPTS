import hashlib
import time

import numpy as np

import abrasax.brain as b

t0 = time.time()
f = b.field()
print(f"field()            {time.time()-t0:7.2f}s  n={f.n} size={f.size}")

for label, fn in [
    ("state.mean",        lambda: float(f.state.mean())),
    ("np.mean(signal)",   lambda: float(np.mean(f.signal))),
    ("memory.mean",       lambda: float(f.memory.mean())),
    ("sha(state.tobytes)", lambda: hashlib.sha256(f.state.tobytes()).hexdigest()),
    ("genome()",          lambda: f.genome()),
    ("backend_name()",    lambda: b.backend_name()),
    ("metrics()",         lambda: f.metrics()),
    ("theta",             lambda: dict(f.theta)),
]:
    t = time.time()
    try:
        fn()
        print(f"{label:20s} {time.time()-t:7.2f}s")
    except Exception as exc:
        print(f"{label:20s} ERROR {type(exc).__name__}: {exc}")

t = time.time()
f.summary()
print(f"{'summary() total':20s} {time.time()-t:7.2f}s")
