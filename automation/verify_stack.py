"""verify_stack.py — one-shot truth check for the ABRASAX stack.

Prints a JSON report and exits 0 only when every critical check passes.
No writes, no restarts, no killing. Safe to run while the stack is live.

Usage:
    python SCRIPTS/automation/verify_stack.py [--json] [--no-chat] [--tests]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from abrasax import services  # noqa: E402


_TOKEN_CACHE: str | None = None


def _load_token() -> str:
    """Gateway bearer token from env or ABRASAX .env files (never printed)."""
    global _TOKEN_CACHE
    if _TOKEN_CACHE is not None:
        return _TOKEN_CACHE
    for key in ("ABRASAX_GATEWAY_TOKEN", "ABRASAX_TOKEN"):
        val = os.environ.get(key)
        if val:
            _TOKEN_CACHE = val
            return val
    candidates = [Path(r"C:\ABRASAX\.env")]
    if (ROOT / ".env") not in candidates:
        candidates.append(ROOT / ".env")
    for env_path in candidates:
        try:
            for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                if key.strip() in ("ABRASAX_GATEWAY_TOKEN", "ABRASAX_TOKEN") and value.strip():
                    _TOKEN_CACHE = value.strip().strip('"').strip("'")
                    return _TOKEN_CACHE
        except OSError:
            continue
    _TOKEN_CACHE = ""
    return ""


def _http(url: str, timeout: float = 8.0, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    token = _load_token()
    if token and "/v1/" in url:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(4096)
            return {"ok": 200 <= resp.status < 300, "status": resp.status,
                    "bytes": len(body), "ms": round((time.perf_counter() - started) * 1000, 1),
                    "body": body}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code,
                "ms": round((time.perf_counter() - started) * 1000, 1),
                "error": exc.read(200).decode("utf-8", "replace")}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": None,
                "ms": round((time.perf_counter() - started) * 1000, 1),
                "error": f"{type(exc).__name__}: {exc}"}


def _json_check(name: str, url: str, *, critical: bool = True, timeout: float = 10.0) -> dict:
    r = _http(url, timeout=timeout)
    r.update({"name": name, "url": url, "critical": critical})
    r.pop("body", None)
    return r


def _chat_check(model: str | None) -> dict:
    payload = {
        "messages": [{"role": "user", "content": "Reply with exactly: ABRASAX-ONLINE"}],
        "max_tokens": 16,
        "temperature": 0,
    }
    if model:
        payload["model"] = model
    r = _http("http://127.0.0.1:9001/v1/chat/completions", timeout=120, payload=payload)
    body = r.pop("body", b"")
    r.update({"name": "gateway_chat", "url": "/v1/chat/completions",
              "critical": True})
    if r.get("ok"):
        try:
            data = json.loads(body)
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            r["model"] = data.get("model")
            r["routed_via"] = (data.get("abrasax") or {}).get("routed_via")
            r["content"] = content[:120]
            r["ok"] = bool(content)
        except Exception as exc:  # noqa: BLE001
            r["ok"] = False
            r["error"] = f"invalid JSON: {exc}"
    return r


def _unfold_check() -> dict:
    try:
        from abrasax import unfold
        started = time.perf_counter()
        result = unfold.unfold_from_genesis(vocab=4, dim=8)
        return {"name": "seed_to_manifold", "critical": True, "ok": True,
                "seed_sha256": result["seed_sha256"][:16],
                "dna_len": result["dna_len"],
                "ms": round((time.perf_counter() - started) * 1000, 1)}
    except Exception as exc:  # noqa: BLE001
        return {"name": "seed_to_manifold", "critical": True, "ok": False,
                "error": f"{type(exc).__name__}: {exc}"}


def _tests_check() -> dict:
    target = ROOT / "TESTS" / "python" / "test_enhance_core.py"
    started = time.perf_counter()
    proc = subprocess.run([sys.executable, "-m", "pytest", str(target), "-q",
                           "--no-header", "-p", "no:cacheprovider"],
                          cwd=str(ROOT), capture_output=True, text=True, timeout=300)
    tail = (proc.stdout or proc.stderr).strip().splitlines()[-1:] or [""]
    return {"name": "pytest_enhance_core", "critical": False,
            "ok": proc.returncode == 0, "exit": proc.returncode,
            "summary": tail[0][:160],
            "ms": round((time.perf_counter() - started) * 1000, 1)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="also print the report as JSON")
    ap.add_argument("--no-chat", action="store_true", help="skip the live LLM chat check")
    ap.add_argument("--tests", action="store_true", help="run the fast test subset")
    args = ap.parse_args(argv)

    checks: list[dict] = []
    rows = services.health(timeout=1.5)
    down = [r["id"] for r in rows
            if r.get("port") and r.get("up") is False]
    optional = {s["id"] for s in services.SERVICES if s.get("optional")}
    critical_down = [d for d in down if d not in optional]
    checks.append({"name": "services", "critical": True,
                   "ok": not critical_down, "up": len(rows) - len(down),
                   "down": down, "critical_down": critical_down})

    checks += [
        _json_check("gateway_health", "http://127.0.0.1:9001/health"),
        _json_check("gateway_metrics", "http://127.0.0.1:9001/metrics", critical=False),
        _json_check("gateway_models", "http://127.0.0.1:9001/v1/models"),
        _json_check("gateway_agents", "http://127.0.0.1:9001/v1/agents"),
        _json_check("brain_state", "http://127.0.0.1:9626/state"),
        _json_check("cellbrain_state", "http://127.0.0.1:9624/state", critical=False),
        _json_check("synaptic_state", "http://127.0.0.1:9625/state", critical=False),
        _json_check("ui", "http://127.0.0.1:8090/"),
        _json_check("floating_brain", "http://127.0.0.1:9700/"),
        _json_check("overlay", "http://127.0.0.1:9627/health", critical=False),
    ]
    if not args.no_chat:
        checks.append(_chat_check(os.environ.get("ABRASAX_VERIFY_MODEL")))
    checks.append(_unfold_check())
    if args.tests:
        checks.append(_tests_check())

    failed = [c for c in checks if c.get("critical", True) and not c.get("ok")]
    report = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "root": str(ROOT), "ok": not failed, "failed": [c["name"] for c in failed],
              "checks": checks}
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        for c in checks:
            state = "PASS" if c.get("ok") else ("FAIL" if c.get("critical", True) else "warn")
            detail = f"{c.get('status') or ''} {c.get('ms', '')}ms"
            if c.get("critical_down"):
                detail = f"down={','.join(c['critical_down'])}"
            if c.get("content"):
                detail += f" {c['content'][:40]!r}"
            if c.get("error"):
                detail += f" {c['error'][:90]}"
            print(f"{state:4} {c['name']:22} {detail}")
        print(f"\n{'OK' if report['ok'] else 'FAILED'}: {len(failed)} critical failure(s)")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
