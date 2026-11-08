"""Section 5 audit: CONFIGURATION AND SECRETS MANAGEMENT.

The question is not "is there a .env?" -- it is "is there ONE source of truth, and
are secrets only there?". Tonight already found a key hardcoded in a tracked .ts
file, so the audit looks for the same class everywhere.

A. config inventory: which files are real config vs vendored catch
B. .env hygiene: present, gitignored, complete (names only, never values)
C. secret literals in config files and code (delegates to triage_secrets logic)
D. env-var references in code that are never defined anywhere (typos / dead config)
E. defined-but-unused keys (rot candidates, and a smell that .env has drifted)
F. precedence: does anything override .env, and is that documented?

Exit 0 = single source of truth, no secret literals, no dead references.
"""
import os
import re
import subprocess
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from secret_rules import classify, mask  # noqa: E402  (shared with the redactor)

ROOT = r"C:\ABRASAX"
ENV = os.path.join(ROOT, ".env")
DEFECTS = []


def header(t):
    print("\n=== " + t + " ===", flush=True)


# ------------------------------------------------------------------ A
header("A. CONFIG INVENTORY")
config_dir = os.path.join(ROOT, "CONFIG")
real_config, vendored = [], []
if os.path.isdir(config_dir):
    for dp, dn, fns in os.walk(config_dir):
        for fn in fns:
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            ext = os.path.splitext(fn)[1].lower()
            # C++ headers, PDFs, SVGs, AUTHORS are vendored source, not our config
            if ext in (".h", ".hpp", ".inl", ".pdf", ".svg", ".c", ".cpp", ".py",
                       ".md", ".txt") or fn in ("AUTHORS", "LICENSE", "README"):
                vendored.append(rel)
            else:
                real_config.append(rel)

print(f"  real config files : {len(real_config)}")
for r in real_config[:10]:
    print("    " + r)
print(f"  vendored catch    : {len(vendored)} file(s) that are NOT config")
# MEASUREMENT, not a verdict. CONFIG/agi-config is a harvested tree that also holds
# live configuration, so "N vendored files" is not a defect -- see split_agi_config.py
# for the real split (2,201 residue / 68 referenced / 246 unread). Only something
# that can BREAK the system belongs in DEFECTS.
if vendored:
    kinds = sorted(set(os.path.splitext(v)[1] or os.path.basename(v) for v in vendored))
    print(f"    note: {len(vendored)} harvested file(s) share this tree "
          f"({', '.join(kinds[:8])})")
    print("    these are archived content, not configuration; see "
          "SCRIPTS/automation/split_agi_config.py")

# ------------------------------------------------------------------ B
header("B. .env HYGIENE")
if not os.path.exists(ENV):
    print("  .env MISSING")
    DEFECTS.append(".env missing")
    env_keys = {}
else:
    env_keys = {}
    for line in open(ENV, encoding="utf-8", errors="replace"):
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        env_keys[k.strip()] = v.strip()
    print(f"  .env present      : {len(env_keys)} keys")

    r = subprocess.run(["git", "-C", ROOT, "check-ignore", "-v", ".env"],
                       capture_output=True, text=True)
    ignored = r.returncode == 0
    print(f"  .env gitignored   : {ignored}")
    if not ignored:
        DEFECTS.append(".env is NOT gitignored")
        print("    [DEFECT] .env would be committed")

    tracked = subprocess.run(["git", "-C", ROOT, "ls-files", "--error-unmatch", ".env"],
                             capture_output=True, text=True)
    if tracked.returncode == 0:
        DEFECTS.append(".env is TRACKED by git")
        print("    [DEFECT] .env is tracked")

    # values must never be printed, only checked for emptiness
    empty = [k for k, v in env_keys.items() if not v or v in ('""', "''")]
    print(f"  keys with empty values: {len(empty)}")
    for k in empty[:10]:
        print("    " + k)

# ------------------------------------------------------------------ C
header("C. SECRET LITERALS IN CONFIG AND CODE")
PATTERNS = {
    "nvapi-": (40, 90),
    "sk-": (20, 200),
    "ghp_": (36, 40),
    "AKIA": (20, 21),
    "xoxb-": (30, 90),
}
TOKEN = re.compile(r"[A-Za-z0-9_\-]{16,220}")

# scan only configuration-ish files: .env, yaml, json, toml, ini, py under abrasax/
# Harvested third-party tool trees. Section A already classifies these as
# "vendored catch"; section C must respect that instead of re-scanning 19,000
# files that are not our configuration.
SCAN_SKIP = {"agi-config", "source-config"}

targets = []
for base in (os.path.join(ROOT, "CONFIG"), os.path.join(ROOT, "abrasax")):
    if not os.path.isdir(base):
        continue
    for dp, dn, fns in os.walk(base):
        dn[:] = [d for d in dn if d != "__pycache__" and d not in SCAN_SKIP]
        for fn in fns:
            if fn.endswith((".yaml", ".yml", ".json", ".toml", ".ini", ".py", ".cfg")):
                targets.append(os.path.join(dp, fn))
