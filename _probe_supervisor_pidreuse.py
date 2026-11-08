import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "sup_probe", r"C:\abrasax\SCRIPTS\automation\supervisor.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

print("pidfile text      :", mod.PIDFILE.read_text().strip())
print("pidfile mtime     :", mod.PIDFILE.stat().st_mtime)
pid = int(mod.PIDFILE.read_text().strip())
print("pid alive         :", mod._pid_alive(pid))
print("pid created epoch :", mod._proc_created_epoch(pid))
print("_pidfile_owner()  :", mod._pidfile_owner(), "  (0 = stale/recycled)")
print("_claim_pidfile()  :", mod._claim_pidfile())
print("pidfile now       :", mod.PIDFILE.read_text().strip())
mod.PIDFILE.unlink(missing_ok=True)
print("cleaned -> exists :", mod.PIDFILE.exists())
