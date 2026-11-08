"""Gateway hardening: refuse a non-loopback bind without ABRASAX_GATEWAY_TOKEN.

`DOC/GATEWAY-PROD.md` §2 states open mode is "only defensible because the socket is
bound to 127.0.0.1", but nothing enforced it: `serve(host=...)` would happily bind
0.0.0.0 with auth open. This adds the guard the doc assumes.

Idempotent. Exit 0 = patched or already patched, 1 = anchor not found.
"""
import shutil
import sys
import time

PATH = r"C:\ABRASAX\abrasax\gateway.py"
SENTINEL = "_LOOPBACK_HOSTS"

src = open(PATH, encoding="utf-8").read()

if SENTINEL in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

anchor = 'def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:\n'
if anchor not in src:
    print("ANCHOR-NOT-FOUND: serve() signature")
    sys.exit(1)

guard = '_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})\n' + '''def _assert_bind_is_safe(host: str) -> None:
    """Open auth on a non-loopback bind is a remote-spend hole. Fail closed.

    DOC/GATEWAY-PROD.md §2: open mode is only defensible on loopback. The doc said
    so; nothing enforced it. Escape hatch for a real deployment that terminates
    auth upstream: ABRASAX_GATEWAY_ALLOW_PUBLIC=1.
    """
    if host in _LOOPBACK_HOSTS:
        return
    if _auth_token():
        return
    if os.environ.get("ABRASAX_GATEWAY_ALLOW_PUBLIC", "").strip() in {"1", "true", "yes"}:
        _log(f"gateway binding to non-loopback host {host!r} with auth open "
             f"(ABRASAX_GATEWAY_ALLOW_PUBLIC set)")
        return
    raise SystemExit(
        f"refusing to bind {host!r}: gateway auth is open and {host!r} is not loopback. "
        "Set ABRASAX_GATEWAY_TOKEN (bearer auth) or ABRASAX_GATEWAY_ALLOW_PUBLIC=1 "
        "to override. See DOC/GATEWAY-PROD.md section 2."
    )


'''

body_old = anchor + '    """Run the gateway server (blocking)."""\n    httpd = ThreadingHTTPServer((host, port), _Handler)\n'
body_new = (anchor
            + '    """Run the gateway server (blocking)."""\n'
            + '    _assert_bind_is_safe(host)\n'
            + '    httpd = ThreadingHTTPServer((host, port), _Handler)\n')

if body_old not in src:
    print("ANCHOR-NOT-FOUND: serve() body")
    sys.exit(1)

out = src.replace(body_old, body_new, 1).replace(anchor, guard + anchor, 1)

backup = PATH + time.strftime(".bak-%Y%m%d-%H%M")
shutil.copy2(PATH, backup)
with open(PATH, "w", encoding="utf-8", newline="") as f:
    f.write(out)

print(f"PATCHED; backup {backup.rsplit(chr(92), 1)[-1]}; {len(src)} -> {len(out)} bytes")
