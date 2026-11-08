"""Prove test_gateway_model_route.py catches the pre-fix routing bug.

Valid proof requires the old module to LOAD and to be the one under test.
Copy the whole package into a temp dir, restore the ORIGINAL _pick_route there,
then run the new regression file with the temp package shadowing the real one.
"""
import io, os, shutil, subprocess, sys, tempfile

REPO = r"C:\ABRASAX"
SRC = os.path.join(REPO, "abrasax", "gateway.py")
text = io.open(SRC, encoding="utf-8").read()
if "_provider_default_model" not in text:
    raise SystemExit("fix not present - nothing to compare against")

old_pick = '''def _pick_route(payload: dict) -> tuple[str, str | None]:
    model = str(payload.get("model") or "").strip()
    for route in ("lmstudio", "nvidia", "xpl"):
        if model.startswith(route + ":"):
            return route, model.split(":", 1)[1] or None
    extra = payload.get("abrasax") or {}
    route = str(extra.get("route") or "auto")
    if model and model not in {"auto", "abrasax/auto"}:
        return route, model
    return route, None
'''

helper_start = text.index("def _provider_default_model(")
pick_start = text.index("def _pick_route(")
pick_end = text.index("\n\n\n", pick_start)
helper_src = text[helper_start:pick_start]
old_src = text[:helper_start] + helper_src + old_pick + text[pick_end:]

d = tempfile.mkdtemp(prefix="gwregress_")
shutil.copytree(os.path.join(REPO, "abrasax"), os.path.join(d, "abrasax"),
                ignore=shutil.ignore_patterns("__pycache__"))
io.open(os.path.join(d, "abrasax", "gateway.py"), "w",
        encoding="utf-8", newline="\n").write(old_src)

probe = (
    "import sys; sys.path.insert(0, %r); sys.path.insert(1, %r);\n"
    "from abrasax import gateway;\n"
    "assert gateway.__file__.startswith(%r), gateway.__file__;\n"
    "print('module:', gateway.__file__);\n"
    "print('old _pick_route:', gateway._pick_route({'model':'deepseek'}))\n"
) % (d, REPO, d)
chk = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
print(chk.stdout.strip() or "")
if "('auto', 'deepseek')" not in (chk.stdout or ""):
    print("STDERR:", chk.stderr.strip()[-500:])
    shutil.rmtree(d, ignore_errors=True)
    raise SystemExit("temp tree did not reproduce old behaviour - aborting")

t = io.open(os.path.join(REPO, "tests", "test_gateway_model_route.py"),
            encoding="utf-8").read()
t = t.replace(
    r'sys.path.insert(0, r"C:\ABRASAX")',
    "sys.path.insert(0, %r)\nsys.path.insert(1, %r)" % (d, REPO))
io.open(os.path.join(d, "test_old.py"), "w", encoding="utf-8").write(t)

cp = subprocess.run([sys.executable, "-m", "pytest", "test_old.py", "-q",
                     "--no-header", "-p", "no:cacheprovider"],
                    cwd=d, capture_output=True, text=True)
print("pytest exit:", cp.returncode)
lines = [l for l in (cp.stdout or "").splitlines() if l.strip()]
print("\n".join(lines[-9:]))
shutil.rmtree(d, ignore_errors=True)

failed_on_assert = cp.returncode == 1 and "failed" in (cp.stdout or "")
collection_err = "errors" in (cp.stdout or "").lower()
print()
if failed_on_assert and not collection_err:
    print("PROVEN: old _pick_route fails the routing regression tests.")
    sys.exit(0)
print("INCONCLUSIVE: exit=%s collection_err=%s" % (cp.returncode, collection_err))
sys.exit(1)
