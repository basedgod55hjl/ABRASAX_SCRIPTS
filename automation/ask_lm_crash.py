"""Consolidate every overlay-related log into one evidence source, then ask
every available LM the same question about it.

Two outputs:
  1. DOC/REPORTS/OVERLAY-CRASH-EVIDENCE.md  -- the "source" pack: crash codes,
     exit log, service log, faulthandler dumps, and the relevant code.
  2. LOGS/lm-crash-verdicts.jsonl           -- one record per model attempted,
     including models that could not load (that failure is data, not noise).

The question asked is narrow on purpose. "How do I fix this?" invites generic
advice. "What is missing" asks for the specific measurement that would convert
a hypothesis into a diagnosis -- which is the only thing that has actually
advanced this bug so far.

Honesty rules enforced here:
  * A model that fails to load is recorded as a failure, never as an opinion.
  * Empty `content` with non-empty `reasoning_content` (thinking models) is
    recorded as `empty_content` rather than being silently treated as silence.
  * Nothing from a model is presented as a finding.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(r"C:\ABRASAX")
LOGS = ROOT / "LOGS"
DOC = ROOT / "DOC" / "REPORTS"
EVIDENCE = DOC / "OVERLAY-CRASH-EVIDENCE.md"
VERDICTS = LOGS / "lm-crash-verdicts.jsonl"

LM = "http://127.0.0.1:1234"
LOCAL = "http://127.0.0.1:8081"  # llama.cpp unity-csharp-coder

QUESTION = """You are debugging a native crash in a Python OpenGL overlay.

EVIDENCE (measured, not hypothesised):
- Process exit code 0xC0000005 (ACCESS VIOLATION) on 3 of 3 runs. Not a Python
  exception: no traceback, no sys.excepthook, no finally -- the interpreter
  never regained control. Exit code was captured by a parent process.
- Frames before death: 29697, 588, 626. Wall time: 435.6s, 13.6s, 13.6s.
  So it is NOT deterministic: same code, same argv, wildly different lifetime.
- The overlay is a GLFW + PyOpenGL + Dear ImGui loop on a GTX 1660 Ti,
  driver 32.0.16.1714, Windows 11 26200, Python 3.11.
- 3 background threads each call urllib.request.urlopen(..., timeout=1.5) at
  ~60Hz (a frame feed on port 9700, an activity feed on 9626, a field feed).
  faulthandler dumps repeatedly show threads parked in socket readinto.
- A /health HTTP server runs on a 4th thread reading a shared `state` dict.
- The GL thread writes that same `state` dict, and the GL thread also writes
  `state["w"], state["h"]` every frame from glfw.get_framebuffer_size().
- Python-level locking: feeds use a single `self._lock`; `state` is a plain
  dict with NO lock. C extensions in play: PyOpenGL, glfw, numpy, Pillow.

