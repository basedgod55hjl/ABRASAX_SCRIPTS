import ctypes
import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:\abrasax\SCRIPTS\automation")
import abrasax_singleton as s  # noqa: E402

lock = Path(r"C:\abrasax\LOGS\locks\host.lock")
lock.parent.mkdir(parents=True, exist_ok=True)
lock.write_text(json.dumps({"pid": 6988, "role": "host",
                            "started": "2026-11-01T02:58:01Z",
                            "cmdline": r"C:\abrasax\host.py"}), encoding="utf-8")

k = ctypes.windll.kernel32
k.OpenProcess.restype = ctypes.c_void_p
k.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
alive = bool(k.OpenProcess(0x1000, 0, 6988))
print("pid 6988 alive ->", alive)
print("created_epoch(6988) ->", s._proc_created_epoch(6988))
print("lock_started_epoch ->", s._lock_started_epoch(json.loads(lock.read_text(encoding='utf-8'))))
print("holder('host') ->", s.holder("host"))
print("claim('host') ->", s.claim("host"))
print("holder after claim ->", {k2: v for k2, v in (s.holder('host') or {}).items() if k2 != 'cmdline'})
s.release("host")
lock.unlink(missing_ok=True)
print("cleaned, lock exists ->", lock.exists())
