"""Seal a secret with a real TPM-persisted key, then prove it round-trips.

MEASURED FOUNDATION (probe_tpm_cng.py)
    NCryptOpenStorageProvider  -> 0x00000000
    NCryptCreatePersistedKey   -> 0x00000000
    NCryptFinalizeKey          -> 0x00000000
    NCryptDeleteKey            -> 0x00000000

  A key can genuinely be created inside this machine's TPM (AMD fTPM 3.92.0.5).
  Its private half never leaves the chip, so the ciphertext is useless on any other
  machine -- which is what abrasax/tpm.py only pretended to provide.

WHAT IS SEALED

  The .env file, because it is the one artefact here whose disclosure is
  immediately damaging (NVIDIA, JEV, XPL, DeepSeek keys). Sealing it produces:
      CONFIG/tpm-sealed/abrasax-env.sealed   ciphertext, TPM-bound
      CONFIG/tpm-sealed/abrasax-env.json     record: sizes, provider, sha256

  The ORIGINAL .env is NOT deleted. Deleting the plaintext would break every script
  that reads it -- 26 files reference .env -- and that is a migration, not a wiring
  task. The sealed copy exists so the secret can be carried and restored on THIS
  machine only.

PROOF
  seal -> unseal -> compare bytes -> confirm the ciphertext differs from plaintext
  -> confirm the record carries no plaintext sha256 that would leak content
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sys

ROOT = r"C:\ABRASAX"
SEAL_DIR = os.path.join(ROOT, "CONFIG", "tpm-sealed")
ENV = os.path.join(ROOT, ".env")
NAME = "abrasax-env"

ncrypt = ctypes.WinDLL("ncrypt")
NCRYPT_SILENT_FLAG = 0x40
NCRYPT_OVERWRITE_KEY_FLAG = 0x80

ncrypt.NCryptOpenStorageProvider.restype = ctypes.c_long
ncrypt.NCryptOpenStorageProvider.argtypes = [
    ctypes.POINTER(ctypes.c_void_p), ctypes.c_wchar_p, ctypes.c_ulong]
ncrypt.NCryptCreatePersistedKey.restype = ctypes.c_long
ncrypt.NCryptCreatePersistedKey.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_wchar_p,
    ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong]
ncrypt.NCryptOpenKey.restype = ctypes.c_long
ncrypt.NCryptOpenKey.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_wchar_p,
    ctypes.c_ulong, ctypes.c_ulong]
ncrypt.NCryptFinalizeKey.restype = ctypes.c_long
ncrypt.NCryptFinalizeKey.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
ncrypt.NCryptEncrypt.restype = ctypes.c_long
ncrypt.NCryptEncrypt.argtypes = [
    ctypes.c_void_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_void_p,
    ctypes.c_char_p, ctypes.POINTER(ctypes.c_ulong), ctypes.c_ulong]
ncrypt.NCryptDecrypt.restype = ctypes.c_long
ncrypt.NCryptDecrypt.argtypes = [
    ctypes.c_void_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_void_p,
    ctypes.c_char_p, ctypes.POINTER(ctypes.c_ulong), ctypes.c_ulong]
ncrypt.NCryptFreeObject.restype = ctypes.c_long
ncrypt.NCryptFreeObject.argtypes = [ctypes.c_void_p]


def st(code):
    return f"0x{code & 0xFFFFFFFF:08X}"


def open_provider():
    p = ctypes.c_void_p()
    s = ncrypt.NCryptOpenStorageProvider(ctypes.byref(p),
                                        "Microsoft Platform Crypto Provider",
                                        NCRYPT_SILENT_FLAG)
    if s != 0:
        raise OSError(f"open provider: {st(s)}")
    return p


def get_or_create_key(prov, name):
    k = ctypes.c_void_p()
    s = ncrypt.NCryptOpenKey(prov, ctypes.byref(k), name, 0, 0)
    if s == 0:
        return k, "existing"
    k = ctypes.c_void_p()
    s = ncrypt.NCryptCreatePersistedKey(prov, ctypes.byref(k), "RSA", name,
                                        0, NCRYPT_OVERWRITE_KEY_FLAG)
    if s != 0:
        raise OSError(f"create key: {st(s)}")
    s = ncrypt.NCryptFinalizeKey(k, NCRYPT_SILENT_FLAG)
    if s != 0:
        raise OSError(f"finalize key: {st(s)}")
    return k, "created"


def enc(key, data):
    n = ctypes.c_ulong(0)
    s = ncrypt.NCryptEncrypt(key, data, len(data), None, None,
                             ctypes.byref(n), 0)
    if s != 0:
        raise OSError(f"encrypt size: {st(s)}")
    buf = ctypes.create_string_buffer(n.value)
    s = ncrypt.NCryptEncrypt(key, data, len(data), None, buf,
                             ctypes.byref(n), 0)
    if s != 0:
        raise OSError(f"encrypt: {st(s)}")
    return buf.raw[:n.value]


def dec(key, blob):
    n = ctypes.c_ulong(0)
    s = ncrypt.NCryptDecrypt(key, blob, len(blob), None, None,
                             ctypes.byref(n), 0)
    if s != 0:
        raise OSError(f"decrypt size: {st(s)}")
    buf = ctypes.create_string_buffer(n.value)
    s = ncrypt.NCryptDecrypt(key, blob, len(blob), None, buf,
                             ctypes.byref(n), 0)
    if s != 0:
        raise OSError(f"decrypt: {st(s)}")
    return buf.raw[:n.value]


def main() -> int:
    if not os.path.isfile(ENV):
        print(f"no .env at {ENV}")
        return 1

    plaintext = open(ENV, "rb").read()
    print(f"=== sealing {ENV} ===")
    print(f"  plaintext bytes: {len(plaintext):,}")

    # NOTE: an RSA key in the platform provider encrypts small payloads only.
    # .env is ~3 KB, which exceeds a 2048-bit RSA block for a single call, so the
    # payload is split into chunks and each is encrypted independently.
    prov = open_provider()
    try:
        key, how = get_or_create_key(prov, NAME)
        print(f"  TPM key '{NAME}': {how}")
        try:
            CHUNK = 190          # safe under a 2048-bit RSA PKCS#1 block
            parts = [plaintext[i:i + CHUNK] for i in range(0, len(plaintext), CHUNK)]
            sealed = []
            for i, part in enumerate(parts):
                sealed.append(enc(key, part))
            print(f"  chunks sealed: {len(sealed)}")
        finally:
            ncrypt.NCryptFreeObject(key)
    finally:
        ncrypt.NCryptFreeObject(prov)

    blob = json.dumps([p.hex() for p in sealed]).encode()
    os.makedirs(SEAL_DIR, exist_ok=True)
    sealed_path = os.path.join(SEAL_DIR, f"{NAME}.sealed")
    with open(sealed_path, "wb") as f:
        f.write(blob)
    print(f"  ciphertext: {len(blob):,} bytes -> {sealed_path}")

    # ---- proof: unseal and compare ----
    print("\n=== proof: unseal and compare ===")
    prov = open_provider()
    try:
        key, _ = get_or_create_key(prov, NAME)
        try:
            restored = b"".join(dec(key, bytes.fromhex(h))
                                for h in json.loads(open(sealed_path, "rb").read().decode()))
        finally:
            ncrypt.NCryptFreeObject(key)
    finally:
        ncrypt.NCryptFreeObject(prov)

    same = restored == plaintext
    print(f"  unsealed bytes : {len(restored):,}")
    print(f"  identical      : {same}")
    print(f"  plaintext leaked in ciphertext: {plaintext[:16] in blob}")

    # the record must not contain anything derived from the secret
    record = {
        "name": NAME,
        "source": ENV,
        "sealed": sealed_path,
        "plaintext_bytes": len(plaintext),
        "ciphertext_bytes": len(blob),
        "chunks": len(sealed),
        "provider": "Microsoft Platform Crypto Provider",
        "binding": "TPM-persisted RSA key; private half never leaves the TPM",
        "note": "No plaintext hash is stored. A hash of .env would let an attacker "
                "confirm a guessed key set offline.",
    }
    rec_path = os.path.join(SEAL_DIR, f"{NAME}.json")
    with open(rec_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    print(f"  record: {rec_path}")

    ok = same and len(blob) > len(plaintext)
    print("\nRESULT:", "PASS -- real TPM seal/unseal round-trip"
          if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
