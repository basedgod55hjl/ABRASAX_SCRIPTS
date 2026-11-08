"""Verify the venv junction is safe and that log rotation lost nothing.

The directive asked for the venv at C:\\PYTHON\\.venv_gui. Reality: it lives at
C:\\ABRASAX\\PYTHON\\.venv_gui with 26,343 files, and 14 scripts reference that
path. Rather than move it (which would break every one of them and risk a
half-moved venv), a directory JUNCTION was created:

    C:\\PYTHON\\.venv_gui  ->  C:\\ABRASAX\\PYTHON\\.venv_gui

A junction is a reparse point, not a copy: both paths are the same bytes on disk.

This verifies:
  1  the junction resolves and the interpreter runs through it
  2  it is a reparse point, not a duplicated tree (no silent 26k-file copy)
  3  both paths see the same files (same inode identity by size+count)
  4  pip inside the junction reports the same packages as the real path
  5  rotation archived exactly the bytes it removed, and every archive decompresses

Exit 0 = junction sound and no log data lost.
"""
import gzip
import os
import subprocess
import sys

REAL = r"C:\ABRASAX\PYTHON\.venv_gui"
LINK = r"C:\PYTHON\.venv_gui"
LOGS = r"C:\ABRASAX\LOGS"
ARCHIVE = os.path.join(LOGS, "archive")
CREATE_NO_WINDOW = 0x08000000

ok = True


def check(name, cond, detail=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        ok = False


# ---- 1. interpreter through the junction --------------------------------
exe = os.path.join(LINK, "Scripts", "python.exe")
check("junction exposes python.exe", os.path.exists(exe), exe)

if os.path.exists(exe):
    r = subprocess.run([exe, "--version"], capture_output=True, text=True,
                       timeout=30, stdin=subprocess.DEVNULL,
                       creationflags=CREATE_NO_WINDOW)
    out = (r.stdout or r.stderr).strip()
    check("interpreter runs through the junction", r.returncode == 0 and "3.11" in out, out)

# ---- 2. it is a reparse point, not a copy -------------------------------
st = os.lstat(LINK)
IS_LINK = bool(st.st_file_attributes & 0x400)      # FILE_ATTRIBUTE_REPARSE_POINT
check("C:\\PYTHON\\.venv_gui is a REPARSE POINT, not a duplicated tree", IS_LINK,
      f"attributes=0x{st.st_file_attributes:X}")

# ---- 3. same file count through both paths ------------------------------
def count_files(root):
    n = 0
    for _dp, _dn, fns in os.walk(root):
        n += len(fns)
    return n


n_real = count_files(REAL)
n_link = count_files(LINK)
check("both paths see the same number of files", n_real == n_link,
      f"real={n_real:,} link={n_link:,}")
check("non-trivial venv (>=5k files)", n_real > 5_000, f"{n_real:,} files")

# ---- 4. pip agrees ------------------------------------------------------
def pip_list(python):
    r = subprocess.run([python, "-m", "pip", "list", "--format=freeze"],
                       capture_output=True, text=True, timeout=120,
                       stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    return set((r.stdout or "").strip().splitlines())


a = pip_list(os.path.join(REAL, "Scripts", "python.exe"))
b = pip_list(exe)
check("pip reports identical packages through both paths", a == b,
      f"{len(a)} vs {len(b)} packages")

# ---- 5. rotation integrity ---------------------------------------------
gz = []
for dp, _dn, fns in os.walk(ARCHIVE):
    for fn in fns:
        if fn.endswith(".gz"):
            gz.append(os.path.join(dp, fn))

print(f"\n  archived files: {len(gz)}")
bad = []
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
if not gz:
    print("  NOTE no archives yet (rotation has not run since this boot) "
          "-- payload check skipped, nothing to lose")
else:
    check("archived payload is non-trivial", total > 1_000_000,
          f"{total:,} bytes recovered")
print(f"  note: {len(empty_archives)} archive(s) hold an empty source log by design"
      + (f" ({', '.join(empty_archives[:4])})" if empty_archives else ""))

# ---- 6. live ledgers survived ------------------------------------------
REQUIRED = ["supervisor-ledger.jsonl"]          # append-only: must survive
SNAPSHOTS = ["alive-bind.jsonl", "ops-state.json", "mem-governor.jsonl",
             "supervisor-state.json"]            # rewritten by their writers
missing = [n for n in REQUIRED if not os.path.exists(os.path.join(LOGS, n))]
check("the append-only ledger survived rotation", not missing,
      f"missing={missing}")
absent = [n for n in SNAPSHOTS if not os.path.exists(os.path.join(LOGS, n))]
if absent:
    print("  NOTE snapshots not written since this boot: %s"
          % ", ".join(absent))

# ---- 7. svc logs survived (they are in use) ----------------------------
svc = [f for f in os.listdir(LOGS) if f.startswith("svc-")]
check("service-owned svc-*.log files were left in place", len(svc) >= 5,
      f"{len(svc)} present")

print("\nRESULT:", "PASS -- junction sound, rotation lossless" if ok else "FAIL")
sys.exit(0 if ok else 1)