QUESTION: What is MISSING? Name the specific measurement, instrumentation, or
piece of information that would let you distinguish between candidate causes.
Give at most 3 candidates ranked by how well they explain a NON-deterministic
0xC0000005, and for the top one say exactly what to add to confirm it.
Be concrete and brief. No generic advice about "adding error handling".
"""


def _tail(p: pathlib.Path, n: int) -> str:
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except OSError as exc:
        return f"<unreadable: {exc}>"


def build_evidence() -> str:
    parts: list[str] = []
    parts.append("# Overlay native-crash evidence\n")
    parts.append("Generated from live logs. Every figure below was measured.\n")

    parts.append("\n## 1. Exit codes (parent-captured, one JSON line per run)\n")
    parts.append("```json\n" + _tail(LOGS / "overlay-watch.jsonl", 12) + "\n```\n")

    parts.append("\n## 2. Overlay's own exit log (Python-level exit paths)\n")
    parts.append("Only `main() start` appears -- no ESC, no WM_CLOSE, no FATAL, "
                 "no SystemExit. Confirms the death is not a Python exit path.\n")
    parts.append("```\n" + _tail(LOGS / "overlay-exit.log", 20) + "\n```\n")

    parts.append("\n## 3. Service log tail (faulthandler thread dumps)\n")
    parts.append("```\n" + _tail(LOGS / "svc-floating-brain-overlay.log", 45) + "\n```\n")

    src = (ROOT / "ENGINE" / "floating_brain" / "imgui_overlay.py").read_text(encoding="utf-8")

    def grab(pattern: str, before: int = 2, after: int = 26) -> str:
        m = re.search(pattern, src, re.M)
        if not m:
            return f"<pattern not found: {pattern}>"
        lines = src.splitlines()
        i = src[: m.start()].count("\n")
        return "\n".join(lines[max(0, i - before): i + after])

    parts.append("\n## 4. The frame feed thread (blocking urlopen, 1.5s timeout)\n")
    parts.append("```python\n" + grab(r"class FrameFeed", 0, 34) + "\n```\n")

    parts.append("\n## 5. Main GL loop: what touches `state` and GL each frame\n")
    parts.append("```python\n" + grab(r"while not glfw.window_should_close", 0, 40) + "\n```\n")

    parts.append("\n## 6. The /health server (4th thread, reads `state`)\n")
    parts.append("```python\n" + grab(r"def _start_health_server", 0, 30) + "\n```\n")

    parts.append("\n## 7. Driving question\n")
    parts.append(QUESTION)
    return "\n".join(parts)


def _post(base: str, model: str, prompt: str, timeout: float = 180.0) -> dict:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 420,
        "temperature": 0.0,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(base + "/v1/chat/completions", data=body,
                                headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"ok": True, "http": r.status, "body": json.loads(r.read().decode("utf-8"))}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "http": exc.code,
                "body": exc.read().decode("utf-8", "replace")[:600]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "http": None, "body": repr(exc)[:300]}


def _extract(res: dict) -> tuple[str, str]:
    """Return (content, reasoning_content). Never conflates the two."""
    try:
        msg = res["body"]["choices"][0]["message"]
        return (msg.get("content") or "").strip(), (msg.get("reasoning_content") or "").strip()
    except Exception:  # noqa: BLE001
        return "", ""


def list_models() -> list[tuple[str, str]]:
    try:
        with urllib.request.urlopen(LM + "/api/v0/models", timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        return [(m["id"], m.get("state", "?")) for m in data.get("data", [])]
    except Exception:  # noqa: BLE001
        try:
            with urllib.request.urlopen(LM + "/v1/models", timeout=8) as r:
                data = json.loads(r.read().decode("utf-8"))
            return [(m["id"], "?") for m in data.get("data", [])]
        except Exception:  # noqa: BLE001
            return []


def main() -> int:
    pack = build_evidence()
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(pack, encoding="utf-8")
    print(f"evidence pack: {EVIDENCE} ({len(pack):,} chars)")

    targets = [(mid, state, LM) for mid, state in list_models()]
    # The locally-built llama.cpp server is the strongest coder available.
    targets.append(("unity-csharp-coder", "local-llamacpp", LOCAL))

    if VERDICTS.exists():
        VERDICTS.unlink()

    ok = failed = empty = 0
    for model, state, base in targets:
        where = "localhost:8081" if base == LOCAL else "lmstudio:1234"
        print(f"\n--- {model}  [{state}] via {where}", flush=True)
        res = _post(base, model, pack)
        content, reasoning = _extract(res)
        rec = {
            "model": model,
            "state": state,
            "endpoint": where,
            "http": res.get("http"),
            "ok": bool(res.get("ok")),
            "content_chars": len(content),
            "reasoning_chars": len(reasoning),
            "content": content,
            "reasoning": reasoning[:4000],
            "error": None if res.get("ok") else str(res.get("body"))[:400],
        }
        if not res.get("ok"):
            rec["status"] = "load_or_http_failure"
            failed += 1
            print(f"    FAILED http={res.get('http')} {rec['error'][:120]}")
        elif not content and reasoning:
            rec["status"] = "empty_content_reasoning_only"
            empty += 1
            print(f"    REASONING-ONLY ({len(reasoning)} chars, content empty)")
        elif not content:
            rec["status"] = "empty"
            empty += 1
            print("    EMPTY")
        else:
            rec["status"] = "answered"
            ok += 1
            print(f"    ANSWER {len(content)} chars")
        with open(VERDICTS, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    print(f"\nanswered={ok} reasoning_only_or_empty={empty} failed={failed} total={len(targets)}")
    print(f"verdicts: {VERDICTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
