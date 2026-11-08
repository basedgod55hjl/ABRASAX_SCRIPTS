"""Section 3 audit: SOURCE CONTROL AND VERSIONING for C:\\ABRASAX.

Tonight a .gitignore rule (`SOURCE/`) silently excluded the entire Unreal C++
module: nothing under APPS/unreal-brain/Source/ had ever been committable, and no
check noticed. This audit exists so that class of failure is detectable rather
than discovered by accident.

A. repo identity, branch, remote, tracked-file count
B. working tree state (would anything be lost?)
C. .gitignore rules that exclude FIRST-PARTY source -- the exact bug above
D. files tracked but missing from disk (broken index)
E. large binaries tracked (repo bloat)
F. secrets tracked (the one that cannot be undone)

Exit 0 = no defects.
"""
import json
import os
import subprocess
import sys

ROOT = r"C:\ABRASAX"
DEFECTS = []
FAST = "--fast" in sys.argv   # skip the slow corpus-wide secret scan


FLUSH = True   # every print is flushed: a buffered hang is indistinguishable from a real one


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
    return _TRACKED_CACHE


def header(t):
    print(f"\n=== {t} ===", flush=FLUSH)


# ---------------------------------------------------------------- A
header("A. REPOSITORY")
branch = git("branch", "--show-current").strip()
remotes = [ln for ln in git("remote", "-v").splitlines() if "(fetch)" in ln]
tracked = len([ln for ln in git("ls-files").splitlines() if ln.strip()])
print(f"  branch        : {branch}", flush=FLUSH)
print(f"  tracked files : {tracked:,}", flush=FLUSH)
for r in remotes:
    print(f"  remote        : {r}", flush=FLUSH)

if not branch:
    DEFECTS.append("detached HEAD")

if not remotes:
    print("  [WARN] no remote configured", flush=FLUSH)

# ---------------------------------------------------------------- B
header("B. WORKING TREE")
status = [ln for ln in git("status", "--porcelain").splitlines() if ln.strip()]
modified = [s for s in status if not s.startswith("??")]
untracked = [s for s in status if s.startswith("??")]
print(f"  modified/staged : {len(modified)}", flush=FLUSH)
print(f"  untracked       : {len(untracked)}", flush=FLUSH)
for s in modified[:8]:
    print("    " + s, flush=FLUSH)
if modified:
    DEFECTS.append(f"{len(modified)} uncommitted change(s)")

# ---------------------------------------------------------------- C
header("C. GITIGNORE vs FIRST-PARTY SOURCE")
# First-party source roots that MUST be committable.
FIRST_PARTY = [
    "abrasax/",
    "SCRIPTS/automation/",
    "ENGINE/floating_brain/",
    "TESTS/python/",
    "APPS/unreal-brain/Source/",
    "APPS/unity-assets/BrainUI/Scripts/",
    "DOC/",
]

problems = 0
for root in FIRST_PARTY:
    r = subprocess.run(["git", "-C", ROOT, "check-ignore", "-v", root.rstrip("/") + "/_probe"],
                       capture_output=True, text=True)
    # check-ignore exits 0 if the path WOULD be ignored -- and also when the
    # matching rule is a NEGATION ('!'), meaning the path is explicitly KEPT.
    # Reading the rule matters: relying on the exit status alone produced a false
    # defect on APPS/unreal-brain/Source/.
    out = r.stdout.strip()
    if r.returncode == 0 and out:
        rule = out.split("\t")[0]
        pattern = rule.split(":", 2)[-1] if ":" in rule else rule
        NEGATED = pattern.startswith("!")
        if NEGATED:
            print(f"  ok       {root} (re-included by {rule})", flush=FLUSH)
        else:
            print(f"  [DEFECT] {root} is IGNORED by: {out}", flush=FLUSH)
            DEFECTS.append(f"{root} ignored by {out}")
            problems += 1
    else:
        print(f"  ok       {root}", flush=FLUSH)

