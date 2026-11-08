"""Fix the URL search in verify_unity_runtime_contract.py.

The checker searched Assembly-CSharp.dll for the ASCII bytes of
"http://127.0.0.1:9700" and reported FAIL. The build was fine: .NET stores string
literals in the #US heap as UTF-16LE. probe_dll_literal.py proved it:

    ascii  hit : False
    utf16  hit : True      (first occurrence at 0x8BEC)
    class 'FloatingBrainRenderer' ascii: True

Searching the wrong encoding and then reporting a build defect is exactly the
failure mode to avoid, so the fix is in the tool.
Idempotent.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\verify_unity_runtime_contract.py"
src = open(PATH, encoding="utf-8").read()

if "utf-16-le" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''dll = open(DLL, "rb").read()
needle = b"http://127.0.0.1:9700"
has_url = needle in dll
print(f"[{'PASS' if has_url else 'FAIL'}] baseUrl string present in Assembly-CSharp.dll")
ok &= has_url'''

NEW = '''dll = open(DLL, "rb").read()
# .NET stores string literals in the #US heap as UTF-16LE, not ASCII. Searching for
# ASCII bytes here produced a false FAIL once already -- see probe_dll_literal.py.
target = "http://127.0.0.1:9700"
has_url = target.encode("utf-16-le") in dll
print(f"[{'PASS' if has_url else 'FAIL'}] baseUrl literal present in Assembly-CSharp.dll "
      f"(utf-16le; ascii would be a false negative)")
ok &= has_url'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: dll search block")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: URL search now uses UTF-16LE")
