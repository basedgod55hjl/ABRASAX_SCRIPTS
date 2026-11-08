import hashlib, json, os, re, subprocess, sys

TREE = r"C:\ABRASAX"
PY = sys.executable
RUNS = 3

seeds, artifacts, digests = [], [], []
for i in range(RUNS):
    cp = subprocess.run([PY, os.path.join(TREE, "tools", "fusion_chain.py")],
                        cwd=TREE, capture_output=True, text=True, timeout=300)
    out = (cp.stdout or "") + (cp.stderr or "")
    m = re.search(r"seed=(JEV7D-[0-9a-f]+)", out)
    a = re.search(r"artifact:\s*(\S+\.png)", out)
    passed = "7/7 stages passed" in out
    seeds.append(m.group(1) if m else None)
    artifacts.append(a.group(1) if a else None)
    if a and os.path.exists(a.group(1)):
        digests.append(hashlib.sha256(open(a.group(1), "rb").read()).hexdigest())
    else:
        digests.append(None)
    print("run %d exit=%s passed=%s seed=%s" % (i + 1, cp.returncode, passed,
                                                (m.group(1)[:30] + "...") if m else None))

uniq_seeds = sorted(set(s for s in seeds if s))
uniq_digest = sorted(set(d for d in digests if d))

print()
print("seeds     :", len(uniq_seeds), "unique of", RUNS)
print("artifacts :", len(uniq_digest), "unique sha256 of", RUNS)
print()
if len(uniq_seeds) == 1:
    print("REPRODUCIBLE: %d runs -> 1 seed  %s" % (RUNS, uniq_seeds[0][:34] + "..."))
else:
    print("NOT REPRODUCIBLE: %d distinct seeds" % len(uniq_seeds))
    for s in uniq_seeds:
        print("   ", s[:40])

json.dump({"runs": RUNS, "seeds": seeds, "digests": digests},
          open(os.path.join(TREE, "logs", "fusion_repro.json"), "w"), indent=2)
