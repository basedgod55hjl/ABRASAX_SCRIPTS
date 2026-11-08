"""Correct the archive check and stop rotating empty files.

DIAGNOSED (diagnose_archive.py), the 3 "bad" archives are:

    ov3.log.gz              gz=28 B   raw=0
    overlay.log.gz          gz=32 B   raw=0
    swarm-run.err.log.gz    gz=38 B   raw=0

They decompress perfectly. They are gzip headers around EMPTY source logs -- a
28-38 byte gzip stream is exactly what compressing zero bytes produces. So:

  * no data was lost. The originals had no content.
  * the checker's message "every archive decompresses -> FAIL" was misleading: it
    was not a decompression failure, it was a policy question about whether to
    archive empty files at all.

Two fixes:
  1  the checker reports empty-archive count separately and does not fail on it,
     because empty in equals empty out is correct
  2  rotate_logs skips 0-byte files: archiving nothing wastes an inode and makes
     the archive count misleading
"""
import sys

# ---- fix 1: the checker --------------------------------------------------
P1 = r"C:\ABRASAX\SCRIPTS\automation\check_tree_organised.py"
s1 = open(P1, encoding="utf-8").read()

if "empty_archives" in s1:
    print("checker ALREADY-PATCHED")
else:
    OLD1 = '''bad = []
total = 0
for g in gz:
    try:
        with gzip.open(g, "rb") as f:
            data = f.read()
        total += len(data)
        if len(data) == 0 and os.path.getsize(g) < 40:
            bad.append((g, "suspiciously small"))
    except OSError as e:
        bad.append((g, str(e)))

check("every archive decompresses", not bad, f"{len(bad)} bad of {len(gz)}")
check("archived payload is non-trivial", total > 1_000_000, f"{total:,} bytes recovered")'''

    NEW1 = '''bad = []
empty_archives = []
total = 0
for g in gz:
    try:
        with gzip.open(g, "rb") as f:
            data = f.read()
        total += len(data)
        if len(data) == 0:
            # A valid gzip stream of 0 bytes. This is CORRECT: the source log was
            # empty. It is not a decompression failure, so it must not fail the
            # check -- but it is worth counting so the archive count is honest.
            empty_archives.append(os.path.basename(g))
    except OSError as e:
        bad.append((g, str(e)))

check("every archive decompresses", not bad, f"{len(bad)} genuinely corrupt of {len(gz)}")
check("archived payload is non-trivial", total > 1_000_000, f"{total:,} bytes recovered")
print(f"  note: {len(empty_archives)} archive(s) hold an empty source log by design"
      + (f" ({', '.join(empty_archives[:4])})" if empty_archives else ""))'''

    if OLD1 not in s1:
        print("checker ANCHOR-NOT-FOUND")
        sys.exit(1)
    s1 = s1.replace(OLD1, NEW1, 1)
    open(P1, "w", encoding="utf-8", newline="").write(s1)
    print("checker: empty archives reported, not failed")

# ---- fix 2: the rotator --------------------------------------------------
P2 = r"C:\ABRASAX\SCRIPTS\automation\rotate_logs.py"
s2 = open(P2, encoding="utf-8").read()

if "st_size == 0" in s2:
    print("rotator ALREADY-PATCHED")
else:
    OLD2 = '''            age_min = (now - st.st_mtime) / 60
            if age_min < MIN_AGE_MINUTES:'''
    NEW2 = '''            if st.st_size == 0:
                # Archiving nothing produces a 20-40 byte gzip and makes the
                # archive count misleading. An empty log has nothing to preserve.
                skipped_recent += 1
                continue
            age_min = (now - st.st_mtime) / 60
            if age_min < MIN_AGE_MINUTES:'''
    if OLD2 not in s2:
        print("rotator ANCHOR-NOT-FOUND")
        sys.exit(1)
    s2 = s2.replace(OLD2, NEW2, 1)
    open(P2, "w", encoding="utf-8", newline="").write(s2)
    print("rotator: 0-byte files skipped")
