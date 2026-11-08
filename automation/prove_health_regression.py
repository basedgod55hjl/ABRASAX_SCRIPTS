"""Prove the regression is real and the fix removes it.

Measures health() itself, not process exit: a wedged worker is a non-daemon
thread, so it keeps the interpreter alive after main returns no matter how the
pool is shut down. The old code blocks *inside* health() (shutdown(wait=True)
joins the wedged worker); the patched code returns at timeout + grace.
"""
import io, os, shutil, subprocess, sys, tempfile

SRC = r"C:\ABRASAX\abrasax\services.py"
text = io.open(SRC, encoding="utf-8").read()
if "wait=False" not in text:
    raise SystemExit("fix not present - nothing to prove against")

old_health = '''def health(timeout: float = 0.6, include_daemons: bool = True) -> list[dict]:
    items = list_services(include_daemons=include_daemons)
    targets = [s for s in items if s.get("port")]
    with cf.ThreadPoolExecutor(max_workers=min(8, len(targets) or 1)) as pool:
        futures = {
            pool.submit(_probe, s["host"], s["port"], timeout,
                        _HEALTH_PATHS.get(s["id"])): s
            for s in targets
        }
        for fut in cf.as_completed(futures):
            s = futures[fut]
            s.update(fut.result())
    for s in items:
        if not s.get("port"):
            s.update({"up": None, "latency_ms": None, "error": None})
    return items
'''
start = text.index("def health(timeout: float = 0.6")
end = text.index("def get(service_id: str)")
old_src = text[:start] + old_health + "\n\n" + text[end:]

harness = '''
import os, sys, threading, time
sys.path.insert(0, sys.argv[1])
from abrasax import services

def wedge(host, port, timeout, path=None):
    threading.Event().wait(3600)          # never returns; simulates stuck connect
services._probe = wedge

t0 = time.monotonic()
services.health(timeout=0.2)
dt = time.monotonic() - t0
print("HEALTH_RETURNED %.1f" % dt, flush=True)
os._exit(0)                               # hard exit: ignore non-daemon workers
'''


def run(label, source_text):
    d = tempfile.mkdtemp(prefix="regress_")
    pkg = os.path.join(d, "abrasax")
    shutil.copytree(os.path.join(r"C:\ABRASAX", "abrasax"), pkg,
                    ignore=shutil.ignore_patterns("__pycache__"))
    io.open(os.path.join(pkg, "services.py"), "w",
            encoding="utf-8", newline="\n").write(source_text)
    h = os.path.join(d, "harness.py")
    io.open(h, "w", encoding="utf-8").write(harness)
    try:
        cp = subprocess.run([sys.executable, "-u", h, d], cwd=d,
                            capture_output=True, text=True, timeout=12)
        line = (cp.stdout or "").strip().splitlines()
        print("%-4s -> %s" % (label, line[-1] if line else repr(cp.stderr[-200:])))
        return "returned"
    except subprocess.TimeoutExpired:
        print("%-4s -> BLOCKED inside health() for >12s (watchdog killed it)" % label)
        return "blocked"
    finally:
        shutil.rmtree(d, ignore_errors=True)


print("== pre-fix code ==")
a = run("OLD", old_src)
print("== patched code ==")
b = run("NEW", text)
print()
if a == "blocked" and b == "returned":
    print("PROVEN: pre-fix health() blocks forever on a wedged probe; the fix returns.")
    sys.exit(0)
print("INCONCLUSIVE old=%s new=%s" % (a, b))
sys.exit(1)
