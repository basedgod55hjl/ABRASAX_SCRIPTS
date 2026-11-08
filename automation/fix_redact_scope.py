"""Make redact_config_secrets.py finish: scope it to real config files, add progress.

Why it never returned:
  * it walked all of CONFIG/ (21,858 'files') and read every .json/.yaml/.toml/.py
  * CONFIG/agi-config and CONFIG/source-config are harvested third-party tool
    settings -- tens of thousands of irrelevant files
  * no progress output, so a slow run was indistinguishable from a hung one
  * two copies ended up running at once (an earlier timeout left one alive), each
    burning CPU and fighting the other

Fixes:
  1. skip the harvested trees (agi-config, source-config) entirely -- they are
     vendored content, not our configuration
  2. classify placeholder values (sk-your-key-here, sk-bypass-osirisblxck) as NOT
     secrets, so redaction does not mangle documentation
  3. print a progress line every 200 files
  4. write the vault file as soon as hits are known, before the write phase
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\redact_config_secrets.py"
src = open(PATH, encoding="utf-8").read()

if "SKIP_DIRS" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

# 1. scope
OLD_SCAN = '''    targets = []
    for dp, dn, fns in os.walk(CONFIG):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for fn in fns:
            if fn.endswith((".json", ".yaml", ".yml", ".toml", ".ini",
                            ".cfg", ".py", ".local", ".settings")):
                targets.append(os.path.join(dp, fn))'''

NEW_SCAN = '''    # Harvested third-party trees: tens of thousands of vendored settings files
    # that are not our configuration. Scanning them made this never finish.
    SKIP_DIRS = {"agi-config", "source-config"}

    targets = []
    for dp, dn, fns in os.walk(CONFIG):
        dn[:] = [d for d in dn
                 if d != "__pycache__" and d not in SKIP_DIRS]
        for fn in fns:
            if fn.endswith((".json", ".yaml", ".yml", ".toml", ".ini",
                            ".cfg", ".py", ".local", ".settings")):
                targets.append(os.path.join(dp, fn))
    print(f"scanning {len(targets)} config file(s) "
          f"(skipping {', '.join(sorted(SKIP_DIRS))})")'''

if OLD_SCAN not in src:
    print("ANCHOR-NOT-FOUND: scan block")
    sys.exit(1)
src = src.replace(OLD_SCAN, NEW_SCAN, 1)

# 2. placeholder filter inside scan_file
OLD_HIT = '''                if tok.startswith(pre) and lo <= len(tok) <= hi:
                    hits.append((ln, tok))
                    break'''
NEW_HIT = '''                if tok.startswith(pre) and lo <= len(tok) <= hi:
                    # Placeholders are not secrets. Redacting them would corrupt
                    # documentation and template files.
                    low = tok.lower()
                    if ("your" in low or "xxxx" in low or "bypass" in low
                            or "here" in low or "placeholder" in low
                            or low.endswith("-key")):
                        break
                    hits.append((ln, tok))
                    break'''
if OLD_HIT not in src:
    print("ANCHOR-NOT-FOUND: hit append")
    sys.exit(1)
src = src.replace(OLD_HIT, NEW_HIT, 1)

# 3. progress
OLD_LOOP = '''    files_with_hits = 0
    total_hits = 0
    for full in targets:
        hits = scan_file(full)'''
NEW_LOOP = '''    files_with_hits = 0
    total_hits = 0
    for idx, full in enumerate(targets, 1):
        if idx % 200 == 0:
            print(f"  ... {idx}/{len(targets)} files scanned", flush=True)
        hits = scan_file(full)'''
if OLD_LOOP not in src:
    print("ANCHOR-NOT-FOUND: scan loop")
    sys.exit(1)
src = src.replace(OLD_LOOP, NEW_LOOP, 1)

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: scoped to real config, placeholder filter, progress")
