import re, json, os, subprocess
from collections import defaultdict

with open(r"C:\Users\sirch\Desktop\ALL_VIDEOS_BY_SIZE.xspf", "r", encoding="utf-8") as f:
    content = f.read()

tracks = re.findall(r'<location>file:///(.+?)</location>', content)

by_name = defaultdict(list)
for loc in tracks:
    fn = loc.split("\\")[-1]
    res_m = re.search(r'\((\d+)\)', fn)
    res = int(res_m.group(1)) if res_m else 0
    by_name[fn].append((loc, res))

best = {}
for fn, versions in by_name.items():
    versions.sort(key=lambda x: -x[1])
    best[fn] = versions[0][0]

high_res = [(fn, path) for fn, path in best.items() 
            if any(x in fn for x in ["(2160)", "(1440)", "(1080)", "(720)"])]

print("High-res files to check: {}".format(len(high_res)))

ffprobe = r"C:\ProgramData\chocolatey\bin\ffprobe.exe"
check_results = []
for fn, path in high_res:
    exists = os.path.exists(path)
    if not exists:
        check_results.append({"file": fn, "path": path, "status": "MISSING"})
        continue
    
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", 
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode == 0 and result.stdout.strip():
            duration = float(result.stdout.strip())
            size_mb = os.path.getsize(path) / (1024*1024)
            check_results.append({
                "file": fn, "path": path, "status": "OK",
                "duration_s": round(duration, 1),
                "size_mb": round(size_mb, 1)
            })
        else:
            check_results.append({
                "file": fn, "path": path, "status": "CORRUPTED",
                "error": result.stderr.strip()[:200]
            })
    except Exception as e:
        check_results.append({
            "file": fn, "path": path, "status": "ERROR",
            "error": str(e)[:200]
        })

ok = [r for r in check_results if r["status"] == "OK"]
corrupted = [r for r in check_results if r["status"] == "CORRUPTED"]
missing = [r for r in check_results if r["status"] == "MISSING"]

print()
print("=== INTEGRITY CHECK RESULTS ===")
print("OK: {}".format(len(ok)))
print("CORRUPTED: {}".format(len(corrupted)))
print("MISSING: {}".format(len(missing)))

for c in corrupted:
    print("  CORRUPT: {} -> {}".format(c["file"], c.get("error","")[:80]))

with open(r"C:\Users\sirch\Desktop\VIDEO_INTEGRITY_REPORT.json", "w") as f:
    json.dump({
        "checked": len(check_results), 
        "ok": len(ok), 
        "corrupted": len(corrupted), 
        "missing": len(missing), 
        "details": check_results
    }, f, indent=2)

print()
print("Report saved to VIDEO_INTEGRITY_REPORT.json")
