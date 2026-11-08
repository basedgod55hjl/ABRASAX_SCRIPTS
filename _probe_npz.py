"""Probe the two synaptic checkpoints: is either a readable npz? (read-only)"""
from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\abrasax")
for rel in ("tools/source-tools/data/state/synaptic_brain.npz",
            "DATA/runtime-memory/synaptic_field.npz"):
    p = ROOT / rel
    print(rel, "size", p.stat().st_size if p.exists() else "ABSENT")
    print("  zip:", zipfile.is_zipfile(p))
    if zipfile.is_zipfile(p):
        with np.load(p, allow_pickle=False) as d:
            print("  files:", sorted(d.files))
            print("  dtypes:", {k: str(d[k].dtype) for k in d.files})
    else:
        head = p.read_bytes()[:16]
        print("  head:", head.hex())
