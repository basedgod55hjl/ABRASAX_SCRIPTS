"""Inventory every DLL and GPU kernel binary on the box, by vendor.

Why: the GPU/kernel surface of this project was unknown. 629 DLLs and hundreds
of kernel sources existed with nothing listing them, so "does the AMD path
exist?" and "which kernels are actually built?" could only be answered by hand.

Classification is by filename + containing path, which is how these toolchains
actually name things:
  nvidia  ggml-cuda, cudart, cublas, cudnn, nvml, nvrtc, cuda*, .cubin, .ptx
  amd     hip, rocm, amd_hip, comgr, hsa, migraphx, rocblas, .hsaco
  intel   oneapi, level_zero, sycl
  other   everything else

Outputs:
  DATA/runtime-memory/device_inventory.json   machine-readable, read by the UI
  DOC/reports/DEVICE_INVENTORY.md             human summary

The UI only needs counts, so the JSON carries a `summary` block sized for a HUD
line plus the full list for anyone who needs it.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(r"C:\ABRASAX")
OUT_JSON = ROOT / "DATA" / "runtime-memory" / "device_inventory.json"
OUT_MD = ROOT / "DOC" / "reports" / "DEVICE_INVENTORY.md"

SKIP_DIRS = {"ARCHIVE", ".git", "node_modules", "__pycache__", ".venv_gui",
             "site-packages", ".gradle", "ndk"}
BIN_EXT = {".dll", ".so", ".dylib"}
KERNEL_EXT = {".cubin", ".ptx", ".fatbin", ".hsaco", ".cl", ".cu", ".cuh"}

VENDORS = [
    ("nvidia", re.compile(r"(cuda|cudnn|cublas|cudart|nvml|nvrtc|nvidia|ggml-cuda|tensorrt)", re.I)),
    ("amd", re.compile(r"(hip|rocm|comgr|\bhsa\b|migraphx|rocblas|amd_|miopen|rccl)", re.I)),
    ("intel", re.compile(r"(oneapi|level_zero|sycl|openvino|dpcpp)", re.I)),
]


def classify(name: str, path: str) -> str:
    hay = name + " " + path
    for vendor, rx in VENDORS:
        if rx.search(hay):
            return vendor
    return "other"


def main() -> int:
    t0 = time.time()
    bins: list[dict] = []
    kernels: list[dict] = []
    by_vendor = {"nvidia": 0, "amd": 0, "intel": 0, "other": 0}
    kern_vendor = {"nvidia": 0, "amd": 0, "intel": 0, "other": 0}
    total_bytes = 0

    # os.walk, not rglob: rglob raises FileNotFoundError on the first
    # unreadable directory it meets (this tree has one named `cycle4__.`),
    # which aborted an earlier inventory outright. onerror=None skips them.
    import os as _os
    for dirpath, dirnames, filenames in _os.walk(ROOT, onerror=lambda e: None):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            p = pathlib.Path(dirpath) / fname
            if not p.is_file():
                continue
            ext = p.suffix.lower()
            if ext not in BIN_EXT and ext not in KERNEL_EXT:
                continue
            try:
                size = p.stat().st_size
            except OSError:
                continue
            try:
                rel = str(p.relative_to(ROOT))
            except ValueError:
                continue
            vendor = classify(p.name, rel)
            rec = {"path": rel, "name": p.name, "size": size, "vendor": vendor}
            if ext in KERNEL_EXT:
                kernels.append(rec)
                kern_vendor[vendor] += 1
            else:
                bins.append(rec)
                by_vendor[vendor] += 1
            total_bytes += size

    # group kernels by directory so it is obvious what is built vs merely source
    kern_dirs: dict[str, int] = {}
    for k in kernels:
        kern_dirs[str(pathlib.Path(k["path"]).parent)] = \
            kern_dirs.get(str(pathlib.Path(k["path"]).parent), 0) + 1

    summary = {
        "dlls_total": len(bins),
        "kernels_total": len(kernels),
        "dll_by_vendor": by_vendor,
        "kernel_by_vendor": kern_vendor,
        "total_mb": round(total_bytes / 1048576.0, 1),
        "kernels_built": sum(1 for k in kernels if k["path"].lower().endswith((".cubin", ".ptx", ".fatbin", ".hsaco"))),
        "kernels_source": sum(1 for k in kernels if k["path"].lower().endswith((".cl", ".cu", ".cuh"))),
    }
    data = {"ts": time.time(), "root": str(ROOT), "summary": summary,
            "kernel_dirs": dict(sorted(kern_dirs.items(), key=lambda kv: -kv[1])[:20]),
            "kernels": kernels, "dlls": bins}
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, indent=1), encoding="utf-8")

    # human summary: only the parts that need judgement
    lines = ["# Device inventory", "",
             f"Generated {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} "
             f"from `{ROOT}` in {time.time() - t0:.1f}s", "",
             "## Summary", "",
             f"- DLL/SO/dylib: **{summary['dlls_total']}** "
             f"(nvidia {by_vendor['nvidia']}, amd {by_vendor['amd']}, "
             f"intel {by_vendor['intel']}, other {by_vendor['other']})",
             f"- Kernels: **{summary['kernels_total']}** "
             f"({summary['kernels_built']} built artefacts, "
             f"{summary['kernels_source']} source files)",
             f"- Kernel vendors: nvidia {kern_vendor['nvidia']}, amd {kern_vendor['amd']}",
             f"- Total size: {summary['total_mb']} MB", "",
             "## Kernel directories", ""]
    for d, n in list(data["kernel_dirs"].items())[:12]:
        lines.append(f"- `{d}` — {n}")
    lines += ["", "## NVIDIA DLLs", ""]
    for b in [x for x in bins if x["vendor"] == "nvidia"][:25]:
        lines.append(f"- `{b['name']}` ({b['size'] // 1024} KB) — {b['path']}")
    lines += ["", "## AMD DLLs / libraries", ""]
    amd = [x for x in bins if x["vendor"] == "amd"]
    lines += [f"- `{b['name']}` — {b['path']}" for b in amd[:25]] or ["- none found"]
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"dlls {summary['dlls_total']}  kernels {summary['kernels_total']}  "
          f"({summary['kernels_built']} built / {summary['kernels_source']} source)  "
          f"{summary['total_mb']} MB")
    print(f"  nvidia dll {by_vendor['nvidia']}  amd dll {by_vendor['amd']}  "
          f"intel {by_vendor['intel']}  other {by_vendor['other']}")
    print(f"  -> {OUT_JSON}")
    print(f"  -> {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
