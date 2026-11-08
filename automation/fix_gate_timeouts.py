"""Cap per-tool time in the gate so one slow check cannot stall the loop.

Measured on a real run:
    check-tree-organised   29.22s   <- walks a 26,343-file venv then decompresses 61 archives
    check-doc-verifier     15.96s
    everything else         < 3.3s

The gate's value is a fast signal. A 29-second tool in the "medium" stage makes the
whole feedback loop slow, and the fix is not to delete the check -- it is to give it
a budget and report honestly when the budget is exceeded.

Behaviour:
  * each tool gets a stage-specific timeout
  * exceeding it is recorded as TIMEOUT, which FAILS the stage (a check that cannot
    finish inside its budget is not a pass)
  * the report distinguishes TIMEOUT from FAIL so the difference is visible

That last point matters: silently treating a timeout as "skip" is how a gate rots.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\build_gate.py"
src = open(PATH, encoding="utf-8").read()

if "STAGE_TIMEOUTS" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

# 1. add budgets
OLD_ORDER = 'ORDER = ["fast", "medium", "heavy"]'
NEW_ORDER = '''ORDER = ["fast", "medium", "heavy"]

# Per-stage budget in seconds. Measured costs: fast < 3.3 s each, medium up to 29 s,
# heavy up to 25 s. A tool that cannot finish inside its budget is NOT a pass --
# silently skipping it is how a gate rots into decoration.
STAGE_TIMEOUTS = {"fast": 30, "medium": 120, "heavy": 180}'''
if OLD_ORDER not in src:
    print("ANCHOR-NOT-FOUND: ORDER")
    sys.exit(1)
src = src.replace(OLD_ORDER, NEW_ORDER, 1)

# 2. use the budget and record timeout separately
OLD_RUN = '''            res = R.run_one(tool, timeout=180)
            matrix.append({
                "stage": stage, "tool": n, "ok": res["ok"],
                "rc": res["rc"], "s": res["elapsed_s"],
            })
            mark = "ok  " if res["ok"] else "FAIL"'''
NEW_RUN = '''            budget = STAGE_TIMEOUTS.get(stage, 180)
            res = R.run_one(tool, timeout=budget)
            timed_out = "TIMEOUT" in (res.get("stderr") or "")
            matrix.append({
                "stage": stage, "tool": n, "ok": res["ok"],
                "rc": res["rc"], "s": res["elapsed_s"],
                "timeout": timed_out,
            })
            mark = "TIMEOUT" if timed_out else ("ok  " if res["ok"] else "FAIL")'''
if OLD_RUN not in src:
    print("ANCHOR-NOT-FOUND: run block")
    sys.exit(1)
src = src.replace(OLD_RUN, NEW_RUN, 1)

# 3. report timeouts distinctly in the summary
OLD_SUM = '''    ok = sum(1 for r in matrix if r["ok"])'''
NEW_SUM = '''    ok = sum(1 for r in matrix if r["ok"])
    timeouts = sum(1 for r in matrix if r.get("timeout"))'''
if OLD_SUM not in src:
    print("ANCHOR-NOT-FOUND: ok sum")
    sys.exit(1)
src = src.replace(OLD_SUM, NEW_SUM, 1)

OLD_REPORT = '''    print(f"  failed    : {len(matrix) - ok}")'''
NEW_REPORT = '''    print(f"  failed    : {len(matrix) - ok}")
    if timeouts:
        print(f"  timed out : {timeouts} (counted as failures)")'''
if OLD_REPORT not in src:
    print("ANCHOR-NOT-FOUND: failed line")
    sys.exit(1)
src = src.replace(OLD_REPORT, NEW_REPORT, 1)

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: per-stage budgets; TIMEOUT reported and counted as failure")
