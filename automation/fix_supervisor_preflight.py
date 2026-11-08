import io, os, shutil

P = r"C:\ABRASAX\SCRIPTS\automation\supervisor.py"
src = io.open(P, encoding="utf-8").read()

OLD = '''def _start_service(service_id: str, spec: dict) -> dict:
    cwd = Path(spec["cwd"])
    log_path = LOGS / f"svc-{service_id}.log"
    try:
'''

NEW = '''def _preflight(spec: dict) -> dict | None:
    """Refuse to launch a service whose declared prerequisites are absent.

    A missing binary or model used to be launched anyway, fail instantly, and
    burn the whole 180 s cooldown on every tick - the "flapping" seen for
    llamacpp-local on 2026-11-01. Returning a reason here makes that visible
    instead of silent.
    """
    for req in spec.get("requires") or []:
        if not Path(req).exists():
            return {"error": f"missing prerequisite: {req}", "blocked": True}
    return None


def _start_service(service_id: str, spec: dict) -> dict:
    blocked = _preflight(spec)
    if blocked:
        return blocked
    cwd = Path(spec["cwd"])
    log_path = LOGS / f"svc-{service_id}.log"
    try:
'''

if OLD not in src:
    raise SystemExit("ANCHOR NOT FOUND")
if "_preflight" in src:
    raise SystemExit("already patched")

src = src.replace(OLD, NEW, 1)

# A blocked service must not be counted as started.
OLD2 = '''        result = _start_service(sid, spec)
        started.append(sid)
        _ledger({"event": "start", "svc": sid, **result})
        events.append({"svc": sid, "state": "started", **result})'''
NEW2 = '''        result = _start_service(sid, spec)
        if result.get("blocked"):
            # Do not record cooldown or "started" for a service we never launched.
            _last_start.pop(sid, None)
            _ledger({"event": "blocked", "svc": sid, **result})
            events.append({"svc": sid, "state": "blocked", **result})
            continue
        started.append(sid)
        _ledger({"event": "start", "svc": sid, **result})
        events.append({"svc": sid, "state": "started", **result})'''

if OLD2 not in src:
    raise SystemExit("start-block anchor not found")
src = src.replace(OLD2, NEW2, 1)

bak = P + ".bak-preflight"
if not os.path.exists(bak):
    shutil.copy2(P, bak)
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("patched", P, os.path.getsize(P), "bytes")
