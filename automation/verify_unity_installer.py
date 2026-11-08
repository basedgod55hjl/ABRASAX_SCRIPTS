"""Verify the Unity installer binary's integrity and signature.

The installer spins at ~130 CPU-seconds-per-25s while writing 0 bytes, and does
not even exit for --version. Before concluding the environment is at fault, the
binary itself has to be proven good.
"""
import hashlib
import subprocess
import sys

PATH = r"C:\ABRASAX\BUILD\installers\UnitySetup64-6000.6.6f1.exe"
EXPECTED_SIZE = 3856567088

import os
size = os.path.getsize(PATH)
h = hashlib.sha256()
with open(PATH, "rb") as f:
    for chunk in iter(lambda: f.read(1 << 20), b""):
        h.update(chunk)

print(f"path      : {PATH}")
print(f"size      : {size:,} (expected {EXPECTED_SIZE:,}) match={size == EXPECTED_SIZE}")
print(f"sha256    : {h.hexdigest()}")

# First bytes identify the packer: MZ header then the runtime.
with open(PATH, "rb") as f:
    head = f.read(64)
print(f"magic     : {head[:2]!r} (MZ expected)")

ps = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     f"$s=Get-AuthenticodeSignature '{PATH}'; \"status=\" + $s.Status; "
     f"\"signer=\" + $s.SignerCertificate.Subject"],
    capture_output=True, text=True)
print(ps.stdout.strip() or ps.stderr.strip())

ok = size == EXPECTED_SIZE and head[:2] == b"MZ" and "Valid" in ps.stdout
print("\nRESULT:", "installer binary is INTACT" if ok else "installer binary may be damaged")
sys.exit(0)
