import sys

sys.path.insert(0, r"C:\ABRASAX")
from abrasax import services

ids = [s["id"] for s in services.SERVICES]
print("overlay registered :", "floating-brain-overlay" in ids)
print("frame server       :", "floating-brain" in ids)
print("service count      :", len(ids))
rows = services.health(timeout=0.6)
by = {r["id"]: r for r in rows}
for sid in ("floating-brain-overlay", "floating-brain", "abrasax-brain"):
    r = by.get(sid)
    print(f"  {sid:24} {r}")
