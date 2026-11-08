import io, os, shutil

P = r"C:\ABRASAX\abrasax\mesh_log.py"
src = io.open(P, encoding="utf-8").read()

OLD = '''                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                latest[e["name"]] = e
'''

NEW = '''                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                # Only a probe can displace a probe. Otherwise a trailing "note"
                # for the same name (e.g. jev:systemone) hid the probe row and
                # the endpoint silently vanished from the table.
                prev = latest.get(e["name"])
                if e["kind"] == "probe" or prev is None or prev["kind"] != "probe":
                    latest[e["name"]] = e
'''

if OLD not in src:
    raise SystemExit("ANCHOR NOT FOUND")
if "Only a probe can displace" in src:
    raise SystemExit("already patched")

src = src.replace(OLD, NEW, 1)
bak = P + ".bak-latest"
if not os.path.exists(bak):
    shutil.copy2(P, bak)
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("patched", P)
