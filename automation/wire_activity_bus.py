"""Replace the stubbed activity sections in abrasax/brain.py with live ones.

Fails loudly if the anchor is absent or ambiguous -- a silent no-op here would
leave the overlay drawing an empty SYSTEM panel and nobody would notice.
"""
from __future__ import annotations

import sys
from pathlib import Path

P = Path(r"C:\ABRASAX\abrasax\brain.py")
lines = P.read_text(encoding="utf-8").splitlines()

start = None
for i, ln in enumerate(lines):
    if ln.strip() == '"transformer": {},':
        start = i
        break
if start is None:
    sys.exit("ANCHOR 'transformer: {}' not found -- refusing to guess")
end = start
while end < len(lines) and lines[end].strip() not in ('"panels": {},', '"nodes": nodes,'):
    end += 1
if end >= len(lines):
    sys.exit("END anchor not found")
print("replacing lines", start + 1, "..", end, ":")
for ln in lines[start:end]:
    print("  -", ln)

replacement = [
    '        # Live sections come from the ActivityBus contract module. These were',
    '        # hardcoded empty dicts -- a silent stub: imgui_overlay.panel_content()',
    '        # reads act["system"] for the SYSTEM panel and got nothing to draw.',
    '        **live,',
    '        "tools": {**live.get("tools", {}),',
    '                  "count": live.get("tools", {}).get("count") or edges},',
]
out = lines[:start] + replacement + lines[end:]

# `live` must be bound before the return literal.
if "live = " not in "\n".join(out):
    helper = [
        '',
        'def _live_sections() -> dict:',
        '    """ActivityBus snapshot; never raises, never blocks the HTTP thread."""',
        '    try:',
        '        from ENGINE.floating_brain.activity_bus import ActivityBus',
        '    except ImportError:',
        '        pass',
        '    try:',
        '        import importlib.util as _ilu',
        '        _p = ROOT / "ENGINE" / "floating_brain" / "activity_bus.py"',
        '        if not _p.exists():',
        '            return {}',
        '        _s = _ilu.spec_from_file_location("abx_activity_bus", _p)',
        '        _m = _ilu.module_from_spec(_s)',
        '        _s.loader.exec_module(_m)  # type: ignore[union-attr]',
        '        bus = _m.ActivityBus()',
        '        snap = bus.snapshot(include_live=True)',
        '        snap.pop("panels", None)  # panels state is owned by panels.py',
        '        return snap if isinstance(snap, dict) else {}',
        '    except Exception:',
        '        return {}',
        '',
    ]
    # insert the helper just above def activity()
    ai = next(i for i, ln in enumerate(out) if ln.startswith("def activity()"))
    out = out[:ai] + helper + out[ai:]
    ri = next(i for i, ln in enumerate(out) if ln.strip() == "**live,")
    out = out[:ri] + ['        ' + 'live = _live_sections()'] + out[ri:]

P.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"wrote {P} ({P.stat().st_size} B, {len(out)} lines)")
