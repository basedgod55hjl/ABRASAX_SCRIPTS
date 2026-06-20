#!/usr/bin/env python3
import re, os
from pathlib import Path

xspf = Path(r"C:\Users\BASEDGOD\Desktop\_SCRIPTS\vlc\playlists\ehgeh.xspf")
content = xspf.read_text(encoding="utf-8")
locations = re.findall(r"<location>(.*?)</location>", content)
videos = []
for loc in locations:
    path = loc.replace("file:///", "").replace("/", "\\")
    videos.append(path)

print(f"Total tracks: {len(videos)}")
missing = []
existing = []
part_files = []
for v in videos:
    if ".part" in v.lower():
        part_files.append(v)
        continue
    if not os.path.exists(v):
        missing.append(v)
    else:
        existing.append(v)

print(f"Existing: {len(existing)}")
print(f"Missing: {len(missing)}")
print(f"Partial downloads (.part): {len(part_files)}")
if missing:
    print(f"\nFirst 15 missing:")
    for m in missing[:15]:
        print(f"  {m}")
if part_files:
    print(f"\nFirst 10 .part files:")
    for p in part_files[:10]:
        print(f"  {p}")
