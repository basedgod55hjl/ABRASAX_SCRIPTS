import io, os, shutil, time

P = r"C:\ABRASAX\abrasax\services.py"
src = io.open(P, encoding="utf-8").read()

OLD = '''def health(timeout: float = 0.6, include_daemons: bool = True) -> list[dict]:
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

NEW = '''def health(timeout: float = 0.6, include_daemons: bool = True) -> list[dict]:
    """Probe every service, but never block longer than `timeout` + grace.

    Measured 2026-10-31/11-01: the supervisor loop wedged permanently (zero CPU,
    heartbeat frozen) with workers parked in
    socket.create_connection -> services.py:_probe_http.  The per-socket timeout
    does not reliably bound a connect on Windows, and the previous
    `with ThreadPoolExecutor(...)` called shutdown(wait=True), which joins those
    workers for ever - one stuck connect froze the whole supervisor.

    Two guarantees now:
      * the pool is never joined (shutdown(wait=False)), so a wedged worker can
        only strand itself, never the caller;
      * every future has a hard deadline, after which it is reported 'down' with
        a timeout error instead of being waited on.
    """
    items = list_services(include_daemons=include_daemons)
    targets = [s for s in items if s.get("port")]
    if targets:
        # A wedged worker leaks a thread; cap the damage per call.
        pool = cf.ThreadPoolExecutor(max_workers=min(8, len(targets)))
        try:
            futures = {
                pool.submit(_probe, s["host"], s["port"], timeout,
                            _HEALTH_PATHS.get(s["id"])): s
                for s in targets
            }
            deadline = time.monotonic() + max(0.0, timeout) + _HEALTH_GRACE_S
            done, pending = cf.wait(futures, timeout=deadline - time.monotonic())
            for fut in done:
                try:
                    futures[fut].update(fut.result())
                except Exception as exc:  # noqa: BLE001 - a probe must not kill a tick
                    futures[fut].update(
                        {"up": False, "latency_ms": None,
                         "error": f"{exc.__class__.__name__}: {exc}"[:160]})
            for fut in pending:
                fut.cancel()
                futures[fut].update(
                    {"up": False, "latency_ms": None,
                     "error": f"TimeoutError: probe exceeded "
                              f"{max(0.0, timeout) + _HEALTH_GRACE_S:.1f}s"})
        finally:
            # wait=False is the whole point: a worker stuck in a connect syscall
            # must never be able to block the supervisor's tick loop.
            pool.shutdown(wait=False)
    for s in items:
        if not s.get("port"):
            s.update({"up": None, "latency_ms": None, "error": None})
    return items
'''

if OLD not in src:
    raise SystemExit("ANCHOR NOT FOUND - refusing to patch")
if "_HEALTH_GRACE_S" in src:
    raise SystemExit("already patched")

src = src.replace(OLD, NEW, 1)

anchor = "def health(timeout: float = 0.6"
grace = ("# Slack granted on top of the per-socket timeout before a probe is declared\n"
         "# timed out. Bounded so health() can never hang the caller (see health()).\n"
         "_HEALTH_GRACE_S = 3.0\n\n\n")
src = src.replace(anchor, grace + anchor, 1)

bak = P + ".bak-healthlock"
if not os.path.exists(bak):
    shutil.copy2(P, bak)
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("patched", P, os.path.getsize(P), "bytes; backup", bak)
