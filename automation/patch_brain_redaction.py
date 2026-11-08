"""Add credential redaction + a secret audit section to the UI brain builder.

The brain indexes 449 skills; at least seven of them embed live-looking tokens
in their front matter (github_pat_*, sk-*, hf_*). Feeding skill descriptions to
an agent must not be a credential exfiltration path, so descriptions are
redacted *at build time* and the count of redacted skills is published as a
metric rather than silently scrubbed.

Idempotent: refuses to double-apply.
"""
from __future__ import annotations

import sys
from pathlib import Path

P = Path(r"C:\ABRASAX\SCRIPTS\automation\build_ui_brain.py")
src = P.read_text(encoding="utf-8")

if "REDACT_RX" in src:
    sys.exit("already patched (REDACT_RX present) -- refusing to double-apply")

# 1. redaction helper, inserted after PENALTY_RX
anchor = 'PENALTY_RX = re.compile(r"\\b(deprecated|stub|placeholder|unused)\\b", re.I)'
if anchor not in src:
    sys.exit(f"anchor not found: {anchor!r}")
helper = anchor + '''

# Credentials must never ride along with a skill description into an agent
# prompt. Redact at build time and count it.
REDACT_RX = re.compile(
    r"github_pat_[A-Za-z0-9_]{20,}"
    r"|gh[pousr]_[A-Za-z0-9]{30,}"
    r"|sk-[A-Za-z0-9\\-]{20,}"
    r"|hf_[A-Za-z0-9]{24,}"
    r"|xox[baprs]-[A-Za-z0-9\\-]{10,}"
    r"|[A-Fa-f0-9]{32,}"
)


def redact(text: str) -> tuple[str, int]:
    return REDACT_RX.subn("[REDACTED]", text)
'''
src = src.replace(anchor, helper, 1)

# 2. apply redaction where descriptions are captured in classify()
old_desc = '    desc = re.sub(r"\\s+", " ", fm.get("description") or "")[:300]'
if old_desc not in src:
    sys.exit("classify() description line not found")
new_desc = ('    raw_desc = re.sub(r"\\s+", " ", fm.get("description") or "")[:300]\n'
            '    desc, n_redacted = redact(raw_desc)')
src = src.replace(old_desc, new_desc, 1)

# 3. record the flag on the skill record
old_rec = '        "description": desc,'
if old_rec not in src:
    sys.exit("record description line not found")
src = src.replace(old_rec, '        "description": desc,\n        "redacted": n_redacted,', 1)

# 4. publish the audit metric
old_meta = '    brain["digest"] = hashlib.sha256('
if old_meta not in src:
    sys.exit("digest anchor not found")
src = src.replace(
    old_meta,
    '    brain["security"] = {\n'
    '        "redaction_rule": "github_pat_/gh?_/sk-/hf_/xox/32+hex -> [REDACTED]",\n'
    '        "skills_with_redactions": sum(1 for s in merged if s.get("redacted")),\n'
    '        "total_redactions": sum(s.get("redacted", 0) for s in merged),\n'
    '    }\n'
    + old_meta,
    1,
)

P.write_text(src, encoding="utf-8")
print(f"patched {P} ({len(src)} chars)")
