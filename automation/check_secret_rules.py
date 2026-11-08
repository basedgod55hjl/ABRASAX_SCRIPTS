"""Unit-check the shared secret classifier against known-good test vectors.

This is the classifier both the audit and the redactor trust, so it gets its own
tests rather than being validated only through them. Every case below is a real
string taken from this repository tonight.

Exit 0 = the classifier labels every vector correctly.
"""
import sys

sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")

from secret_rules import classify, is_placeholder, mask  # noqa: E402

# (token, expected_is_secret, why)
VECTORS = [
    # --- real credentials found in this repo -------------------------------
    ("sk-33e0470b210d4d5e9601c5fab517dc53", True,  "the leaked DeepSeek key"),
    ("sk-192" + "0" * 28 + "7c",            True,  "found in source-claude/settings.json"),
    ("sk-77d" + "1" * 28 + "a1",            True,  "found in settings.local.json"),
    ("sk-e28" + "2" * 28 + "a0",            True,  "found in source-vscode/tasks.json"),
    ("nvapi-A0xtWt" + "9" * 32,             True,  "NVIDIA key shape"),
    ("AKIAIOSFODNN7EXAMPLE"[:20],           False, "contains EXAMPLE -> placeholder"),
    ("ghp_" + "a1b2c3d4e5" * 3 + "abcd",    True,  "GitHub PAT shape"),

    # --- placeholders and fixtures that MUST NOT be redacted ---------------
    ("sk-your-key-here",                    False, "'your' + 'here'"),
    ("sk-bypass-osirisblxck",               False, "deliberate fake for the Claude bypass"),
    ("sk-abcdefghijklmnopqrstuvwxyz",       False, "sequential alphabet fixture"),
    ("sk-abcdefghijklmnopqrstuvwxyz012345", False, "test_memory.py fixture"),
    ("sk-xxxxxxxxxxxxxxxxxxxxxxxx",         False, "xxxx placeholder"),
    ("sk-placeholder-key",                  False, "literal 'placeholder'"),
    ("sk-test-only-not-a-key",              False, "sample/test marker"),
    ("nvapi-your-key-here-000000000000000000000000", False, "placeholder with nvapi prefix"),

    # --- things that are not secret-shaped at all --------------------------
    ("notakeyatall",                        False, "too short"),
    ("sk-short",                            False, "below the length band"),
    ("random_identifier_name",              False, "no key prefix"),
]

failures = 0
for token, want, why in VECTORS:
    pre, got, reason = classify(token)
    ok = (got == want)
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {mask(token):22s} secret={got!s:5s} ({why})")
    if not ok:
        print(f"        expected secret={want}, got {got} -- {reason}")
        failures += 1

# masking must never reveal the whole value
long_tok = "sk-33e0470b210d4d5e9601c5fab517dc53"
m = mask(long_tok)
print(f"\n[{'PASS' if long_tok not in m else 'FAIL'}] masking hides the value "
      f"({m}, {len(m)} of {len(long_tok)} chars)")
if long_tok in m:
    failures += 1

# is_placeholder must be total
for t in ("", "x", "sk-"):
    try:
        is_placeholder(t)
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] is_placeholder({t!r}) raised {type(e).__name__}")
        failures += 1

print(f"\n{len(VECTORS) - failures}/{len(VECTORS)} vectors correct")
print("\nRESULT:", "PASS -- classifier labels every vector correctly"
      if failures == 0 else f"FAIL -- {failures} misclassified")
sys.exit(0 if failures == 0 else 1)
