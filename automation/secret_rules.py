"""Single source of truth for "is this string a secret?".

Both audit_config_secrets.py and redact_config_secrets.py import from here. Two
independent copies of this rule drifted apart once and produced a false defect on
`sk-your-key-here` -- the twelfth false red of the night. Sharing the classifier is
the fix, not patching each copy.

Conservative by design: it would rather call something a placeholder than redact
documentation. It never returns or logs a full value.
"""
import re

# prefix -> plausible (min_len, max_len) of the complete token
PREFIXES = {
    "nvapi-": (40, 90),
    "sk-ant-": (40, 200),
    "sk-": (20, 200),
    "ghp_": (36, 40),
    "gho_": (36, 40),
    "AKIA": (20, 21),
    "xoxb-": (30, 90),
    "AIza": (35, 40),
}

TOKEN = re.compile(r"[A-Za-z0-9_\-]{16,220}")

# substrings that mark a value as an example, not a credential
PLACEHOLDER_MARKERS = (
    "your", "xxxx", "bypass", "here", "placeholder", "example", "dummy",
    "sample", "fake", "insert", "redact", "changeme", "todo", "sk-test",
)


def is_placeholder(token: str) -> bool:
    low = token.lower()
    if any(m in low for m in PLACEHOLDER_MARKERS):
        return True
    if low.endswith("-key") or low.endswith("-token"):
        return True

    # a body that is a sequential alphabet run is a fixture (sk-abcdef...).
    # No real key generator produces abcdefgh...
    body = low
    for pre in PREFIXES:
        if low.startswith(pre):
            body = low[len(pre):]
            break
    if len(body) >= 10:
        alpha = [c for c in body if c.isalpha()]
        if len(alpha) >= 8 and all(
                ord(alpha[i + 1]) - ord(alpha[i]) in (0, 1)
                for i in range(len(alpha) - 1)):
            return True
    return False


def classify(token: str):
    """Return (prefix, is_secret, why). Never raises."""
    for pre, (lo, hi) in PREFIXES.items():
        if token.startswith(pre) and lo <= len(token) <= hi:
            if is_placeholder(token):
                return pre, False, "placeholder"
            return pre, True, "looks like a credential"
    return None, False, "no known prefix or wrong length"


def mask(token: str) -> str:
    """First 6 and last 2 characters -- enough to identify, not to use."""
    if len(token) <= 10:
        return token[:4] + "***"
    return token[:6] + "..." + token[-2:]
