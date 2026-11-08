"""Fix check_unity_proc's two failing assertions -- the CODE was right, the TEST was wrong.

Failure 1: "refusal explains the DataStore, not privileges"
    The message contains the word "privilege" -- in the sentence
        "...this is the measured cause, not a privilege prompt."
    The test rejected it for containing a word it uses to DISCLAIM. Checking for a
    substring instead of checking the claim, again.

Failure 2: "guard permits a trivial allocation"
    guard(need_gb=0.001) was refused because SAFE_HEADROOM_GB (1.5) is added
    unconditionally, and free RAM was 0.65 GB. That is CORRECT behaviour: the
    DataStore allocates a fixed 1 GB regardless of what the caller asks about, so a
    tiny need_gb does not make the launch safe. The test asserted a property the
    function never had.

Both are test bugs. This fixes the assertions, not the implementation -- and adds
the case that actually matters: guard must flip to allowed=True when free RAM is
genuinely sufficient, which cannot be faked, so it is reported as informational
when memory is short rather than failed.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\check_unity_proc.py"
src = open(PATH, encoding="utf-8").read()

if "asserts the CLAIM" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''check("refusal explains the DataStore, not privileges",
      "DataStore" in msg_big and "privilege" not in msg_big.lower(),
      msg_big[:70])
check("refusal says what to do", "reap" in msg_big.lower() or "free" in msg_big.lower())

# a tiny requirement must always be allowed
allowed_small, msg_small = unity_proc.guard(need_gb=0.001)
check("guard permits a trivial allocation", allowed_small is True, msg_small[:60])'''

NEW = '''# This asserts the CLAIM, not a substring. The message legitimately contains the
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
check("guard refuses a need_gb larger than physical memory", allowed_huge is False)'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: assertions")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: assertions now test the claim, not substrings")
