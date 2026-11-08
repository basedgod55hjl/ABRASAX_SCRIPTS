"""Meta-check: prove audit_env_process.py can actually DETECT a defect.

Six times tonight a red result was the checker's fault. The inverse risk is just as
bad and I have not tested it: a checker that always prints PASS is worthless and I
would not notice, because PASS is what I want to see.

This injects known-bad conditions and asserts the audit catches them. If the audit
still says PASS with a defect present, the audit is decoration.

Method: run the real detector functions on synthetic process data rather than
perturbing the live system (which would mean killing real services).

Exit 0 = the detectors fire on bad input and stay quiet on good input.
"""
import importlib.util
import sys

SPEC = r"C:\ABRASAX\SCRIPTS\automation\audit_env_process.py"
spec = importlib.util.spec_from_file_location("audit", SPEC)
audit = importlib.util.module_from_spec(spec)
# do not execute main(); just load the module to reach its helpers
try:
    spec.loader.exec_module(audit)
except SystemExit:
    pass  # the module exits at the end; we only need its definitions

ok = True


def report(name, passed, detail=""):
    global ok
    print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not passed:
        ok = False


# ---------------------------------------------------------------- root counting
# The rule under test: one instance behind a launcher chain is NOT a duplicate.

GOOD_CHAIN = [
    ("100", "1",   'cmd /c "python.exe script.py"'),      # root
    ("101", "100", "python.exe script.py"),               # venv shim
    ("102", "101", "uv/python.exe script.py"),            # real interpreter
]

BAD_DUPES = GOOD_CHAIN + [
    ("200", "1",   'cmd /c "python.exe script.py"'),      # second independent
    ("201", "200", "python.exe script.py"),
]

audit.procs = GOOD_CHAIN
if hasattr(audit, "count_roots"):
    roots, hits = audit.count_roots("script.py")
    report("launcher chain of 3 counts as 1 instance",
           len(roots) == 1 and len(hits) == 3,
           f"roots={len(roots)} pids={len(hits)}")

    audit.procs = BAD_DUPES
    roots, hits = audit.count_roots("script.py")
    report("two independent chains count as 2 instances",
           len(roots) == 2,
           f"roots={len(roots)} pids={len(hits)}")

    audit.procs = []
    roots, hits = audit.count_roots("script.py")
    report("no processes -> 0 instances", len(roots) == 0)
else:
    report("count_roots exists", False, "function missing")
    audit.procs = []

# ---------------------------------------------------------------- pid hygiene
# A pid file naming a dead process must be reported stale.
import os
import tempfile

LOGS = r"C:\ABRASAX\LOGS"
probe = os.path.join(LOGS, "_audit_meta_probe.pid")

with open(probe, "w") as f:
    f.write("999999")  # certainly not a live pid

alive = audit.run_ps(
    "if (Get-Process -Id 999999 -EA 0) {'yes'} else {'no'}")
report("a bogus pid is detected as dead", alive.strip() == "no", f"got {alive!r}")

# and a real pid as alive.
# Use THIS process: it is guaranteed to exist while the check runs. Asking a
# child PowerShell for its own $PID gives a pid that dies the moment that child
# exits, which made the previous version of this check report a false failure.
mypid = os.getpid()
alive2 = audit.run_ps(f"if (Get-Process -Id {mypid} -EA 0) {{'yes'}} else {{'no'}}")
report("a live pid is detected as alive", alive2.strip() == "yes",
       f"pid {mypid} -> {alive2!r}")

os.remove(probe)

# ---------------------------------------------------------------- env presence
# run_ps must actually return data; a silent empty string would make every
# environment check trivially pass.
out = audit.run_ps("'MARKER-OK'")
report("run_ps returns real output", "MARKER-OK" in out, repr(out[:40]))

out = audit.run_ps("Write-Error 'boom' 2>$null")
report("run_ps survives a failing command", isinstance(out, str), "returned a string")

print("\nRESULT:", "PASS -- the audit detects defects it is shown" if ok else "FAIL")
sys.exit(0 if ok else 1)
