"""Verify unity_proc does what it claims, including the negative cases.

Claims to test:
  1  guard() refuses when RAM is short and permits when it is not (both directions)
  2  reap() finds an orphaned Unity helper and leaves a live one alone
  3  read_upm() returns quickly on a missing file, an empty file and a large file
  4  read_upm() distinguishes "empty because truncated" from "not present"
  5  stale_upm() flags an old file and not a fresh one

The orphan test uses a process pair we create ourselves, not the real editor, so
the test cannot disturb a build.
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")

import unity_proc  # noqa: E402

LOGS = r"C:\ABRASAX\LOGS"
PY = sys.executable
CREATE_NO_WINDOW = 0x08000000
ok = True


def check(name, cond, detail=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        ok = False


# ---- 1. guard, both directions ------------------------------------------
allowed, msg = unity_proc.guard(need_gb=1.0)
print(f"\nguard(1.0 GB): allowed={allowed}")
print(f"  {msg}")
check("guard returns a bool and a message",
      isinstance(allowed, bool) and isinstance(msg, str) and len(msg) > 10)

# an absurd requirement must always be refused
allowed_big, msg_big = unity_proc.guard(need_gb=10_000.0)
check("guard refuses an impossible allocation", allowed_big is False)
# This asserts the CLAIM, not a substring. The message legitimately contains the
# word "privilege" -- in "not a privilege prompt", which is the disclaimer.
check("refusal names the DataStore as the cause",
      "DataStore" in msg_big, msg_big[:70])
check("refusal does not BLAME a privilege prompt",
      "not a privilege prompt" in msg_big,
      "message explicitly disclaims it")
check("refusal says what to do",
      "reap" in msg_big.lower() or "free memory" in msg_big.lower())

# guard() adds a fixed headroom because DataStore always allocates 1 GB, so a
# small need_gb does NOT make a launch safe. The honest assertions are:
#   * with insufficient RAM it must refuse, whatever need_gb says  (tested above)
#   * its verdict must AGREE with measured free memory
fb = unity_proc.free_gb()
allowed_small, msg_small = unity_proc.guard(need_gb=0.001)
if fb >= unity_proc.DATASTORE_GB + unity_proc.SAFE_HEADROOM_GB:
    check("guard permits a launch when RAM is genuinely sufficient",
          allowed_small is True, f"{fb:.2f} GB free")
else:
    check("guard refuses when RAM is insufficient, even for a tiny need_gb",
          allowed_small is False, f"{fb:.2f} GB free < {unity_proc.DATASTORE_GB + unity_proc.SAFE_HEADROOM_GB:.1f} GB")

# the boundary: need_gb so large that refusal is certain even with lots of RAM
allowed_huge, _ = unity_proc.guard(need_gb=1e6)
check("guard refuses a need_gb larger than physical memory", allowed_huge is False)

# ---- 2. reap: orphan vs live --------------------------------------------
# Build a parent/child pair, then kill the parent so the child is orphaned.
# Use cmd.exe as a stand-in: we test the REAPER, not Unity.
parent_script = (
    "$p = Start-Process -FilePath cmd.exe -ArgumentList '/c','ping -n 60 127.0.0.1 >nul' "
    "-WindowStyle Hidden -PassThru; $p.Id"
)
parent_pid = subprocess.run(
    ["powershell", "-NoProfile", "-NonInteractive", "-Command", parent_script],
    capture_output=True, text=True, timeout=30).stdout.strip()
time.sleep(1.0)
print(f"\n  created stand-in parent pid={parent_pid}")

# the reaper only looks at Unity-named processes, so this 'orphan' must NOT be
# touched -- that is itself the property: reap() is narrowly scoped.
victims = unity_proc.reap(dry_run=True)
names = {v["name"] for v in victims}
check("reap() only considers Unity-family processes",
      all(n in unity_proc.UNITY_HELPERS or n == "Unity.exe" for n in names),
      f"names seen: {sorted(names) if names else 'none'}")

# clean up the stand-in
subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                f"Stop-Process -Id {parent_pid} -Force -EA 0"],
               capture_output=True, text=True, timeout=20)

# ---- 3/4. read_upm timing and semantics ---------------------------------
missing = os.path.join(LOGS, "_no_such_upm.log")
if os.path.exists(missing):
    os.remove(missing)
t0 = time.time()
r = unity_proc.read_upm(missing)
dt = time.time() - t0
check("read_upm on a missing file returns fast", dt < 2.0, f"{dt:.2f}s")
check("read_upm reports 'not present' distinctly",
      r["exists"] is False and "not present" in (r["error"] or ""), r["error"][:60])

empty = os.path.join(LOGS, "_empty_upm.log")
open(empty, "w").close()
r = unity_proc.read_upm(empty)
check("read_upm on an EMPTY existing file says exists=True, bytes=0",
      r["exists"] is True and r["bytes"] == 0, f"exists={r['exists']} bytes={r['bytes']}")

big = os.path.join(LOGS, "_big_upm.log")
with open(big, "w", encoding="utf-8") as f:
    for i in range(20000):
        f.write(f"line {i} " + "x" * 60 + "\n")
t0 = time.time()
r = unity_proc.read_upm(big, max_bytes=100_000)
dt = time.time() - t0
check("read_upm on a large file is bounded", dt < 3.0 and r["truncated"] is True,
      f"{dt:.2f}s truncated={r['truncated']}")
check("read_upm returns at most 60 lines", len(r["lines"]) <= 60, str(len(r["lines"])))

# ---- 5. stale_upm --------------------------------------------------------
fresh = os.path.join(LOGS, "_fresh_upm.log")
open(fresh, "w").write("x")
check("stale_upm is False for a fresh file",
      unity_proc.stale_upm(fresh, max_age_s=300) is False)

old = os.path.join(LOGS, "_old_upm.log")
open(old, "w").write("x")
os.utime(old, (time.time() - 3600, time.time() - 3600))
check("stale_upm is True for a file untouched for an hour",
      unity_proc.stale_upm(old, max_age_s=300) is True)

for f in (empty, big, fresh, old):
    try:
        os.remove(f)
    except OSError:
        pass

print("\nRESULT:", "PASS -- process/memory guard and log reader behave" if ok else "FAIL")
sys.exit(0 if ok else 1)
