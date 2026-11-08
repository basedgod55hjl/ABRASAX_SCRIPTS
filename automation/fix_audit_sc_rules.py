"""Fix audit_source_control.py section C (corrected anchors).

Problems, all mine:
  1. It flagged APPS/unreal-brain/Source/ as IGNORED because check-ignore matched
     `.gitignore:99:!APPS/unreal-brain/Source/**`. A leading '!' is a NEGATION --
     the path is explicitly KEPT. I trusted the exit status without reading the
     matched rule.
  2. It counted 39,001 untracked files under DOC/, almost all the deliberately
     untracked 2.77 GB crawled corpus in DOC/source-docs (37,340 files). That is
     noise, not a defect.

Anchors are taken from the file as it actually is (an earlier pass already inserted
flush=FLUSH), which is why the previous attempt missed.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\audit_source_control.py"
src = open(PATH, encoding="utf-8").read()

if "NEGATED" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''    # check-ignore exits 0 if the path WOULD be ignored
    if r.returncode == 0 and r.stdout.strip():
        print(f"  [DEFECT] {root} is IGNORED by: {r.stdout.strip()}", flush=FLUSH)
        DEFECTS.append(f"{root} ignored by {r.stdout.strip()}")
        problems += 1
    else:
        print(f"  ok       {root}", flush=FLUSH)'''

NEW = '''    # check-ignore exits 0 if the path WOULD be ignored -- and also when the
    # matching rule is a NEGATION ('!'), meaning the path is explicitly KEPT.
    # Reading the rule matters: relying on the exit status alone produced a false
    # defect on APPS/unreal-brain/Source/.
    out = r.stdout.strip()
    if r.returncode == 0 and out:
        rule = out.split("\\t")[0]
        pattern = rule.split(":", 2)[-1] if ":" in rule else rule
        NEGATED = pattern.startswith("!")
        if NEGATED:
            print(f"  ok       {root} (re-included by {rule})", flush=FLUSH)
        else:
            print(f"  [DEFECT] {root} is IGNORED by: {out}", flush=FLUSH)
            DEFECTS.append(f"{root} ignored by {out}")
            problems += 1
    else:
        print(f"  ok       {root}", flush=FLUSH)'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND (1): probe loop")
    sys.exit(1)
src = src.replace(OLD, NEW, 1)

OLD2 = '''    missing_from_git = [p for p in on_disk if p not in tracked_set
                        and not p.endswith((".pyc", ".exe", ".obj", ".cubin", ".png"))]'''
NEW2 = '''    # Generated artifacts, archives and backups are not source. Without this the
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

    missing_from_git = [p for p in on_disk if p not in tracked_set and not _is_noise(p)]'''

if OLD2 not in src:
    print("ANCHOR-NOT-FOUND (2): missing_from_git")
    sys.exit(1)
src = src.replace(OLD2, NEW2, 1)

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: negation rules read, archive/backup noise excluded")
