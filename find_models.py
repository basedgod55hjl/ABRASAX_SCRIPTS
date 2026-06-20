import os

search_paths = [
    r"C:\Users\BASEDGOD\Desktop\ABRASAX",
    r"C:\Users\BASEDGOD\Desktop\ABRASAX AGI",
    r"C:\Users\BASEDGOD\Desktop"
]

for base in search_paths:
    if not os.path.exists(base):
        continue
    print("Searching: %s" % base)
    for root, dirs, files in os.walk(base):
        for f in files:
            if f.endswith('.gguf'):
                fp = os.path.join(root, f)
                try:
                    size = os.path.getsize(fp)
                    size_gb = size / (1024**3)
                    if size > 1000000:
                        print("  %s (%.2f GB)" % (fp, size_gb))
                except:
                    pass
        # Don't go too deep
        depth = root.replace(base, '').count(os.sep)
        if depth > 5:
            dirs.clear()
