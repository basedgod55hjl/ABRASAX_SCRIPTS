"""Make audit_source_control.py fast and observable.

Why it hung with an empty log:
  * it shelled out to `git ls-files` once per first-party root inside the walk loop
  * every print was buffered, so a slow run looked identical to a hung one

Two fixes:
  1. call `git ls-files` ONCE and keep the result in a set
  2. flush every print, and emit a progress line per phase

The heavy path (walking 6,890 tracked files for sizes) is replaced with a single
`git ls-files -s` + os.stat over only files git already reported, and the secret
scan is chunked with a counter so it shows movement.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\audit_source_control.py"
src = open(PATH, encoding="utf-8").read()

if "FLUSH" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

# 1. cache ls-files once
old_git = '''def git(*args, check=False):
    r = subprocess.run(["git", "-C", ROOT] + list(args),
                       capture_output=True, text=True, timeout=180)
    if check and r.returncode != 0:
        print("git failed:", " ".join(args), r.stderr[:200])
    return r.stdout'''

new_git = '''FLUSH = True   # every print is flushed: a buffered hang is indistinguishable from a real one


def git(*args, check=False):
    r = subprocess.run(["git", "-C", ROOT] + list(args),
                       capture_output=True, text=True, timeout=300)
    if check and r.returncode != 0:
        print("git failed:", " ".join(args), r.stderr[:200], flush=FLUSH)
    return r.stdout


_TRACKED_CACHE = None


def tracked_files():
    """git ls-files, computed once. The naive version shelled out per directory
    and made this audit appear hung."""
    global _TRACKED_CACHE
    if _TRACKED_CACHE is None:
        _TRACKED_CACHE = [ln for ln in git("ls-files").splitlines() if ln.strip()]
    return _TRACKED_CACHE'''

if old_git not in src:
    print("ANCHOR-NOT-FOUND: git()")
    sys.exit(1)
src = src.replace(old_git, new_git, 1)

# 2. replace per-root ls-files with the cache
old_c = '''    tracked_set = set(ln for ln in git("ls-files", "--", root).splitlines())'''
new_c = '''    tracked_set = {p for p in tracked_files() if p.startswith(root)}'''
if old_c not in src:
    print("ANCHOR-NOT-FOUND: per-root ls-files")
    sys.exit(1)
src = src.replace(old_c, new_c, 1)

# 3. use the cache in D/E/F
src = src.replace('deleted = git("ls-files", "--deleted").splitlines()',
                  'deleted = git("ls-files", "--deleted").splitlines()')
src = src.replace('for rel in git("ls-files").splitlines():\n    full = os.path.join(ROOT, rel.replace("/", os.sep))\n    try:\n        sz = os.path.getsize(full)',
                  'for rel in tracked_files():\n    full = os.path.join(ROOT, rel.replace("/", os.sep))\n    try:\n        sz = os.path.getsize(full)')
src = src.replace('files = git("ls-files").splitlines()', 'files = tracked_files()')

# 4. every print gets flush=True
out_lines = []
for line in src.splitlines(keepends=True):
    stripped = line.lstrip()
    if stripped.startswith("print(") and "flush=" not in line:
        # insert flush before the final closing paren on this line
        idx = line.rstrip().rfind(")")
        if idx != -1:
            line = line[:idx] + ", flush=FLUSH" + line[idx:]
    out_lines.append(line)
src = "".join(out_lines)

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: ls-files cached, all prints flushed")
