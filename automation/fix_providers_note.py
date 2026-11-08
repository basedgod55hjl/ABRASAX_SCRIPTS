"""Move the free-text `jit_load_note` out of the `models` map in providers.json.

It is a *note*, but it sits among aliases, so any consumer that iterates
`models` treats it as a model id:

    gemma       -> gemma-4-e4b-agentic   (real alias, model not in LM Studio now)
    jit_load_note -> "Only three models are intentionally resident: ..."  (JSON text!)

llm_router resolves by named key only (models.get(model)), so nothing is broken
today -- this is preventing a future mis-fire, and keeping the note where a
human and a machine both read it correctly (under a `notes` key).

Also records the Gemma alias's real state instead of leaving a dangling id.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

P = Path(r"C:\ABRASAX\CONFIG\llm\providers.json")
raw = P.read_text(encoding="utf-8")
data = json.loads(raw)

lm = data["providers"]["lmstudio"]
models = lm.get("models", {})
note = models.pop("jit_load_note", None)
if note is None:
    sys.exit("jit_load_note not found -- already clean?")

bak = P.with_suffix(P.suffix + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M"))
shutil.copy2(P, bak)

notes = lm.setdefault("notes", {})
if isinstance(notes, dict):
    notes["jit_load"] = note
else:  # defensive: never clobber a non-dict
    lm["notes"] = {"jit_load": note}

# The alias points at a model the live server does not list; say so, don't guess.
if models.get("gemma") and not any(
    str(v) == models["gemma"] for k, v in models.items() if k != "gemma"
):
    lm.setdefault("warnings", {})["gemma"] = (
        f"alias target {models['gemma']!r} was not listed by the live LM Studio "
        f":1234 /v1/models at audit time; it will JIT-load or fail startup"
    )

P.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")

# verify round-trip
back = json.loads(P.read_text(encoding="utf-8"))
m2 = back["providers"]["lmstudio"]["models"]
assert "jit_load_note" not in m2, "note still in models"
assert "jit_load" in back["providers"]["lmstudio"]["notes"], "note not relocated"
bad = [k for k, v in m2.items() if not isinstance(v, str) or len(v) > 80]
print(f"backup      : {bak.name}")
print(f"models keys : {len(m2)} (all short strings: {not bad})")
print(f"note moved  : notes.jit_load ({len(back['providers']['lmstudio']['notes']['jit_load'])} chars)")
print(f"warnings    : {list(back['providers']['lmstudio'].get('warnings', {}))}")
