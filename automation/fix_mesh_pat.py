import io, os, shutil

P = r"C:\ABRASAX\SCRIPTS\automation\mesh_runner.py"
src = io.open(P, encoding="utf-8").read()

OLD = '''    # ---- GitHub ---------------------------------------------------------
    pat = os.environ.get("ABRASAX_GH_PAT") or env.get("GITHUB_PAT") or env.get("GH_PAT")
    if pat:
        mesh_log.probe_http("github:api", "https://api.github.com/user",
                            headers={"Authorization": "Bearer " + pat,
                                     "Accept": "application/vnd.github+json",
                                     "User-Agent": "abrasax-mesh"},
                            timeout=30, expect="json")
    else:
        mesh_log.blocker("github:api", "no GitHub PAT in env")
'''

NEW = '''    # ---- GitHub ---------------------------------------------------------
    pat = (os.environ.get("ABRASAX_GH_PAT") or env.get("GITHUB_PAT")
           or env.get("GH_PAT") or env.get("GITHUB_TOKEN"))
    if pat:
        mesh_log.probe_http("github:api", "https://api.github.com/user",
                            headers={"Authorization": "Bearer " + pat,
                                     "Accept": "application/vnd.github+json",
                                     "User-Agent": "abrasax-mesh"},
                            timeout=30, expect="json")
    else:
        mesh_log.blocker("github:api", "no GitHub PAT in env")
'''

if OLD not in src:
    raise SystemExit("ANCHOR NOT FOUND")
src = src.replace(OLD, NEW, 1)

# The PAT supplied for this session is passed in the environment by the caller.
bak = P + ".bak-pat"
if not os.path.exists(bak):
    shutil.copy2(P, bak)
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("patched mesh_runner")
