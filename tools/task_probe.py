"""Probe: which step of a sense tick blocks under Task Scheduler?

Writes a line-by-line trace so a hang is localised without guesswork.
Run it from the scheduled task and read the trace even if it never finishes.
"""
import sys, time, traceback, pathlib

TRACE = pathlib.Path(r"C:\ABRASAX\LOGS\task-probe.log")

def log(msg):
    with TRACE.open("a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
        fh.flush()

log("=== probe start ===")
log(f"cwd={pathlib.Path.cwd()}")
log(f"sys.executable={sys.executable}")

try:
    log("import abrasax.adb_sensors")
    from abrasax.adb_sensors import AdbSensorReader, find_adb, _run
    log(f"find_adb -> {find_adb()}")

    log("adb devices")
    t = time.time()
    s = AdbSensorReader().device_serial()
    log(f"device_serial -> {s} in {time.time()-t:.2f}s")

    log("dumpsys sensorservice")
    t = time.time()
    out = AdbSensorReader().dump()
    log(f"dump len={len(out)} in {time.time()-t:.2f}s")

    log("import phone_senses")
    from abrasax.phone_senses import build_registry
    log("build_registry")
    t = time.time()
    reg = build_registry()
    log(f"registry built in {time.time()-t:.2f}s")

    log("discover (this probes HTTP :8081 with a 5s timeout)")
    t = time.time()
    rows = reg.discover()
    log(f"discover done in {time.time()-t:.2f}s: "
        + ", ".join(f"{r['key']}={r['status']}" for r in rows))

    log("read_all")
    t = time.time()
    evs = reg.read_all()
    log(f"read_all -> {len(evs)} events in {time.time()-t:.2f}s")

    log("=== probe OK ===")
except Exception:
    log("EXCEPTION:\n" + traceback.format_exc())
