"""verify_world.py — Phase 1 world-model integration check.

Exercises the real gateway: world state, canonical event ingest, health,
camera frame + latest, sensor state, and the black/green UI shell.

    python SCRIPTS/automation/verify_world.py [--json] [--tests]

Exit 0 only when every critical check passes. Safe to run while live.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATEWAY = os.environ.get("ABRASAX_GATEWAY", "http://127.0.0.1:9001").rstrip("/")
UI = os.environ.get("ABRASAX_UI", "http://127.0.0.1:8090").rstrip("/")
TOKEN = os.environ.get("ABRASAX_GATEWAY_TOKEN") or os.environ.get("ABRASAX_TOKEN")

# 1x1 white JPEG, a valid frame for the camera route.
JPEG_1PX = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAP//////////////////////////////////////////"
    "//////////////////////////////////////////////////////////////wAALCAABAAEB"
    "AREA/8QAFAABAAAAAAAAAAAAAAAAAAAAA//EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEA"
    "AD8AfwD/2Q=="
)


def _headers(content_type: str | None = None) -> dict:
    h: dict[str, str] = {}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    if content_type:
        h["Content-Type"] = content_type
    return h


def _req(method: str, url: str, data: bytes | None = None,
         content_type: str | None = None, timeout: float = 15.0) -> dict:
    req = urllib.request.Request(url, data=data, headers=_headers(content_type),
                                 method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(65536)
            return {"ok": 200 <= resp.status < 300, "status": resp.status,
                    "content_type": resp.headers.get("Content-Type", ""),
                    "bytes": len(body), "body": body,
                    "ms": round((time.perf_counter() - started) * 1000, 1)}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code,
                "body": exc.read(500),
                "ms": round((time.perf_counter() - started) * 1000, 1)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": None, "error": f"{type(exc).__name__}: {exc}",
                "ms": round((time.perf_counter() - started) * 1000, 1)}


def _json_body(r: dict):
    try:
        return json.loads(r.get("body") or b"{}")
    except Exception:  # noqa: BLE001
        return {}


def _check(name: str, r: dict, *, critical: bool = True, predicate=None) -> dict:
    ok = bool(r.get("ok"))
    if ok and predicate is not None:
        try:
            ok = bool(predicate(r))
        except Exception:  # noqa: BLE001
            ok = False
    out = {"name": name, "critical": critical, "ok": ok,
           "status": r.get("status"), "ms": r.get("ms")}
    if r.get("error"):
        out["error"] = r["error"]
    if not ok and r.get("body"):
        out["body"] = r["body"][:200].decode("utf-8", "replace")
    return out


def _event(seq: int) -> dict:
    now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    return {
        "event_id": f"verify-{seq}-{int(time.time())}",
        "seq": seq,
        "sensor_id": "imu",
        "provider_id": "verify",
        "sensor_type": "sensor",
        "origin": "simulated",
        "schema_version": "1.0",
        "sync_status": "unsynced",
        "quality": "ok",
        "calibration": "unknown",
        "ts_origin": now,
        "payload_type": "json",
        "payload": {"mag": [1.0, 2.0, 3.0], "imu": [0, 0, 9.81, 0, 0, 0],
                    "env": [1013.0, 100.0]},
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--tests", action="store_true")
    args = ap.parse_args(argv)

    checks: list[dict] = []

    r = _req("GET", f"{GATEWAY}/v1/world/state")
    checks.append(_check("world_state", r,
                         predicate=lambda x: "entities" in _json_body(x)))

    r = _req("POST", f"{GATEWAY}/v1/world/ingest",
             json.dumps(_event(1)).encode(), "application/json")
    body = _json_body(r)
    checks.append(_check("world_ingest", r,
                         predicate=lambda x: bool(body.get("ok", True))))

    r = _req("GET", f"{GATEWAY}/v1/world/health")
    body = _json_body(r)
    health = body.get("health") if isinstance(body.get("health"), dict) else body
    checks.append(_check("world_health", r,
                         predicate=lambda x: health.get("status") in
                         {"ok", "degraded", "critical"}))

    r = _req("POST", f"{GATEWAY}/v1/camera/frame", JPEG_1PX, "image/jpeg")
    checks.append(_check("camera_frame", r))

    r = _req("GET", f"{GATEWAY}/v1/camera/latest")
    checks.append(_check("camera_latest", r,
                         predicate=lambda x: "image/jpeg" in (x.get("content_type") or "")
                         and x.get("bytes", 0) > 0))

    r = _req("GET", f"{GATEWAY}/v1/camera/state")
    checks.append(_check("camera_state", r))

    r = _req("GET", f"{GATEWAY}/v1/sensors/state")
    checks.append(_check("sensor_state", r))

    r = _req("GET", f"{UI}/world/")
    checks.append(_check("world_ui", r, critical=False,
                         predicate=lambda x: b"world" in (x.get("body") or b"").lower()))

    if args.tests:
        cmd = [sys.executable, "-m", "pytest",
               "TESTS/python/test_fusion.py", "TESTS/python/test_world_health.py",
               "TESTS/python/test_camera.py", "TESTS/python/test_gateway_world.py",
               "TESTS/python/test_world_ui.py",
               "-q", "--no-header", "-p", "no:cacheprovider"]
        started = time.perf_counter()
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                              timeout=600)
        tail = (proc.stdout or proc.stderr).strip().splitlines()[-1:]
        checks.append({"name": "phase1_tests", "critical": False,
                       "ok": proc.returncode == 0, "exit": proc.returncode,
                       "summary": (tail[0] if tail else "")[:180],
                       "ms": round((time.perf_counter() - started) * 1000, 1)})

    failed = [c for c in checks if c.get("critical", True) and not c.get("ok")]
    report = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "gateway": GATEWAY, "ok": not failed,
              "failed": [c["name"] for c in failed], "checks": checks}
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        for c in checks:
            state = "PASS" if c.get("ok") else ("FAIL" if c.get("critical", True) else "warn")
            detail = f"{c.get('status') or ''} {c.get('ms', '')}ms"
            if c.get("error"):
                detail += f" {c['error'][:100]}"
            if c.get("body"):
                detail += f" body={c['body'][:80]!r}"
            if c.get("summary"):
                detail += f" {c['summary']}"
            print(f"{state:4} {c['name']:18} {detail}")
        print(f"\n{'OK' if report['ok'] else 'FAILED'}: {len(failed)} critical failure(s)")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