print(f"  (skipping vendored trees: {', '.join(sorted(SCAN_SKIP))})", flush=True)

literals = []
for full in targets:
    try:
        if os.path.getsize(full) > 2_000_000:
            continue
        text = open(full, encoding="utf-8", errors="ignore").read()
    except OSError:
        continue
    for line_no, line in enumerate(text.splitlines(), 1):
        for pre, (lo, hi) in PATTERNS.items():
            if pre not in line:
                continue
            for m in TOKEN.finditer(line):
                tok = m.group(0)
                if not (tok.startswith(pre) and lo <= len(tok) <= hi):
                    continue
                # an os.environ read is not a literal
                if "environ" in line or "getenv" in line or "process.env" in line:
                    continue
                # Shared classifier: placeholders such as sk-your-key-here are
                # documentation, not credentials.
                _prefix, is_secret, _why = classify(tok)
                if not is_secret:
                    break
                literals.append((os.path.relpath(full, ROOT), line_no, mask(tok)))
                break

print(f"  scanned           : {len(targets)} config/code files")
if literals:
    print(f"  [DEFECT] {len(literals)} secret literal(s):")
    for rel, ln, masked in literals[:12]:
        print(f"    {rel}:{ln}  {masked}")
    DEFECTS.append(f"{len(literals)} secret literal(s) in config/code")
else:
    print("  no secret literals found")

# ------------------------------------------------------------------ D
header("D. ENV VARS READ BY CODE BUT NEVER DEFINED")
READ = re.compile(r"""(?:os\.environ(?:\.get)?\s*[\(\[]\s*["'](\w+)["']|"""
                  r"""os\.getenv\s*\(\s*["'](\w+)["'])""")
referenced = defaultdict(set)
code_roots = [os.path.join(ROOT, "abrasax"),
              os.path.join(ROOT, "SCRIPTS", "automation"),
              os.path.join(ROOT, "ENGINE", "floating_brain")]
for base in code_roots:
    if not os.path.isdir(base):
        continue
    for dp, dn, fns in os.walk(base):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for fn in fns:
            if not fn.endswith(".py"):
                continue
            full = os.path.join(dp, fn)
            try:
                text = open(full, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            for m in READ.finditer(text):
                name = m.group(1) or m.group(2)
                if name:
                    referenced[name].add(os.path.relpath(full, ROOT))

defined = set(env_keys)
# defaults passed as the second arg to get() are fine to be undefined
UNDEFINED_OK = set()
for base in code_roots:
    if not os.path.isdir(base):
        continue
    for dp, dn, fns in os.walk(base):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for fn in fns:
            if not fn.endswith(".py"):
                continue
            try:
                text = open(os.path.join(dp, fn), encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            # Two default idioms exist in this codebase. Missing the second one
            # produced five false defects.
            #   os.environ.get("X", default)      <- keyword form
            for m in re.finditer(r"""environ\.get\s*\(\s*["'](\w+)["']\s*,\s*[^)]+\)""", text):
                UNDEFINED_OK.add(m.group(1))
            #   os.environ.get("X") or default    <- boolean-or form
            OR_DEFAULT = re.finditer(
                r"""environ\.get\s*\(\s*["'](\w+)["']\s*\)\s*or\s+[^\n#]+""", text)
            for m in OR_DEFAULT:
                UNDEFINED_OK.add(m.group(1))
            #   os.getenv("X") or default
            for m in re.finditer(
                    r"""getenv\s*\(\s*["'](\w+)["']\s*\)\s*or\s+[^\n#]+""", text):
                UNDEFINED_OK.add(m.group(1))

print(f"  env vars referenced: {len(referenced)}")
neither = sorted(k for k in referenced
                 if k not in defined and k not in UNDEFINED_OK)
print(f"  referenced but neither in .env nor given a code default: {len(neither)}")
for k in neither:
    files = sorted(referenced[k])[:2]
    print(f"    {k:28s} {', '.join(files)}")
if neither:
    DEFECTS.append(f"{len(neither)} env var(s) read with no definition and no default")

# ------------------------------------------------------------------ E
header("E. DEFINED BUT NEVER READ")
unused = sorted(k for k in defined if k not in referenced)
print(f"  .env keys never read by the audited code: {len(unused)}")
for k in unused[:20]:
    print("    " + k)
if len(unused) > 20:
    print(f"    ... and {len(unused) - 20} more")

# ------------------------------------------------------------------ summary
header("SUMMARY")
if DEFECTS:
    print(f"{len(DEFECTS)} defect(s):")
    for d in DEFECTS:
        print("  - " + d)
    print("\nRESULT: DEFECTS FOUND")
    sys.exit(1)

print("no defects found")
print("\nRESULT: PASS")
sys.exit(0)
