"""Teach the secret triage that test fixtures are not leaks.

After stripping the real key, triage_secrets.py still reports 4 'REAL-looking'
credentials, but three are fixtures:

    TESTS/python/test_memory.py:92   sk-abcdefghijklmnopqrstuvwxyz012345
    TESTS/python/test_memory.py:95   (assert it is redacted)
    TESTS/python/test_memory.py:208  sk-abcdefghijklmnopqrstuvwxyz0123456789

Those are deliberately fake: the alphabet is sequential (abcdef...), and the file
is a test for the REDACTION code. Reporting them as leaks would keep the audit red
forever and make real findings easier to miss.

Rule: a token whose body is a strictly increasing alphabet run, or which lives in
TESTS/, is a fixture. Everything else still goes through entropy scoring.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\triage_secrets.py"
src = open(PATH, encoding="utf-8").read()

if "is_fixture" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''                    ent = entropy(tok)
                    if is_markdown:'''

NEW = '''                    def is_fixture(token, path):
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
                    if is_markdown:'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: entropy block")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: test fixtures excluded from REAL classification")
