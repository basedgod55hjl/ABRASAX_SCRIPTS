"""Probe the TPM provider step by step, printing every NTSTATUS.

Inline ctypes calls produce no output when something fails silently, so this walks
the CNG sequence explicitly and prints the status after each call. If a step fails,
the numeric NTSTATUS is the evidence.
"""
import ctypes
import ctypes.wintypes as wt

ncrypt = ctypes.WinDLL("ncrypt")

NCRYPT_SILENT_FLAG = 0x00000040
NCRYPT_OVERWRITE_KEY_FLAG = 0x00000080

# declare the signatures so failures are visible rather than silent
ncrypt.NCryptOpenStorageProvider.restype = ctypes.c_long
ncrypt.NCryptOpenStorageProvider.argtypes = [ctypes.POINTER(ctypes.c_void_p),
                                             ctypes.c_wchar_p, ctypes.c_ulong]
ncrypt.NCryptCreatePersistedKey.restype = ctypes.c_long
ncrypt.NCryptCreatePersistedKey.argtypes = [ctypes.c_void_p,
                                            ctypes.POINTER(ctypes.c_void_p),
                                            ctypes.c_wchar_p, ctypes.c_wchar_p,
                                            ctypes.c_ulong, ctypes.c_ulong]
ncrypt.NCryptFreeObject.restype = ctypes.c_long
ncrypt.NCryptFreeObject.argtypes = [ctypes.c_void_p]
ncrypt.NCryptFinalizeKey.restype = ctypes.c_long
ncrypt.NCryptFinalizeKey.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
ncrypt.NCryptDeleteKey.restype = ctypes.c_long
ncrypt.NCryptDeleteKey.argtypes = [ctypes.c_void_p, ctypes.c_ulong]


def status(code):
    return f"0x{code & 0xFFFFFFFF:08X}"


print("=== step 1: open the platform provider ===")
prov = ctypes.c_void_p()
st = ncrypt.NCryptOpenStorageProvider(ctypes.byref(prov),
                                     "Microsoft Platform Crypto Provider",
                                     NCRYPT_SILENT_FLAG)
print(f"  NCryptOpenStorageProvider -> {status(st)}")
if st != 0:
    print("  provider cannot be opened; TPM sealing unavailable")
    raise SystemExit(0)
print(f"  handle = {prov.value}")

print("\n=== step 2: create a persisted RSA key inside the TPM ===")
key = ctypes.c_void_p()
st = ncrypt.NCryptCreatePersistedKey(prov, ctypes.byref(key), "RSA",
                                     "abrasax-probe", 0,
                                     NCRYPT_OVERWRITE_KEY_FLAG)
print(f"  NCryptCreatePersistedKey -> {status(st)}")
print(f"  handle = {key.value}")

if st != 0:
    print("  key creation refused. Common causes:")
    print("    0x8009000D NTE_NO_KEY        -- TPM has no key storage available")
    print("    0x80090029 NTE_NOT_SUPPORTED -- provider does not do persisted keys")
    print("    0x80090005 NTE_BAD_DATA")
    ncrypt.NCryptFreeObject(prov)
    raise SystemExit(0)

print("\n=== step 3: finalize (this is where the TPM actually creates it) ===")
st = ncrypt.NCryptFinalizeKey(key, NCRYPT_SILENT_FLAG)
print(f"  NCryptFinalizeKey -> {status(st)}")

if st == 0:
    print("  SUCCESS: a key now exists inside the TPM and is bound to this machine.")
    print("  Cleaning up the probe key ...")
    st_del = ncrypt.NCryptDeleteKey(key, 0)
    print(f"  NCryptDeleteKey -> {status(st_del)}")
else:
    print("  finalize refused -- the key object existed but the TPM would not")
    print("  materialise it. That usually means the TPM is owned by a policy that")
    print("  forbids this provider from creating keys.")
    ncrypt.NCryptFreeObject(key)

ncrypt.NCryptFreeObject(prov)
print("\n  provider handle released")
