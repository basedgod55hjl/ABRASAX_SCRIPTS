"""scripts/drop_rebuild_stage.py — remove the redundant ABRASAX-REBUILD stage copy.

The stage copy is a duplicate of the canonical tree (source == "."). It is not a
build product, it carries 344 .bak files, and it is 97% of the stage size.

Windows MAX_PATH blocks a plain recursive delete on deep vendored paths
(.../website/i18n/zh-Hans/.../skills/bundled/autonomous-ai-agents/*.md), so this
uses the \\\\?\\ extended-length prefix and retries with read-only attributes
cleared. It then re-measures the stage and reports what actually happened.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TARGET = Path(r"C:\Users\lucar\abrasax-build\stage\ABRASAX-REBUILD")
STAGE = TARGET.parent


def _long(p: Path) -> str:
    s = str(p)
    return s if s.startswith("\\\\?\\") else "\\\\?\\" + s


def _clear_readonly(root: Path) -> int:
    import os
    import stat

    cleared = 0
    for dirpath, _dirnames, filenames in os.walk(_long(root)):
        for name in filenames:
            fp = os.path.join(dirpath, name)
            try:
                os.chmod(fp, stat.S_IWRITE)
                cleared += 1
            except OSError:
                pass
    return cleared


def main() -> int:
    if not TARGET.exists():
        sys.stdout.write("already gone\n")
        return 0
    before = sum(p.stat().st_size for p in TARGET.rglob("*") if p.is_file()) if TARGET.exists() else 0
    _clear_readonly(TARGET)
    shutil.rmtree(_long(TARGET), ignore_errors=False)
    gone = not TARGET.exists()

    files = [p for p in STAGE.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    dirs = sorted(p.name for p in STAGE.iterdir() if p.is_dir())
    sys.stdout.write(f"removed={gone} freed_mb={before/1e6:.2f}\n")
    sys.stdout.write(f"stage_now: {len(files)} files {total/1e6:.2f} MB in {len(dirs)} dirs\n")
    for d in dirs:
        sys.stdout.write(f"  {d}\n")
    return 0 if gone else 1


if __name__ == "__main__":
    raise SystemExit(main())
