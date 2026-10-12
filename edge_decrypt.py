import sqlite3, os, json, base64, struct

# Read the Edge encrypted key from Local State
with open(r"C:\Users\osiris_admin\AppData\Local\Microsoft\Edge\User Data\Local State", "r") as f:
    local_state = json.load(f)
encrypted_key_b64 = local_state["os_crypt"]["encrypted_key"]
encrypted_key = base64.b64decode(encrypted_key_b64)
print("Encrypted key length: %d" % len(encrypted_key))
print("Header: %s" % encrypted_key[:5].hex())
ciphertext = encrypted_key[5:]
print("Ciphertext length: %d" % len(ciphertext))

# Try to query the SQLite database
db_path = r"C:\Users\sirch\Desktop\login_data_copy.db"
if not os.path.exists(db_path):
    print("DB file not found!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get table schema
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables: %s" % [t[0] for t in tables])

# Check logins table
cursor.execute("PRAGMA table_info(logins)")
cols = cursor.fetchall()
print("Logins columns: %s" % [(c[1], c[2]) for c in cols])

# Get count and sample
cursor.execute("SELECT COUNT(*) FROM logins")
count = cursor.fetchone()[0]
print("Total saved logins: %d" % count)

if count > 0:
    cursor.execute("SELECT id, origin_url, username_value, password_value FROM logins LIMIT 10")
    rows = cursor.fetchall()
    for row in rows:
        print("")
        print("  ID: %d" % row[0])
        print("  URL: %s" % row[1][:80] if row[1] else "None")
        print("  Username: %s" % row[2])
        pw = row[3]
        print("  Encrypted password length: %d bytes" % len(pw))
        if len(pw) > 3:
            print("  Password hex (first 48): %s" % pw[:48].hex())
            print("  Version/Nonce: %s" % pw[:3].hex())
conn.close()
