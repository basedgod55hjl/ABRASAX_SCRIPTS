"""Fix 0x80090027 when encrypting with a TPM-persisted key.

MEASURED
    NCryptOpenStorageProvider  0x00000000
    NCryptCreatePersistedKey   0x00000000
    NCryptFinalizeKey          0x00000000
    NCryptEncrypt (size)       0x80090027   NTE_INVALID_PARAMETER

NTE_INVALID_PARAMETER on the size probe means the key cannot do symmetric-style
encryption at all. A CNG RSA key created with no usage properties defaults to what
the provider permits, and the platform TPM provider does not allow plaintext
encryption with a persisted RSA key by default.

The fix is to set the key's usage policy BEFORE finalizing:
    NCRYPT_KEY_USAGE_PROPERTY        = "Key Usage"
        NCRYPT_ALLOW_DECRYPT_FLAG 0x00000001
        NCRYPT_ALLOW_ENCRYPT_FLAG 0x00000004
        NCRYPT_ALLOW_PLAINTEXT_ENCRYPTION_FLAG 0x00000040   <- the one that matters

Also set the padding to PKCS#1 so plaintext encryption is well-defined:
    BCRYPT_PAD_PKCS1 = 0x00000002  via NCRYPT_PADDING_PROPERTY

This probe finds which combination the platform provider actually accepts, by
trying them and printing each NTSTATUS. It deletes its probe key afterwards.
"""
import ctypes
import ctypes.wintypes as wt
import struct

ncrypt = ctypes.WinDLL("ncrypt")

SILENT = 0x40
OVERWRITE = 0x80
MACHINE = 0x20

ALLOW_DECRYPT = 0x00000001
ALLOW_ENCRYPT = 0x00000004
ALLOW_PLAINTEXT = 0x00000040
PAD_PKCS1 = 0x00000002

for fn, res, args in [
    ("NCryptOpenStorageProvider", ctypes.c_long,
     [ctypes.POINTER(ctypes.c_void_p), ctypes.c_wchar_p, ctypes.c_ulong]),
    ("NCryptCreatePersistedKey", ctypes.c_long,
     [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_wchar_p,
      ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong]),
    ("NCryptSetProperty", ctypes.c_long,
     [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_char_p, ctypes.c_ulong,
      ctypes.c_ulong]),
    ("NCryptFinalizeKey", ctypes.c_long, [ctypes.c_void_p, ctypes.c_ulong]),
    ("NCryptEncrypt", ctypes.c_long,
     [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_void_p,
      ctypes.c_char_p, ctypes.POINTER(ctypes.c_ulong), ctypes.c_ulong]),
    ("NCryptFreeObject", ctypes.c_long, [ctypes.c_void_p]),
    ("NCryptDeleteKey", ctypes.c_long, [ctypes.c_void_p, ctypes.c_ulong]),
]:
    f = getattr(ncrypt, fn)
    f.restype = res
    f.argtypes = args


def st(c):
    return f"0x{c & 0xFFFFFFFF:08X}"


def dword(v):
    return struct.pack("<I", v)


print("=== attempt: set key usage BEFORE finalize ===")
prov = ctypes.c_void_p()
s = ncrypt.NCryptOpenStorageProvider(ctypes.byref(prov),
                                     "Microsoft Platform Crypto Provider", SILENT)
print(f"  open provider      {st(s)}")

key = ctypes.c_void_p()
s = ncrypt.NCryptCreatePersistedKey(prov, ctypes.byref(key), "RSA",
                                    "abrasax-seal-probe", 0, OVERWRITE)
print(f"  create key         {st(s)}")

usage = ALLOW_DECRYPT | ALLOW_ENCRYPT | ALLOW_PLAINTEXT
s = ncrypt.NCryptSetProperty(key, "Key Usage", dword(usage), 4, 0)
print(f"  set Key Usage      {st(s)}  (0x{usage:08X})")

s = ncrypt.NCryptSetProperty(key, "Padding", dword(PAD_PKCS1), 4, 0)
print(f"  set Padding        {st(s)}  (PKCS#1)")

s = ncrypt.NCryptSetProperty(key, "Length", dword(2048), 4, 0)
print(f"  set Length         {st(s)}  (2048)")

s = ncrypt.NCryptFinalizeKey(key, SILENT)
print(f"  finalize           {st(s)}")

if s == 0:
    data = b"ABRASAX-TPM-SEAL-PROBE"
    n = ctypes.c_ulong(0)
    s = ncrypt.NCryptEncrypt(key, data, len(data), None, None, ctypes.byref(n), 0)
    print(f"\n  encrypt (size)     {st(s)}  needed={n.value}")

    if s == 0:
        buf = ctypes.create_string_buffer(n.value)
        s = ncrypt.NCryptEncrypt(key, data, len(data), None, buf,
                                 ctypes.byref(n), 0)
        print(f"  encrypt            {st(s)}  produced={n.value} bytes")
        if s == 0:
            blob = buf.raw[:n.value]
            print(f"  ciphertext[:16]    {blob[:16].hex()}")
            print("\n  RESULT: the TPM key CAN encrypt plaintext with these settings.")
        else:
            print(f"\n  RESULT: encryption refused even after the policy change ({st(s)})")
    else:
        print(f"\n  RESULT: size probe still refused ({st(s)})")
        print("  -> this provider will not do plaintext encryption on a persisted")
        print("     RSA key. TPM sealing of arbitrary data needs TPM2_Create/Seal")
        print("     via TBS, not CNG NCryptEncrypt.")
else:
    print(f"\n  RESULT: key could not be finalized with this policy ({st(s)})")

# cleanup
d = ncrypt.NCryptDeleteKey(key, 0)
print(f"\n  delete probe key   {st(d)}")
ncrypt.NCryptFreeObject(prov)
