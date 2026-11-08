"""Fix the f-string SyntaxError in strip_leaked_key.py by rewriting the file cleanly.

Python 3.11 forbids a backslash inside an f-string expression part:
    f"from {os.path.relpath(PATH, r'C:\\ABRASAX')}\n"
Raised: SyntaxError: f-string expression part cannot include a backslash.

Rather than patch a fragile string, compute the relative path into a variable
first. Also drops the unused ROOT reference confusion.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\strip_leaked_key.py"

CLEAN = r'''"""Remove the hardcoded DeepSeek key from lm_client.ts WITHOUT rewriting history.

FINDING (section 3 audit): CORE/OSIRISBLXCK-CORE/src/lm_client.ts:11 carried a real
API key in plaintext:

    const DEEPSEEK_KEY = process.env.DEEPSEEK_API_KEY || "sk-33e0...dc53";

It is in commit 83534d9, which IS on origin/main (verified with
`git branch -r --contains 83534d9` -> origin/main). Live exposure, not hypothetical.

DOES:      strip the literal, keep the env-var path, preserve the key in a
           gitignored vault file for the operator.
DOES NOT:  rewrite git history. Rewriting 32 commits and force-pushing would
           destroy other clones, is itself destructive, and does not un-publish
           what GitHub already has.

The only real remediation for a pushed key is ROTATION at the provider.
Idempotent.
"""
import os
import re
import shutil
import sys
import time

ROOT = r"C:\ABRASAX"
PATH = os.path.join(ROOT, "CORE", "OSIRISBLXCK-CORE", "src", "lm_client.ts")
VAULT = os.path.join(ROOT, "_VAULT", "secrets", "extracted-20261018.txt")

PATTERN = re.compile(r'"(sk-[0-9a-f]{32})"')

if not os.path.exists(PATH):
    print("FAIL: not found: " + PATH)
    sys.exit(1)

src = open(PATH, encoding="utf-8").read()
found = PATTERN.findall(src)

if not found:
    print("ALREADY-PATCHED: no hardcoded key literal remains")
    sys.exit(0)

print("found %d hardcoded key literal(s)" % len(found))

# --- preserve the value outside git ---------------------------------------
vault_dir = os.path.dirname(VAULT)
if not os.path.isdir(vault_dir):
    os.makedirs(vault_dir, exist_ok=True)

stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
rel = os.path.relpath(PATH, ROOT)
with open(VAULT, "a", encoding="utf-8") as f:
    f.write("# extracted " + stamp + " from " + rel + "\n")
    for k in found:
        f.write("DEEPSEEK_API_KEY=" + k + "\n")
print("preserved to " + VAULT)

# --- strip from the source ------------------------------------------------
backup = PATH + ".bak-" + time.strftime("%Y%m%d-%H%M")
shutil.copy2(PATH, backup)

new = PATTERN.sub('""', src)
marker = 'const DEEPSEEK_KEY = process.env.DEEPSEEK_API_KEY || "";'
comment = (
    "// SECURITY: a key was hardcoded here and is in git history (commit 83534d9,\n"
    "// pushed to origin/main). Rotate it at the provider; supply it via the\n"
    "// environment only.\n"
)
new = new.replace(marker, comment + marker)

open(PATH, "w", encoding="utf-8", newline="").write(new)

print("stripped literal from " + os.path.basename(PATH))
print("backup: " + os.path.basename(backup))
print()
print("REMAINING WORK (cannot be automated):")
print("  1. ROTATE the key at platform.deepseek.com - the old one is public forever")
print("  2. set DEEPSEEK_API_KEY in the environment")
print("  3. optionally rewrite history + force-push (destructive; operator's call)")
sys.exit(0)
'''

open(PATH, "w", encoding="utf-8", newline="").write(CLEAN)
print("rewrote strip_leaked_key.py cleanly")
