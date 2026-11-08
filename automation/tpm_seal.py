"""Real TPM sealing via the Microsoft Platform Crypto Provider.

WHY THIS EXISTS

  abrasax/tpm.py records TPM metadata and then protects the payload with
  sha256(MachineGuid). Measured: MachineGuid is readable without elevation, so that
  hash is not a secret -- it proves nothing an attacker could not forge. The "tpm"
  mode label describes an inventory, not a binding.

  Measured availability on this host:
      Microsoft Platform Crypto Provider : present
      TPM 2.0 (AMD firmware 3.92.0.5)    : present, ready, enabled, owned
  So a genuine sealed-key binding IS possible.

WHAT THIS DOES

  Uses Windows CNG through ctypes to create a PERSISTED key in the platform TPM
  provider, then encrypt/decrypt with it. A persisted TPM key is bound to the TPM:
  the private half never leaves the chip and cannot be copied to another machine.

  This is honest about its limits:
    * it does NOT claim to defeat an attacker with Administrator on this machine --
      they can use the key too, because that is what a machine-bound key means
    * it DOES make the secret unusable if the file or the record is copied to
      another machine, which sha256(MachineGuid) also does but only by comparison,
      not by cryptography

  Nothing is sealed unless --seal is passed, so importing this module is inert.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import sys

ROOT = r"C:\ABRASAX"
SEAL_DIR = os.path.join(ROOT, "CONFIG", "tpm-sealed")

# --- CNG bindings -------------------------------------------------------
bcrypt = ctypes.WinDLL("bcrypt")
ncrypt = ctypes.WinDLL("ncrypt")

NCRYPT_PROV = ctypes.c_void_p
NCRYPT_KEY = ctypes.c_void_p

NCRYPT_PLATFORM_CRYPTO_PROVIDER = "Microsoft Platform Crypto Provider"
NCRYPT_SILENT_FLAG = 0x00000040
NCRYPT_OVERWRITE_KEY_FLAG = 0x00000080
NCRYPT_MACHINE_KEY_FLAG = 0x00000020
NCRYPT_ALLOW_DECRYPT_FLAG = 0x00000001
NCRYPT_ALLOW_ENCRYPT_FLAG = 0x00000004
NCRYPT_ALLOW_PLAINTEXT_ENCRYPTION_FLAG = 0x00000040

BCRYPT_RSAPRIVATE_BLOB = "RSAPRIVATEBLOB"   # not needed; kept for reference


def _check(status: int, what: str):
    if status != 0:
        raise OSError(f"{what} failed with NTSTATUS 0x{status & 0xFFFFFFFF:08X}")


def open_provider(machine: bool = False) -> NCRYPT_PROV:
    prov = NCRYPT_PROV()
    flags = NCRYPT_SILENT_FLAG | (NCRYPT_MACHINE_KEY_FLAG if machine else 0)
    _check(ncrypt.NCryptOpenStorageProvider(ctypes.byref(prov),
                                            NCRYPT_PLATFORM_CRYPTO_PROVIDER,
                                            flags),
           "NCryptOpenStorageProvider")
    return prov


def create_persisted_key(prov: NCRYPT_PROV, name: str) -> NCRYPT_KEY:
    key = NCRYPT_KEY()
    _check(ncrypt.NCryptCreatePersistedKey(prov, ctypes.byref(key),
                                           "RSA", name, 0,
                                           NCRYPT_OVERWRITE_KEY_FLAG),
           "NCryptCreatePersistedKey")
    _check(ncrypt.NCryptSetProperty(key, "Length", 2048), "set Length") \
        if hasattr(ncrypt, "NCryptSetProperty") else None
    _check(ncrypt.NCryptFinalizeKey(key, NCRYPT_SILENT_FLAG), "NCryptFinalizeKey")
    return key


def encrypt(key: NCRYPT_KEY, data: bytes) -> bytes:
    size = wt.DWORD(0)
    # first call gets the required size
    _check(ncrypt.NCryptEncrypt(key, data, len(data), None, None,
                                ctypes.byref(size), 0), "NCryptEncrypt(size)")
    buf = ctypes.create_string_buffer(size.value)
    _check(ncrypt.NCryptEncrypt(key, data, len(data), None, buf,
                                ctypes.byref(size), 0), "NCryptEncrypt")
    return buf.raw[:size.value]


def decrypt(key: NCRYPT_KEY, blob: bytes) -> bytes:
    size = wt.DWORD(0)
    _check(ncrypt.NCryptDecrypt(key, blob, len(blob), None, None,
                                ctypes.byref(size), 0), "NCryptDecrypt(size)")
    buf = ctypes.create_string_buffer(size.value)
    _check(ncrypt.NCryptDecrypt(key, blob, len(blob), None, buf,
                                ctypes.byref(size), 0), "NCryptDecrypt")
    return buf.raw[:size.value]


def open_persisted_key(prov: NCRYPT_PROV, name: str) -> NCRYPT_KEY:
    key = NCRYPT_KEY()
    _check(ncrypt.NCryptOpenKey(prov, ctypes.byref(key), name, 0, 0),
           f"NCryptOpenKey({name})")
    return key


def seal_file(path: str, name: str) -> dict:
    """Encrypt a file with a TPM-persisted key and store the ciphertext."""
    src = open(path, "rb").read()
    prov = open_provider()
    try:
        try:
            key = create_persisted_key(prov, name)
            created = True
        except OSError:
            key = open_persisted_key(prov, name)
            created = False
        try:
            blob = encrypt(key, src)
        finally:
            ncrypt.NCryptFreeObject(key)
    finally:
        ncrypt.NCryptFreeObject(prov)

    os.makedirs(SEAL_DIR, exist_ok=True)
    out = os.path.join(SEAL_DIR, f"{name}.sealed")
    with open(out, "wb") as f:
        f.write(blob)
    rec = {
        "name": name,
        "source": path,
        "sealed": out,
        "blob_bytes": len(blob),
        "plaintext_bytes": len(src),
        "provider": NCRYPT_PLATFORM_CRYPTO_PROVIDER,
        "key_created": created,
    }
    with open(os.path.join(SEAL_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=2)
    return rec


def unseal_file(name: str) -> bytes:
    prov = open_provider()
    try:
        key = open_persisted_key(prov, name)
        try:
            blob = open(os.path.join(SEAL_DIR, f"{name}.sealed"), "rb").read()
            return decrypt(key, blob)
        finally:
            ncrypt.NCryptFreeObject(key)
    finally:
        ncrypt.NCryptFreeObject(prov)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if cmd == "probe":
        try:
            prov = open_provider()
            ncrypt.NCryptFreeObject(prov)
            print(json.dumps({"provider": "open ok",
                              "name": NCRYPT_PLATFORM_CRYPTO_PROVIDER}))
        except OSError as e:
            print(json.dumps({"provider": "FAILED", "error": str(e)}))
    elif cmd == "seal" and len(sys.argv) > 3:
        print(json.dumps(seal_file(sys.argv[2], sys.argv[3]), indent=2))
    else:
        print("usage: probe | seal <file> <name>")
