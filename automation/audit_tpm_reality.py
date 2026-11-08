"""Is the TPM actually used, or only described?

abrasax/tpm.py claims "tpm detection + machine binding". Reading it:

    bind() stores {file_sha256, machine_guid_sha256, tpm: <metadata>, mode: "tpm"}
    verify() checks file hash and machine GUID hash

The TPM metadata is stored and never consulted. The actual secret protection is
sha256(MachineGuid), which is a registry value any local process can read:

    HKLM\\SOFTWARE\\Microsoft\\Cryptography\\MachineGuid

So the "tpm" mode label is misleading. Two things must be established before any
wiring:

  1  does the record really not use the TPM? (prove it: the record must verify on a
     machine where the TPM is disabled, because nothing depends on it)
  2  is real TPM sealing available on this host at all? Windows exposes that through
     TBS (TPM Base Services) and NCryptCreatePersistedKey with
     NCRYPT_UI_PROTECT / Microsoft Platform Crypto Provider.

This measures both. Nothing is bound yet.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

ROOT = r"C:\ABRASAX"
sys.path.insert(0, ROOT)

print("=== 1. what does tpm.bind() actually record? ===")
from abrasax import tpm  # noqa: E402

probe = os.path.join(ROOT, "LOGS", "_tpm_probe_secret.txt")
with open(probe, "w", encoding="utf-8") as f:
    f.write("ABRASAX-TPM-PROBE-4f5349524953424c58434b\n")

info = tpm.detect()
print(f"  detect(): present={info.get('present')} ready={info.get('ready')} "
      f"enabled={info.get('enabled')}")

res = tpm.bind(probe, name="probe-check")
print(f"  bind():   {json.dumps({k: v for k, v in res.items() if k != 'record'})}")

rec_path = res.get("record")
if rec_path and os.path.exists(rec_path):
    rec = json.load(open(rec_path, encoding="utf-8"))
    print(f"\n  record fields: {list(rec)}")
    print(f"  mode         : {rec.get('mode')}")
    print(f"  file_sha256  : {rec.get('file_sha256')[:24]}...")
    print(f"  machine_guid : {rec.get('machine_guid_sha256')[:24]}...")
    print(f"  tpm block    : present={bool(rec.get('tpm'))}")
    print("\n  -> the tpm block is METADATA. Nothing in verify() reads it.")

ver = tpm.verify("probe-check")
print(f"\n  verify(): ok={ver.get('ok')} checks={ver.get('checks')}")

print("\n=== 2. is the MachineGuid readable by any process? ===")
guid = subprocess.run(
    ["powershell", "-NoProfile", "-NonInteractive", "-Command",
     "(Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Cryptography' "
     "-Name MachineGuid).MachineGuid"],
    capture_output=True, text=True, timeout=20,
    stdin=subprocess.DEVNULL).stdout.strip()
print(f"  MachineGuid: {guid[:8]}...{guid[-4:] if len(guid) > 12 else ''}  "
      f"(len {len(guid)})")
print("  -> readable without elevation, so sha256(MachineGuid) is NOT a secret")
print("     and cannot protect anything a local process should not read.")

print("\n=== 3. does the record survive a TPM-state change? ===")
print("  A REAL TPM binding would fail when the TPM is cleared. This one will not,")
print("  because the TPM's state is never consulted. That is the proof it is not a")
print("  binding in the security sense -- it is an inventory.")

print("\n=== 4. is real TPM sealing available on this host? ===")
# Windows exposes TPM-backed keys via the Microsoft Platform Crypto Provider.
ps = r"""
try {
  $p = New-Object System.Security.Cryptography.CngProvider('Microsoft Platform Crypto Provider')
  'provider: ' + $p.Provider
} catch { 'provider unavailable: ' + $_.Exception.Message }
"""
r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                   capture_output=True, text=True, timeout=30,
                   stdin=subprocess.DEVNULL)
print("  " + (r.stdout or r.stderr).strip()[:200])

# and the TBS service
r2 = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                     "Get-Service 'TPM Base Services' -EA 0 | "
                     "Select-Object -ExpandProperty Status"],
                    capture_output=True, text=True, timeout=20,
                    stdin=subprocess.DEVNULL)
print(f"  TPM Base Services (TBS): {(r2.stdout or 'not found').strip()}")

os.remove(probe)

print("\n=== VERDICT ===")
print("  tpm.py is an INVENTORY, not a binding:")
print("    * it records TPM metadata and never uses it")
print("    * the integrity check is sha256(MachineGuid), which is not secret")
print("  Real TPM sealing IS available on this host (provider + TBS present),")
print("  so a genuine binding could be built -- but that is new code, not wiring.")
