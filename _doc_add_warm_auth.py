from pathlib import Path

p = Path(r"C:\abrasax\DOC\RUN-STATE-20261101T1735Z.md")
s = p.read_text(encoding="utf-8")
assert "## 12. A rejected key" not in s

s += """
---

## 12. A rejected key is not a dead server

Found while watching the autonomous loop come back online. Every 60 s the build
loop wrote:

```
{"ok": false, "error": "HTTP Error 401: Unauthorized", "auth": true}
```

while the same function in a fresh process returned 200, and a manual probe
split the cases cleanly:

```
with key    -> 200
without key -> 401 {"message": "An LM Studio API token is required ..."}
```

`auth: true` only meant *a key exists*; the resident loop had started at 12:13
with a key the server no longer accepted. Two lessons, both encoded:
`_lmstudio_key()` is resolved fresh on every call (a rotated key needs no
restart), a 401 triggers one re-resolve-and-retry, and the result now separates
`auth_ok` (the server accepted it) from `auth_stale` (a key exists and was
refused). The resident loop was then restarted; its next cycle wrote
`warm={"ok":true,"status":200,"auth_ok":true}`.

Same family as the headless bug: the *resident* process was the stale thing. A
long-running daemon keeps the code and credentials it imported.

Tests: `tests/test_buildloop_warm_auth.py` (3).
"""
p.write_text(s, encoding="utf-8", newline="")
print("doc updated with §12")
