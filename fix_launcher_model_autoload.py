#!/usr/bin/env python3
"""fix_launcher_model_autoload.py -- idempotent patch for start_abrasax_stack.ps1

Defect (measured 2026-11-01 18:18Z, cold boot on this host):
    $want = @('nvidia/nemotron-3-nano-4b', 'liquid/lfm2.5-1.2b', 'text-embedding-nomic-embed-text-v1.5')
    ... (& $lms load $m ...)

'nvidia/nemotron-3-nano-4b' is not installed here (`lms ls` lists 9 keys, none of them
that one).  `lms load` with an unmatched key does not fail -- it opens its INTERACTIVE
model picker and waits on stdin.  With stdout piped through ForEach-Object the picker
never gets a terminal, spams its ANSI menu into LOGS/stack-start.log, and the launcher
never reaches the control-plane section: the whole stack stays down while the log looks
busy.

Rule now encoded:
  * a model key is a REQUIREMENT, checked against `lms ls` before it is requested;
  * `-y` is passed so a stray prompt can never block the boot;
  * the requirement list is overridable per host with ABRASAX_REQUIRED_MODELS.

Structural, not line-guessed: the `foreach` is brace-matched, an earlier application is
removed by its markers (plus the orphan '}' the first version of this patch left behind),
and "already applied" is decided by re-patching and comparing, so a second run is a no-op.

Run: python SCRIPTS/fix_launcher_model_autoload.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "SCRIPTS" / "launchers" / "start_abrasax_stack.ps1"

BEGIN = "        # ---- model autoload (patched: requirements checked against `lms ls`) ----"
END = "        # ---- end model autoload ----"

BLOCK = [
    BEGIN,
    "        $want = @('liquid/lfm2.5-1.2b', 'text-embedding-nomic-embed-text-v1.5')",
    "        if ($env:ABRASAX_REQUIRED_MODELS) {",
    "            $want = $env:ABRASAX_REQUIRED_MODELS -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ }",
    "        }",
    "        $psOut = ''",
    "        try { $psOut = (& $lms ps 2>$null | Out-String) } catch { Log \"lms ps failed: $($_.Exception.Message)\" }",
    "        $lsOut = ''",
    "        try { $lsOut = (& $lms ls 2>$null | Out-String) } catch { Log \"lms ls failed: $($_.Exception.Message)\" }",
    "        foreach ($m in $want) {",
    "            if ($psOut -match [regex]::Escape($m)) { Log \"model resident: $m\"; continue }",
    "            if ($lsOut -and -not ($lsOut -match [regex]::Escape($m))) { Log \"model not installed, skipped: $m\"; continue }",
    "            Log \"loading model: $m\"",
    "            try { (& $lms load $m --gpu max -y 2>&1 | ForEach-Object { Log \"  lms: $_\" }) } catch { Log \"  load failed: $($_.Exception.Message)\" }",
    "        }",
    END,
]

LEGACY_NEEDLES = ("nvidia/nemotron-3-nano-4b", "(& $lms load $m 2>&1")


def strip_previous(lines: list[str]) -> tuple[list[str], int | None]:
    """Remove an earlier application, including the orphan '}' that the first
    (line-guessed) version of this patch left after the end marker.

    Returns (remaining_lines, index_where_the_removed_block_started).
    """
    if not any(ln.strip() == BEGIN.strip() for ln in lines):
        return lines, None
    out: list[str] = []
    pos: int | None = None
    skipping = False
    orphan_ok = False
    for ln in lines:
        if skipping:
            if ln.strip() == END.strip():
                skipping = False
                orphan_ok = True
            continue
        if orphan_ok:
            orphan_ok = False
            if ln.strip() == "}":
                continue
        if ln.strip() == BEGIN.strip():
            skipping = True
            pos = len(out)
            continue
        out.append(ln)
    return out, pos


def find_foreach_end(lines: list[str], start: int) -> int:
    """Index of the line closing the `foreach ($m in $want) {` opened at/after start."""
    i = start
    while "foreach ($m in $want)" not in lines[i]:
        i += 1
        if i - start > 4:
            raise SystemExit("could not locate the foreach in the model-autoload block")
    depth = 0
    while True:
        depth += lines[i].count("{") - lines[i].count("}")
        if depth <= 0:
            return i
        i += 1
        if i - start > 40:
            raise SystemExit("unbalanced braces in the model-autoload block")


def patch(text: str) -> str:
    lines, pos = strip_previous(text.replace("\r\n", "\n").split("\n"))
    start = next((i for i, ln in enumerate(lines) if "$want = @(" in ln), None)
    if start is None:
        if pos is None:
            raise SystemExit("no $want block and no previous patch marker: refusing to guess")
        return "\n".join(lines[:pos] + BLOCK + lines[pos:])
    end = find_foreach_end(lines, start)
    return "\n".join(lines[:start] + BLOCK + lines[end + 1:])


def main() -> int:
    if not TARGET.exists():
        print(f"MISSING {TARGET}")
        return 2
    text = TARGET.read_text(encoding="utf-8-sig")
    new = patch(text)
    applied = new == text
    legacy = [n for n in LEGACY_NEEDLES if n in text]

    if "--check" in sys.argv:
        ok = applied and not legacy
        print(("PASS " if ok else "FAIL ") + f"{TARGET.name}: patched={applied} legacy_needles={legacy}")
        return 0 if ok else 1

    if applied and not legacy:
        print(f"already patched: {TARGET}")
        return 0

    backup = TARGET.with_suffix(TARGET.suffix + ".bak-modelautoload")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
    TARGET.write_text(new, encoding="utf-8")
    print(f"patched {TARGET} (backup {backup.name}); removed legacy needles: {legacy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
