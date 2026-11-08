"""fix_buildloop_warm_auth.py - a stale key must not fail every cycle.

MEASURED 2026-11-01T18:20Z, live build-loop ledger, every 60 s:

    {"ok": false, "error": "HTTP Error 401: Unauthorized", "auth": true}

while the same code in a fresh process returned

    {'ok': True, 'status': 200, 'auth': True}

and a manual probe showed the server's answer clearly:

    with key    -> 200
    without key -> 401 {"message": "An LM Studio API token is required ..."}

So the resident build loop held a key that the current server rejects: it
started at 12:13 and resolves the key once per call from a loader that had
already been imported. `auth: true` only meant "a key exists", not "the server
accepted it" - the field was reassuring and wrong.

Fix:
  * `_lmstudio_key()` is resolved fresh on every call (router loader, then
    process env), so a rotated key is picked up without a restart;
  * a 401 triggers one re-resolve-and-retry;
  * `auth` now reports whether the key was ACCEPTED (`auth_ok`), and
    `auth_stale` distinguishes "key rejected" from "server down".

Idempotent.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\abrasax\build_loop.py")

OLD = '''def _warm() -> dict:
    try:
        import urllib.request
        # LM Studio requires Bearer auth when "Require Authentication" is on.
        # Reuse the router's .env loader so there is exactly one credential path.
        headers = {"Content-Type": "application/json"}
        try:
            from agents.agents_hub.llm_router import _load_env
            env = _load_env()
        except Exception:
            env = {}
        key = (env.get("LM_STUDIO_API_KEY") or env.get("LM_API_KEY")
               or os.environ.get("LM_STUDIO_API_KEY") or os.environ.get("LM_API_KEY") or "")
        if key:
            headers["Authorization"] = f"Bearer {key}"
        req = urllib.request.Request(
            "http://127.0.0.1:1234/v1/chat/completions",
            data=json.dumps({
                "model": "liquid/lfm2.5-1.2b",
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 2,
                "stream": False,
            }).encode(),
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=25) as r:
            return {"ok": True, "status": r.status, "auth": bool(key)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "auth": bool(key)}'''

NEW = '''def _lmstudio_key() -> str:
    """The LM Studio token, resolved FRESH (a rotated key is picked up here)."""
    try:
        from agents.agents_hub.llm_router import _load_env
        env = _load_env()
    except Exception:  # noqa: BLE001
        env = {}
    env = {**(env or {}), **{k: v for k, v in os.environ.items()
                             if k in ("LM_STUDIO_API_KEY", "LM_API_KEY")}}
    return (env.get("LM_STUDIO_API_KEY") or env.get("LM_API_KEY") or "").strip()


def _warm() -> dict:
    import urllib.error
    import urllib.request

    body = json.dumps({
        "model": "liquid/lfm2.5-1.2b",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 2,
        "stream": False,
    }).encode()

    def call(key: str):
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        req = urllib.request.Request("http://127.0.0.1:1234/v1/chat/completions",
                                     data=body, headers=headers)
        return urllib.request.urlopen(req, timeout=25)

    key = _lmstudio_key()
    try:
        try:
            with call(key) as r:
                return {"ok": True, "status": r.status, "auth": bool(key),
                        "auth_ok": True}
        except urllib.error.HTTPError as exc:
            if exc.code not in (401, 403):
                raise
            # One re-resolve: the resident process may have started before the
            # key was rotated, and "a key exists" is not "the server liked it"
            # (measured 18:20Z: auth:true, every cycle 401).
            fresh = _lmstudio_key()
            if fresh and fresh != key:
                with call(fresh) as r:
                    return {"ok": True, "status": r.status, "auth": True,
                            "auth_ok": True, "key_reloaded": True}
            return {"ok": False, "error": f"HTTP Error {exc.code}: Unauthorized",
                    "auth": bool(fresh), "auth_ok": False, "auth_stale": True}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:200], "auth": bool(key),
                "auth_ok": False}'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "_lmstudio_key" in src:
        print("already applied")
        return 0
    if src.count(OLD) != 1:
        raise SystemExit(f"anchor {src.count(OLD)}x")
    TARGET.write_text(src.replace(OLD, NEW, 1), encoding="utf-8", newline="")
    print("patched", TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
