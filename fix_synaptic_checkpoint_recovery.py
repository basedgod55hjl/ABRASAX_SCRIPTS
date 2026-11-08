"""fix_synaptic_checkpoint_recovery.py - stop synaptic-brain from crash-looping on a bad weights file.

MEASURED 2026-11-01T17:14:21Z (supervisor-ledger start event, pid 5496):

    tools/source-tools/data/state/synaptic_brain.npz
      size   345034
      head   00000000000000000000000000000000   <- not a zip, not a pickle
    SynapticField.load -> np.load(allow_pickle=False)
      ValueError: This file contains pickled (object) data.

The checkpoint had been zero-filled (interrupted write / preallocated file), so
``--resume`` could never come up: every supervisor restart re-ran the same load
and the service died in ~0.2 s, while a *valid* checkpoint of the same schema sat
at DATA/runtime-memory/synaptic_field.npz (zip, 12 arrays, 11:32Z).

Two defects, both fixed here:

1. ``SynapticField.load`` let numpy's message describe a disk fault as a pickle
   problem. It now validates the file is an npz and names the real condition
   (``CheckpointError``, a ValueError subclass, so existing handlers still work).
2. The server had no recovery path: ``--resume`` either loaded or died. It now
   quarantines the unreadable file (never deletes evidence), re-seeds from a
   verified alternate checkpoint when one exists, and starts fresh otherwise -
   loudly, in the log, with the reason.

Idempotent: re-running changes nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\abrasax")
BRAIN = ROOT / "tools" / "source-tools" / "brains" / "abraxas_synaptic_brain.py"
SERVER = ROOT / "tools" / "source-tools" / "brains" / "abraxas_synaptic_server.py"

OLD_LOAD = '''    @classmethod
    def load(cls, path) -> "SynapticField":
        d = np.load(path, allow_pickle=False)
        meta = json.loads(bytes(d["meta"]).decode())'''

NEW_LOAD = '''    @classmethod
    def load(cls, path) -> "SynapticField":
        path = Path(path)
        # A zero-filled or truncated checkpoint makes np.load raise
        # "This file contains pickled (object) data", which describes a disk
        # fault as a pickle/security problem. Measured 2026-11-01: a 345,034-byte
        # all-zero synaptic_brain.npz produced exactly that, and the service
        # crash-looped on --resume. Say what is actually wrong, and say which
        # file, so a recovery path can act on it.
        if not zipfile.is_zipfile(path):
            head = ""
            try:
                with open(path, "rb") as fh:
                    head = fh.read(16).hex()
            except OSError:
                head = "unreadable"
            size = path.stat().st_size if path.exists() else 0
            raise CheckpointError(
                f"{path} is not an npz checkpoint (size={size}, head={head or 'empty'})")
        d = np.load(path, allow_pickle=False)
        missing = [k for k in CHECKPOINT_FIELDS if k not in d.files]
        if missing:
            raise CheckpointError(f"{path} is missing checkpoint fields {missing}")
        meta = json.loads(bytes(d["meta"]).decode())'''

CHECKPOINT_ERROR = '''class CheckpointError(ValueError):
    """A weights file that exists but cannot be trusted as a checkpoint."""


# Every npz written by SynapticField.save(); anything less is a partial write.
CHECKPOINT_FIELDS = ("pre", "post", "mag", "sign", "reciprocal", "state",
                     "memory", "signal", "steps", "meta")


'''

OLD_IMPORT = '''import argparse
import hashlib
import json
import sys
from pathlib import Path
'''
NEW_IMPORT = '''import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
'''

OLD_SERVER_LOAD = '''    f = sb.SynapticField.load(WEIGHTS) if (a.resume and WEIGHTS.exists()) else sb.SynapticField(size=a.size, seed=a.seed)'''
NEW_SERVER_LOAD = '''    if a.resume:
        f, how = load_checkpoint(WEIGHTS, size=a.size, seed=a.seed)
        print(f"[synaptic] weights {how}")
    else:
        f = sb.SynapticField(size=a.size, seed=a.seed)'''

OLD_RUN_ONCE = '''    if resume and WEIGHTS.exists():
        f = sb.SynapticField.load(WEIGHTS)
        print(f"resumed from {WEIGHTS} at step {f.steps}")
    else:'''
NEW_RUN_ONCE = '''    if resume and WEIGHTS.exists():
        f, how = load_checkpoint(WEIGHTS, size=size, seed=seed)
        print(f"weights {how} at step {f.steps}")
    else:'''

RECOVERY = '''
# ---------------------------------------------------------------------------
# checkpoint recovery: a bad file must not be able to crash-loop the service
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[3]
# A verified second copy of the same schema (see _probe_npz.py, 2026-11-01):
# the runtime brain writes it, and it survived when the service copy did not.
ALT_WEIGHTS = Path(os.environ.get(
    "ABRASAX_SYNAPTIC_ALT",
    REPO / "DATA" / "runtime-memory" / "synaptic_field.npz"))


def quarantine(path: Path) -> Path:
    """Move an unreadable checkpoint aside; never destroy the evidence."""
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    dest = path.with_name(f"{path.name}.corrupt-{stamp}")
    n = 1
    while dest.exists():
        dest = path.with_name(f"{path.name}.corrupt-{stamp}-{n}")
        n += 1
    path.replace(dest)
    return dest


def load_checkpoint(path: Path = WEIGHTS, *, size: int = 64, seed: int = 17,
                    fallbacks: tuple[Path, ...] = (ALT_WEIGHTS,),
                    ) -> tuple["sb.SynapticField", str]:
    """Resume if the checkpoint is readable, else recover without dying.

    Returns ``(field, how)`` where ``how`` is one of
      ``resumed:<path>``      the requested file loaded
      ``fresh``               nothing existed (first run)
      ``recovered:<path>``    requested file bad; a verified fallback loaded
      ``fresh-after-quarantine:<dest>``  nothing usable; started at step 0
    """
    path = Path(path)
    if not path.exists():
        return sb.SynapticField(size=size, seed=seed), "fresh"
    try:
        return sb.SynapticField.load(path), f"resumed:{path}"
    except Exception as exc:  # noqa: BLE001 - any unreadable file is the same case
        print(f"[synaptic] WARNING: {path} unusable: {type(exc).__name__}: {exc}")
        dest = quarantine(path)
        print(f"[synaptic] quarantined -> {dest}")
        for alt in fallbacks:
            alt = Path(alt)
            if not alt.exists() or alt == path:
                continue
            try:
                f = sb.SynapticField.load(alt)
            except Exception as alt_exc:  # noqa: BLE001
                print(f"[synaptic] fallback {alt} unusable too: "
                      f"{type(alt_exc).__name__}: {alt_exc}")
                continue
            f.save(path)  # re-seed the canonical path so the next start is plain
            return f, f"recovered:{alt}"
        return sb.SynapticField(size=size, seed=seed), f"fresh-after-quarantine:{dest}"

'''

OLD_HEADER = '''ROOT = Path(__file__).resolve().parents[1]'''
NEW_HEADER = '''import os  # noqa: E402 - keep the import block above byte-stable

ROOT = Path(__file__).resolve().parents[1]'''


def patch(path: Path, pairs: list[tuple[str, str]], anchor: str | None = None,
          insert: str | None = None) -> bool:
    src = path.read_text(encoding="utf-8")
    before = src
    for old, new in pairs:
        if new in src and old not in src:
            continue  # already applied
        if src.count(old) != 1:
            raise SystemExit(f"{path}: anchor not unique ({src.count(old)}x):\n{old[:120]}")
        src = src.replace(old, new)
    if anchor and insert and insert.strip() not in src:
        if src.count(anchor) != 1:
            raise SystemExit(f"{path}: insertion anchor not unique")
        src = src.replace(anchor, anchor + insert)
    if src != before:
        path.write_text(src, encoding="utf-8", newline="")
        return True
    return False


def main() -> int:
    changed = []
    if patch(BRAIN, [(OLD_IMPORT, NEW_IMPORT), (OLD_LOAD, NEW_LOAD)],
             anchor="PHI, KAPPA, S2 = 1.618033988749895, 0.618033988749895, 0.01\n",
             insert="\n" + CHECKPOINT_ERROR):
        changed.append(BRAIN)
    if patch(SERVER, [(OLD_SERVER_LOAD, NEW_SERVER_LOAD),
                      (OLD_RUN_ONCE, NEW_RUN_ONCE),
                      (OLD_HEADER, NEW_HEADER)],
             anchor='LOG = DATA / "logs" / "synaptic_brain.jsonl"\n',
             insert=RECOVERY):
        changed.append(SERVER)
    for p in changed:
        print("patched", p)
    if not changed:
        print("already applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
