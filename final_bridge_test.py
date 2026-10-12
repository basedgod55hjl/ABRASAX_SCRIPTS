import ctypes, json

dll = r'C:\Users\sirch\Desktop\ABRASAX\rust_core\target\release\rust_hydrator.dll'
lib = ctypes.CDLL(dll)

def call_rust(fn_name):
    fn = getattr(lib, fn_name)
    fn.restype = ctypes.c_void_p
    ptr = fn()
    if ptr:
        s = ctypes.c_char_p(ptr).value.decode('utf-8') if ptr else ""
        lib.hydrator_free_string(ctypes.c_char_p(ptr))
        return s
    return ""

print("[1] Initializing Rust Hydrator...")
ver = call_rust("hydrator_init")
print(f"  -> {ver}")

print("\n[2] System Status (JSON)...")
status = json.loads(call_rust("hydrator_status"))
print(f"  -> Rust: v{status['rust_hydrator']['version']}")
print(f"  -> GPU:  {status['gpu']['name']} | VRAM: {status['gpu']['vram_used']}/{status['gpu']['vram_total']}")
print(f"  -> RAM:  {status['memory']['used_percent']} | {status['memory']['free_gb']}GB free")
print(f"  -> Processes tracked: {len(status['processes'])}")
print(f"  -> Components: {len(status['components'])}")

print("\n[3] Connect All Components...")
report = call_rust("hydrator_connect_all")
for line in report.split('\n'):
    l = line.strip()
    if l and ('Result' in l or 'STATUS' in l or l.startswith('[')):
        print(f"  {l}")

print("\n[4] Exec via Rust: nvidia-smi...")
lib.hydrator_exec.argtypes = [ctypes.c_char_p]
lib.hydrator_exec.restype = ctypes.c_void_p
ptr = lib.hydrator_exec(b"nvidia-smi --query-gpu=temperature.gpu,utilization.gpu,power.draw,memory.used --format=csv,noheader")
out = ctypes.c_char_p(ptr).value.decode('utf-8')
lib.hydrator_free_string(ctypes.c_char_p(ptr))
print(f"  -> Telemetry: {out.strip()}")

print("\n" + "="*60)
print("ABRASAX RUST-PYTHON-VLC BRIDGE — FULLY OPERATIONAL")
print("PRIMAL_HEX: 4f5349524953424c58434b")
print("PHI: 1.618033988749895")
print("="*60)
