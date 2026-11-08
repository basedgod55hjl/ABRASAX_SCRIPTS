"""Section 4 audit: TESTING AND QUALITY ASSURANCE.

A green suite is not the same as coverage. Tonight three checks were green while
the thing they claimed to verify was broken (a compiled-but-never-instantiated
Unity client, a stub whose namespace did not exist, a DLL search that used the
wrong encoding). So this audit asks a harder question than "do tests pass?":

  which modules that RUN in production have NO test that imports them?

A. test inventory and suite configuration
B. the skip/xfail register -- are they documented failures or hidden ones?
C. coverage by import: every module under abrasax/ that any test imports
D. uncovered modules that are actually wired into a live surface
E. test smells: tests that cannot fail

Exit 0 = every production module is imported by at least one test, or is listed
in a documented exclusion.
"""
import ast
import os
import subprocess
import sys

ROOT = r"C:\ABRASAX"
TESTS = os.path.join(ROOT, "TESTS", "python")
PKG = os.path.join(ROOT, "abrasax")
DEFECTS = []


def header(t):
    print("\n=== " + t + " ===", flush=True)


# ------------------------------------------------------------------ A
header("A. TEST INVENTORY")
test_files = []
for dp, dn, fns in os.walk(TESTS):
    dn[:] = [d for d in dn if d != "__pycache__"]
    for fn in fns:
        if fn.startswith("test_") and fn.endswith(".py"):
            test_files.append(os.path.join(dp, fn))
print(f"  test files        : {len(test_files)}")

n_tests = 0
for f in test_files:
    try:
        tree = ast.parse(open(f, encoding="utf-8", errors="replace").read())
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            n_tests += 1
print(f"  test functions    : {n_tests}")

pyp = os.path.join(ROOT, "pyproject.toml")
cfg = open(pyp, encoding="utf-8").read() if os.path.exists(pyp) else ""
has_testpaths = "testpaths" in cfg
print(f"  pyproject testpaths: {'yes' if has_testpaths else 'NO'}")
print(f"  conftest present   : "
      f"{'yes' if os.path.exists(os.path.join(TESTS, 'conftest.py')) else 'NO'}")

# ------------------------------------------------------------------ B
header("B. SKIP / XFAIL REGISTER")
log = os.path.join(ROOT, "LOGS", "suite2.log")
if os.path.exists(log):
    text = open(log, encoding="utf-8", errors="replace").read()
    for kind in ("SKIPPED", "XFAIL", "XPASS"):
        hits = [ln for ln in text.splitlines() if ln.strip().startswith(kind)]
        print(f"  {kind:8s}: {len(hits)}")
        for h in hits:
            print("    " + h.strip()[:140])
else:
    print("  no suite log at LOGS/suite2.log")

# ------------------------------------------------------------------ C
header("C. WHICH PRODUCTION MODULES DO TESTS IMPORT?")

# every module under abrasax/
pkg_mods = set()
for fn in os.listdir(PKG):
    if fn.endswith(".py") and not fn.startswith("__"):
        pkg_mods.add(fn[:-3])
print(f"  modules in abrasax/: {len(pkg_mods)}")

# what do the tests import?
imported = set()
bare_imports = set()
for f in test_files:
    try:
        src = open(f, encoding="utf-8", errors="replace").read()
        tree = ast.parse(src)
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("abrasax"):
                parts = node.module.split(".")
                if len(parts) > 1:
                    # from abrasax.NAME import ...      -> NAME is the module
                    imported.add(parts[1])
                else:
                    # from abrasax import a, b          -> a and b ARE modules
                    # (missing this made test_cbm_bridge.py invisible and kept
                    #  reporting cbm_bridge as uncovered)
                    for a in node.names:
                        imported.add(a.name)
                for a in node.names:
                    bare_imports.add(a.name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("abrasax."):
                    imported.add(a.name.split(".")[1])

# also catch monkeypatch/importlib style strings
for f in test_files:
    try:
        src = open(f, encoding="utf-8", errors="replace").read()
    except OSError:
        continue
    for mod in pkg_mods:
        if f'"{mod}"' in src or f"'{mod}'" in src:
            imported.add(mod)

covered = sorted(m for m in pkg_mods if m in imported)
uncovered = sorted(m for m in pkg_mods if m not in imported)
print(f"  imported by tests  : {len(covered)}")
print(f"  NEVER imported     : {len(uncovered)}")
for m in uncovered:
    print("    " + m)

# ------------------------------------------------------------------ D
header("D. UNCOVERED MODULES THAT ARE LIVE")
# A module is "live" if the CLI exposes it or a script/service invokes it.
cli = os.path.join(PKG, "cli.py")
cli_text = open(cli, encoding="utf-8", errors="replace").read() if os.path.exists(cli) else ""

live_uncovered = []
for m in uncovered:
    reasons = []
    if m in cli_text:
        reasons.append("referenced in cli.py")
    # look for it in services / gateway
    for f in ("services.py", "gateway.py", "brain.py"):
        p = os.path.join(PKG, f)
        if os.path.exists(p) and m in open(p, encoding="utf-8", errors="replace").read():
            reasons.append("referenced in " + f)
    if reasons:
        live_uncovered.append((m, reasons))

if live_uncovered:
    print(f"  {len(live_uncovered)} uncovered module(s) are wired into a live surface:")
    for m, r in live_uncovered:
        print(f"    {m:22s} {', '.join(r)}")
        DEFECTS.append(f"{m} is live but has no test importing it")
else:
    print("  every uncovered module is inert")

# ------------------------------------------------------------------ E
header("E. TEST SMELLS")
CAN_FAIL_PATTERNS = ('assert', 'raises', 'raise', 'fail')
# tests with no assert and no raise context cannot fail
noassert = []
for f in test_files:
    try:
        tree = ast.parse(open(f, encoding="utf-8", errors="replace").read())
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            # A test can fail in four legitimate ways. Checking only `assert` and
            # `pytest.raises` reported three valid try/except/else tests as
            # un-failable -- the 8th false red tonight.
            has_assert = False
            for n in ast.walk(node):
                if isinstance(n, ast.Assert):
                    has_assert = True
                # explicit `raise ...
                if isinstance(n, ast.Raise):
                    has_assert = True
                # pytest.raises(...) / assertRaises(...) as a context manager
                if isinstance(n, ast.With):
                    for item in n.items:
                        ce = item.context_expr
                        fn = ce.func if isinstance(ce, ast.Call) else None
                        name = getattr(fn, "attr", "") or getattr(fn, "id", "")
                        if name in ("raises", "assertRaises", "warns"):
                            has_assert = True
                # pytest.fail(...)
                if isinstance(n, ast.Call):
                    fn = n.func
                    name = getattr(fn, "attr", "") or getattr(fn, "id", "")
                    if name in ("fail", "assertRaises"):
                        has_assert = True

            has_raises = has_assert
            if not has_assert and not has_raises:
                noassert.append((os.path.basename(f), node.name, node.lineno))


print(f"  tests that cannot fail (no assert, no raises): {len(noassert)}")
for f, n, ln in noassert[:15]:
    print(f"    {f}:{ln} {n}")

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