# Count real files that exist on disk under first-party roots but are untracked.
print("\n  files on disk under first-party roots but NOT tracked:", flush=FLUSH)
for root in FIRST_PARTY:
    full_root = os.path.join(ROOT, root.replace("/", os.sep))
    if not os.path.isdir(full_root):
        continue
    on_disk = []
    for dp, dn, fns in os.walk(full_root):
        dn[:] = [d for d in dn if d not in ("__pycache__", ".git")]
        for fn in fns:
            on_disk.append(os.path.relpath(os.path.join(dp, fn), ROOT).replace(os.sep, "/"))
    if not on_disk:
        continue
    tracked_set = {p for p in tracked_files() if p.startswith(root)}
    # Generated artifacts, archives and backups are not source. Without this the
    # check reported 39,001 "defects" that were all the deliberately-untracked
    # 2.77 GB crawled corpus under DOC/source-docs.
    EXCLUDE_DIRS = ("source-docs/", "rust-docs/", "source-knowledge/",
                    "notebooks-rust/", "source-reports/", "source-root-docs/",
                    "rust-root-docs/", "source-catalogs/")
    EXCLUDE_EXT = (".pyc", ".exe", ".obj", ".cubin", ".png", ".log", ".out",
                   ".dll", ".pdb", ".lib", ".so", ".dylib", ".jsonl")

    def _is_noise(p):
        rel = p.split("/", 1)[1] if "/" in p else p
        if any(rel.startswith(d) for d in EXCLUDE_DIRS):
            return True
        if ".bak-" in p:
            return True
        return p.endswith(EXCLUDE_EXT)

    missing_from_git = [p for p in on_disk if p not in tracked_set and not _is_noise(p)]
    if missing_from_git:
        print(f"    {root}: {len(missing_from_git)} untracked", flush=FLUSH)
        for p in missing_from_git[:5]:
            print(f"      {p}", flush=FLUSH)
        DEFECTS.append(f"{len(missing_from_git)} untracked file(s) under {root}")
        problems += 1

# ---------------------------------------------------------------- D
header("D. INDEX INTEGRITY")
deleted = git("ls-files", "--deleted").splitlines()
if deleted:
    print(f"  {len(deleted)} tracked file(s) missing from disk:", flush=FLUSH)
    for d in deleted[:8]:
        print("    " + d, flush=FLUSH)
    DEFECTS.append(f"{len(deleted)} tracked file(s) deleted on disk")
else:
    print("  every tracked file exists on disk", flush=FLUSH)

# ---------------------------------------------------------------- E
header("E. LARGE TRACKED BINARIES")
BIG = 5 * 1024 * 1024
big = []
for rel in tracked_files():
    full = os.path.join(ROOT, rel.replace("/", os.sep))
    try:
        sz = os.path.getsize(full)
    except OSError:
        continue
    if sz > BIG:
        big.append((sz, rel))
big.sort(reverse=True)
if big:
    print(f"  {len(big)} tracked file(s) over 5 MB:", flush=FLUSH)
    for sz, rel in big[:8]:
        print(f"    {sz / 1e6:8.1f} MB  {rel}", flush=FLUSH)
    DEFECTS.append(f"{len(big)} tracked binary over 5 MB")
else:
    print("  none over 5 MB", flush=FLUSH)

# ---------------------------------------------------------------- F
if FAST:
    header("F. SECRETS IN TRACKED FILES")
    print("  skipped (--fast); run without --fast for the full corpus scan", flush=FLUSH)
    hits = []
else:
    header("F. SECRETS IN TRACKED FILES")
    PATTERNS = ("nvapi-", "sk-", "ghp_", "AKIA", "BEGIN RSA PRIVATE KEY",
                "BEGIN OPENSSH PRIVATE KEY", "xoxb-", "AIza")
    hits = []
    files = tracked_files()
    for rel in files:
        if not rel.endswith((".py", ".ps1", ".bat", ".json", ".toml", ".md", ".env", ".txt", ".cs", ".cpp", ".h")):
            continue
        full = os.path.join(ROOT, rel.replace("/", os.sep))
        try:
            # 1 MB cap: the big files here are generated catalogs (a 30 MB
            # FILESYSTEM_INDEX.json). Scanning them for keys is pointless and
            # dominated the runtime of this whole audit.
            if os.path.getsize(full) > 1_000_000:
                continue
            text = open(full, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for pat in PATTERNS:
            if pat in text:
                hits.append((rel, pat))
                break

    if hits:
        print(f"  {len(hits)} tracked file(s) contain a secret-shaped string:", flush=FLUSH)
        for rel, pat in hits[:12]:
            print(f"    {rel}  <- {pat}", flush=FLUSH)
        DEFECTS.append(f"{len(hits)} tracked file(s) contain secret-shaped strings")
    else:
        print("  none found in tracked text files", flush=FLUSH)

    # ---------------------------------------------------------------- summary
header("SUMMARY")
if DEFECTS:
    print(f"{len(DEFECTS)} defect(s):", flush=FLUSH)
    for d in DEFECTS:
        print("  - " + d, flush=FLUSH)
    print("\nRESULT: DEFECTS FOUND", flush=FLUSH)
    sys.exit(1)

print("no defects found", flush=FLUSH)
print("\nRESULT: PASS", flush=FLUSH)
sys.exit(0)
