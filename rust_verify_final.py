import ctypes

dll = r"C:\Users\sirch\Desktop\ABRASAX\rust_core\target\release\rust_hydrator.dll"
lib = ctypes.CDLL(dll)

# Get connect all report directly from Rust
lib.hydrator_connect_all.restype = ctypes.c_void_p
ptr = lib.hydrator_connect_all()
report = ctypes.c_char_p(ptr).value.decode()
lib.hydrator_free_string(ctypes.c_char_p(ptr))

print(report)
