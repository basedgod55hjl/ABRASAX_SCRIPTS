import io, os, shutil

P = r"C:\ABRASAX\tests\test_neo_loader.py"
src = io.open(P, encoding="utf-8").read()

OLD = 'ROOT = Path(__file__).resolve().parents[2]\n'
NEW = ('# parents[0] is tests/, parents[1] is the repo root. parents[2] is C:\\ -\n'
       '# measured 2026-11-01: it resolved C:\\SCRIPTS\\tools, so `import neo_loader`\n'
       '# failed collection with ModuleNotFoundError.\n'
       'ROOT = Path(__file__).resolve().parents[1]\n')

if OLD not in src:
    raise SystemExit("ANCHOR NOT FOUND")
if "parents[1]\n" in src and "parents[2]" not in src:
    raise SystemExit("already patched")

src = src.replace(OLD, NEW, 1)
bak = P + ".bak-rootfix"
if not os.path.exists(bak):
    shutil.copy2(P, bak)
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("patched", P)
