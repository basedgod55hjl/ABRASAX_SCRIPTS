"""Fix the silent import failure that made the port reconciliation meaningless.

reconcile_ports.py printed "1 in catalog" while 12 services are running. The cause,
found by probe_service_shape.py:

    list_services() -> list of 16 dicts, ports
    [1234, 8090, 8765, 8766, 8777, 8778, 8795, 9001, 9624, 9625, 9626, 9782]

The import works. My code did:

    try:
        from abrasax.services import list_services
        CATALOG = {s.get('port') for s in list_services() if s.get('port')}
    except Exception:
        CATALOG = set()

and `except Exception` swallowed whatever went wrong -- most likely that
`abrasax.services` needs the repo root on sys.path AND the package import pulls
dependencies that fail in this context. Either way, the failure was invisible and
every listening port was then reported as "not in catalog".

A bare `except Exception: pass` around a data load is how a check becomes a liar.
This version reports the failure loudly and falls back to reading the catalog
through the CLI, which is known to work.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\reconcile_ports.py"
src = open(PATH, encoding="utf-8").read()

if "catalog_source" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''sys.path.insert(0, os.path.join(ROOT, "SCRIPTS", "automation"))
try:
    from abrasax.services import list_services  # type: ignore
    CATALOG = {s.get("port") for s in list_services() if s.get("port")}
except Exception:
    CATALOG = set()

CATALOG |= {9700}          # floating-brain renderer, documented today
CATALOG.discard(None)'''

NEW = '''sys.path.insert(0, os.path.join(ROOT, "SCRIPTS", "automation"))
sys.path.insert(0, ROOT)

catalog_source = None
CATALOG = set()

try:
    from abrasax.services import list_services  # type: ignore
    svc = list_services()
    CATALOG = {int(s["port"]) for s in svc if isinstance(s, dict) and s.get("port")}
    catalog_source = f"abrasax.services.list_services ({len(svc)} entries)"
except Exception as e:
    # Do NOT swallow this. A silent empty catalog made every listening port look
    # undocumented, which invalidated the whole reconciliation.
    print(f"  [WARN] in-process catalog import failed: {type(e).__name__}: {e}")
    print("  [WARN] falling back to the CLI")
    try:
        import subprocess
        r = subprocess.run(
            [sys.executable, "-m", "abrasax", "services"],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
            stdin=subprocess.DEVNULL)
        for line in (r.stdout or "").splitlines():
            parts = line.split()
            for tok in parts:
                if tok.isdigit() and 1000 <= int(tok) <= 65535:
                    CATALOG.add(int(tok))
                    break
        catalog_source = f"CLI (abrasax services), {len(CATALOG)} ports"
    except Exception as e2:  # noqa: BLE001
        print(f"  [ERROR] CLI fallback also failed: {type(e2).__name__}: {e2}")
        catalog_source = "UNAVAILABLE"

CATALOG.add(9700)          # floating-brain renderer, documented today
CATALOG.discard(None)'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: catalog block")
    sys.exit(1)
src = src.replace(OLD, NEW, 1)

src = src.replace(
    'print(f"=== PORT RECONCILIATION ({len(claimed)} claimed, {len(CATALOG)} in catalog) ===")',
    'print(f"=== PORT RECONCILIATION ({len(claimed)} claimed, {len(CATALOG)} in catalog) ===")\n'
    'print(f"  catalog source: {catalog_source}")')

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: catalog failure is loud, with a CLI fallback")
