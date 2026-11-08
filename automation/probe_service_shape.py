"""Find out what list_services() actually returns, so the reconciliation is right.

reconcile_ports.py reported "1 in catalog" while 12 services are demonstrably
running. Either list_services() returns a shape my code does not read, or the import
failed silently and CATALOG was empty except for the port I add by hand (9700).

That is the twenty-third false reading of the night and it makes the whole
reconciliation useless: every listening port shows as "not in catalog".
"""
import sys

sys.path.insert(0, r"C:\ABRASAX")

try:
    from abrasax.services import list_services
    print("import ok:", list_services)
except Exception as e:  # noqa: BLE001
    print("import FAILED:", type(e).__name__, e)
    sys.exit(0)

try:
    svc = list_services()
except Exception as e:  # noqa: BLE001
    print("call FAILED:", type(e).__name__, e)
    sys.exit(0)

print("type:", type(svc).__name__)
try:
    print("len :", len(svc))
except TypeError:
    print("len : (no len)")

if isinstance(svc, dict):
    print("dict keys:", list(svc)[:12])
    k = next(iter(svc))
    print("sample value type:", type(svc[k]).__name__)
    print("sample value:", repr(svc[k])[:300])
elif isinstance(svc, (list, tuple)):
    print("first element type:", type(svc[0]).__name__ if svc else "empty")
    if svc:
        print("first element:", repr(svc[0])[:300])
else:
    print("repr:", repr(svc)[:400])

# extract ports the way any sensible consumer would
def ports_from(obj):
    out = set()
    def walk(o, depth=0):
        if depth > 4:
            return
        if isinstance(o, dict):
            for k, v in o.items():
                kl = str(k).lower()
                if kl in ("port", "default_port", "listen_port", "http_port"):
                    try:
                        out.add(int(v))
                    except (TypeError, ValueError):
                        pass
                elif kl == "ports" and isinstance(v, (list, tuple, set)):
                    for x in v:
                        try:
                            out.add(int(x))
                        except (TypeError, ValueError):
                            pass
                else:
                    walk(v, depth + 1)
        elif isinstance(o, (list, tuple)):
            for x in o:
                walk(x, depth + 1)
        elif isinstance(o, (int, str)):
            pass
    walk(obj)
    return out

ports = ports_from(svc)
print("\nports discovered:", sorted(ports))
print("count:", len(ports))
