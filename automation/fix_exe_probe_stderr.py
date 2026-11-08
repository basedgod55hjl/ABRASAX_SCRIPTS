import io, os, shutil

P = r"C:\ABRASAX\SCRIPTS\automation\supervisor.py"
src = io.open(P, encoding="utf-8").read()

OLD = '''        cp = _sp.run([str(path), "--version"], cwd=str(path.parent),
                     capture_output=True, timeout=8)
        if cp.returncode != 0 and not (cp.stdout or b"").strip():
            reason = "exit 0x%08X" % (cp.returncode & 0xFFFFFFFF)
'''

NEW = '''        cp = _sp.run([str(path), "--version"], cwd=str(path.parent),
                     capture_output=True, timeout=8)
        # llama.cpp writes its banner to STDERR ("version: 0.7.0-dev"), so
        # checking stdout alone reported a healthy binary as broken. Measured
        # 2026-11-01: that false block kept :8083 disabled even though the
        # service serves real completions at ~130 tok/s.
        spoke = bool((cp.stdout or b"").strip() or (cp.stderr or b"").strip())
        if cp.returncode != 0 and not spoke:
            reason = "exit 0x%08X" % (cp.returncode & 0xFFFFFFFF)
'''

if OLD not in src:
    raise SystemExit("ANCHOR NOT FOUND")
if "spoke =" in src:
    raise SystemExit("already patched")

src = src.replace(OLD, NEW, 1)
bak = P + ".bak-exeprobe3"
if not os.path.exists(bak):
    shutil.copy2(P, bak)
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("patched", P)
