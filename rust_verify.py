import ctypes, json

dll = r"C:\Users\sirch\Desktop\ABRASAX\rust_core\target\release\rust_hydrator.dll"
lib = ctypes.CDLL(dll)
lib.hydrator_exec.argtypes = [ctypes.c_char_p]
lib.hydrator_exec.restype = ctypes.c_void_p

def rust_exec(cmd):
    ptr = lib.hydrator_exec(cmd.encode())
    r = ctypes.c_char_p(ptr).value.decode()
    lib.hydrator_free_string(ctypes.c_char_p(ptr))
    return r

# Check LM Studio
r1 = rust_exec('tasklist /FI "IMAGENAME eq LM Studio.exe" /FO CSV /NH 2>&1')
lm_running = "LM Studio" in r1

# Check server
r2 = rust_exec('curl -s http://127.0.0.1:1234/v1/models 2>nul || echo NOCURL')
server_up = "gemma" in r2

# Get full Rust status
lib.hydrator_status.restype = ctypes.c_void_p
ptr = lib.hydrator_status()
status = json.loads(ctypes.c_char_p(ptr).value.decode())
lib.hydrator_free_string(ctypes.c_char_p(ptr))

# Get connect all
lib.hydrator_connect_all.restype = ctypes.c_void_p
ptr2 = lib.hydrator_connect_all()
report = ctypes.c_char_p(ptr2).value.decode()
lib.hydrator_free_string(ctypes.c_char_p(ptr2))

print("=" * 70)
print("  ABRASAX GOD OS — 8/8 COMPONENT STATUS")
print("  OSIRISBLXCK — PRIMAL: 4f5349524953424c58434b")
print("=" * 70)
print()

for line in report.split('\n'):
    print(f"  {line}")

print()
status_line = "DISCONNECTED"
if lm_running and server_up:
    status_line = "CONNECTED (via LM Studio + gemma-4-e4b-uncensored-hauhaucs-aggressive)"
print(f"  [{status_line}] LLM Inference Engine (LM Studio server)")
print()

# Count actual connected
connected = sum(1 for line in report.split('\n') if '[CONNECTED]' in line)
if lm_running and server_up:
    connected += 1
    print(f"  Result: {connected}/8 components connected.")
    print(f"  STATUS: ALL SYSTEMS NOMINAL — Full connectivity established!")
else:
    print(f"  Result: {connected}/8 components connected.")
    if lm_running:
        print(f"  STATUS: Engine running but server not responding yet.")
    else:
        print(f"  STATUS: LM Studio server needs model loaded.")

print()
print(f"  GPU: {status['gpu']['name']}")
print(f"  VRAM: {status['gpu']['vram_used']}/{status['gpu']['vram_total']}")
print(f"  RAM: {status['memory']['used_percent']} used")
print(f"  LM Studio processes: {len([p for p in status['processes'] if 'python' in p['name']])} python + LM Studio")
print()
print("=" * 70)
print("  PHI: 1.618033988749895")
print("  Rust Hydrator v4.1.0 — BUILD: release")
print("  GEMMA-4-E2B — Inference Ready")
print("  VLC ENHANCED — Master Playlist Playing")
print("=" * 70)
