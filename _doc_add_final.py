from pathlib import Path

p = Path(r"C:\abrasax\DOC\RUN-STATE-20261101T1735Z.md")
s = p.read_text(encoding="utf-8")
assert "## 13. Two more" not in s

s += """
---

## 13. Two more found by insisting on a green suite

### D12 - the default LM Studio model cannot fit on this GPU

```
POST :1234/v1/chat/completions  model=gemma-4-e2b-uncensored-hauhaucs-aggressive
-> HTTP 500 <html>Internal Server Error</html>
```

while `gemma-4-e2b-uncensored-hauhaucs-aggressive` answered (twice, 36 and 30 tokens). The GTX 1660 Ti
has 6 GB, llama.cpp holds ~1.4 GB for :8083, and gemma-4-e2b is a 4.0 GB file;
free VRAM measured during this session was 444-555 MB. LM Studio could not load
it, so every request naming the configured default failed and `route="auto"`
fell through to llamacpp-local. Local-first still held (zero paid calls), but the
first local provider was a dead end on every request.

`providers.json` now names the model that is actually resident for every chat
alias; the embedding alias keeps its embedder. The note explaining the
arithmetic lives in the config, so restoring gemma is a one-line change once the
VRAM budget exists.

Live after the change:

```
mode=local_only paid_allowed=False local_up=['llamacpp-local','lmstudio']
provider=lmstudio routed_via=lmstudio model=gemma-4-e2b-uncensored-hauhaucs-aggressive
content='ROUTER-LOCAL-OK'  LOCAL_ROUTE: OK
```

### D13 - the pidfile claim could hand out two winners under load

`test_exactly_one_winner_under_a_real_process_race` failed in the full suite at
18:33Z and passed 9/9 alone. The cause is a real hole, not flakiness:
`O_CREAT|O_EXCL` is atomic, but the winner writes its pid in a second step, so
for a few hundred microseconds the file exists and is **empty**. A loser in that
window read no owner, called it stale, unlinked the winner's lock and created its
own - two supervisors, which is exactly what the atomic claim was added to stop.

The two "no owner" cases are now distinct: an empty file younger than a 2 s grace
is a winner mid-write (wait and re-read); an empty file older than that, or a
non-empty body naming no live pid, is stale (unlink and retry). The pid is
written with `fsync`, and the window is pinned by a test that writes a live
foreign pid 0.2 s after the empty create.

### Final numbers

```
python -m pytest -q            395 passed, 2 skipped   (123.57 s)
verify_stack_run.py            STACK RUN: OK up=16 down=3 failed=0
abrasax autonomy               mode=local_only  paid_allowed=False
                               lmstudio=up, llamacpp-local=up
visible consoles               2   (both the operator's own term.cmd)
```
"""
p.write_text(s, encoding="utf-8", newline="")
print("doc updated with §13")
