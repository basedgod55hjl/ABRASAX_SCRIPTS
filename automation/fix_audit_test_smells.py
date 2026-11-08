"""Fix audit_testing.py: a test can fail without a literal `assert`.

Section E flagged three tests as 'cannot fail':

    test_native.py:165  test_policy_refuses_unknown_and_empty
    test_native.py:175  test_policy_refuses_unsafe_arguments
    test_native.py:195  test_policy_timeout_bounds

They use the try/except/else pattern:

    try:
        native.call(bad)
    except native.NativePolicyError:
        pass
    else:
        raise AssertionError(f"... should have been refused")

That is a perfectly good assertion -- and arguably stricter than `pytest.raises`,
because it names the expected exception explicitly. My detector only looked for
`ast.Assert` and for `raises` context managers, so it missed `raise` entirely.

Eighth false red tonight. Fix the detector: a test can fail via assert, via a
raises context manager, via an explicit `raise`, or via pytest.fail().
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\audit_testing.py"
src = open(PATH, encoding="utf-8").read()

if "CAN_FAIL_PATTERNS" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD_START = '''        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            has_assert = any(isinstance(n, ast.Assert) for n in ast.walk(node))'''

OLD_END = '''            if not has_assert and not has_raises:
                noassert.append((os.path.basename(f), node.name, node.lineno))'''

i = src.find(OLD_START)
j = src.find(OLD_END)
if i == -1 or j == -1 or j < i:
    print("ANCHOR-NOT-FOUND: section E loop")
    sys.exit(1)

NEW = '''        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
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
'''

src = src[:i] + NEW + src[j + len(OLD_END):]
src = src.replace("header(\"E. TEST SMELLS\")",
                  "header(\"E. TEST SMELLS\")\nCAN_FAIL_PATTERNS = ('assert', 'raises', 'raise', 'fail')")
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: raise / pytest.fail now count as failure paths")
