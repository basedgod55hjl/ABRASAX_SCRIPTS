import io

for p in (r"C:\ABRASAX\abrasax\fusion.py", r"C:\ABRASAX\tools\fusion_chain.py"):
    s = io.open(p, encoding="utf-8", errors="replace").read()
    print("=" * 24, p, os_size if False else (len(s), "bytes"))
    print(s[:1600])
    print()
