"""Triage the 112 'secret-shaped' hits: real credential, or a mention?.

A substring scan for 'sk-' or 'AKIA' matches documentation, variable names, regexes
and placeholder examples. Reporting 112 secrets without triage would be exactly the
kind of false alarm that has burned seven checks tonight.

Classification, strictly evidence-based:
  REAL    : the string looks like a live key (correct prefix + plausible length +
            high entropy) and is not wrapped in quotes-as-example, <angle>, or
            preceded by 'example'/'your'/'xxx'
  MENTION : appears in .md prose, a comment, a variable NAME, or a placeholder
  UNSURE  : everything else -- reported for a human, not silently passed

Never prints a full secret. Shows first 6 and last 2 characters only, which is
enough to identify a key without leaking it into a log.
"""
import os
import re
import sys

ROOT = r"C:\ABRASAX"

# prefix -> (min_len, max_len) of the whole token
PREFIXES = {
    "nvapi-": (40, 90),
    "sk-":    (20, 200),
    "sk-ant-": (40, 200),
    "ghp_":   (36, 40),
    "gho_":   (36, 40),
    "xoxb-":  (30, 90),
    "AKIA":   (20, 21),
    "AIza":   (35, 40),
}

PLACEHOLDER_HINTS = ("example", "your", "xxx", "placeholder", "<", ">", "${",
                     "sk-...", "sk-xxx", "INSERT", "REDACT", "changeme")

# a token is a run of key-ish characters
TOKEN = re.compile(r"[A-Za-z0-9_\-]{16,220}")


def entropy(s):
    from math import log2
    if not s:
        return 0.0
    counts = {}
    for c in s:
        counts[c] = counts.get(c, 0) + 1
    n = len(s)
    return -sum((c / n) * log2(c / n) for c in counts.values())


def mask(tok):
    if len(tok) <= 10:
        return tok[:4] + "***"
    return tok[:6] + "..." + tok[-2:]


def scan():
    tracked = os.popen(f'git -C "{ROOT}" ls-files').read().splitlines()
    real, unsure, mention = [], [], []

    for rel in tracked:
        if not rel.endswith((".py", ".ps1", ".bat", ".json", ".toml", ".md",
                             ".env", ".txt", ".cs", ".cpp", ".h", ".jsonl", ".ini",
                             ".cfg", ".yaml", ".yml", ".sh", ".mjs", ".js", ".ts")):
            continue
        full = os.path.join(ROOT, rel.replace("/", os.sep))
        try:
            if os.path.getsize(full) > 2_000_000:
                continue
            text = open(full, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue

        is_markdown = rel.endswith(".md")
        for line_no, line in enumerate(text.splitlines(), 1):
            for pre in PREFIXES:
                if pre not in line:
                    continue
                for m in TOKEN.finditer(line):
                    tok = m.group(0)
                    if not tok.startswith(pre):
                        continue
                    lo, hi = PREFIXES[pre]
                    if not (lo <= len(tok) <= hi):
                        continue

                    low_line = line.lower()
                    if any(h.lower() in low_line for h in PLACEHOLDER_HINTS):
                        mention.append((rel, line_no, mask(tok), "placeholder hint"))
                        continue

                    def is_fixture(token, path):
                        """A test fixture, not a leak.

                        Two independent signals: it lives under TESTS/, or its body
                        is a sequential alphabet run (abcdefgh...) which no real key
                        generator produces.
                        """
                        if path.startswith("TESTS/") or "/test_" in path:
                            return "test fixture (path)"
                        body = token[len(pre):]
                        if len(body) >= 12:
                            seq = all(
                                ord(body[i + 1]) - ord(body[i]) in (1, 0)
                                for i in range(len(body) - 1)
                                if body[i].isalpha() and body[i + 1].isalpha()
                            )
                            if seq and body[:6] == "abcdef":
                                return "test fixture (sequential alphabet)"
                        return None

                    fixture = is_fixture(tok, rel)
                    if fixture:
                        mention.append((rel, line_no, mask(tok), fixture))
                        continue

                    ent = entropy(tok)
                    if is_markdown:
                        mention.append((rel, line_no, mask(tok), f"markdown prose (entropy {ent:.2f})"))
                        continue
                    if ent >= 3.6:
                        real.append((rel, line_no, mask(tok), f"entropy {ent:.2f}, len {len(tok)}"))
                    else:
                        unsure.append((rel, line_no, mask(tok), f"low entropy {ent:.2f}"))
                    break

    return real, unsure, mention


real, unsure, mention = scan()

print(f"REAL-looking credentials : {len(real)}")
for rel, ln, m, why in real[:20]:
    print(f"  {rel}:{ln}  {m}  ({why})")

print(f"\nUNSURE                   : {len(unsure)}")
for rel, ln, m, why in unsure[:10]:
    print(f"  {rel}:{ln}  {m}  ({why})")

print(f"\nMENTION / placeholder    : {len(mention)}")
for rel, ln, m, why in mention[:10]:
    print(f"  {rel}:{ln}  {m}  ({why})")

print("\nRESULT:", "REAL SECRETS PRESENT" if real else
      ("unsure only" if unsure else "no real secrets"))
sys.exit(1 if real else 0)
