"""_probe_buildloop_warm.py - is the warm ping broken in code, or only in the old process?"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abrasax import build_loop as B  # noqa: E402


def main() -> int:
    result = B._warm()
    print("warm:", result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
