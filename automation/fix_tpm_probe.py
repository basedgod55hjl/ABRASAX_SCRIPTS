"""Fix the struct.pack call in probe_tpm_encrypt.py.

ctypes.c_ulong has no .to_bytes(); struct.pack("<I", v) is what CNG expects for a
DWORD property value.
"""
import re

PATH = r"C:\ABRASAX\SCRIPTS\automation\probe_tpm_encrypt.py"
src = open(PATH, encoding="utf-8").read()

if "import struct" not in src:
    src = src.replace("import ctypes.wintypes as wt",
                      "import ctypes.wintypes as wt\nimport struct", 1)

src = re.sub(r"return ctypes\.c_ulong\(v\)\.to_bytes\(4,\s*[\"']little[\"']\)",
             'return struct.pack("<I", v)', src)

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("patched: struct.pack")
print("has struct import:", "import struct" in src)
print("has to_bytes:", "to_bytes" in src)
