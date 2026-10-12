import re, json, os
from collections import Counter, defaultdict

with open(r"C:\Users\sirch\Desktop\ALL_VIDEOS_BY_SIZE.xspf", "r", encoding="utf-8") as f:
    content = f.read()

tracks_raw = re.findall(r'<location>file:///(.+?)</location>', content)

print("=== MASTER PLAYLIST ANALYSIS ===")
print(f"Total tracks in XSPF: {len(tracks_raw)}")

parsed = []
missing_count = 0

for loc in tracks_raw:
    path = loc
    filename = path.split('\\')[-1] if '\\' in path else path.split('/')[-1]
    res_match = re.search(r'\((\d+)\)', filename)
    resolution = int(res_match.group(1)) if res_match else 0
    drive = path[0] if len(path) > 0 else "?"
    exists = os.path.exists(path)
    size = os.path.getsize(path) if exists else 0
    parsed.append({
        'path': path, 'filename': filename,
        'resolution': resolution, 'drive': drive,
        'exists': exists, 'size': size,
        'size_mb': round(size / (1024*1024), 2)
    })
    if not exists:
        missing_count += 1

res_counts = Counter(p['resolution'] for p in parsed)
print("\n=== BY RESOLUTION ===")
for res in sorted(res_counts.keys(), reverse=True):
    count = res_counts[res]
    valid = sum(1 for p in parsed if p['resolution'] == res and p['exists'])
    print(f"  {res}p: {count} total ({valid} exist)")

drive_counts = Counter(p['drive'] for p in parsed)
print("\n=== BY DRIVE ===")
for d in sorted(drive_counts.keys()):
    valid = sum(1 for p in parsed if p['drive'] == d and p['exists'])
    print(f"  {d}:\\ -> {drive_counts[d]} listed ({valid} exist)")

filename_map = defaultdict(list)
for p in parsed:
    filename_map[p['filename']].append(p)
duplicates = {k: v for k, v in filename_map.items() if len(v) > 1}
print(f"\n=== DUPLICATES: {len(duplicates)} files with multiple copies ===")

total_size = sum(p['size'] for p in parsed if p['exists'])
print("\n=== STORAGE ===")
existing = sum(1 for p in parsed if p['exists'])
print(f"  Existing files: {existing}")
print(f"  Missing files: {missing_count}")
print(f"  Total size of existing: {total_size / (1024**3):.2f} GB")
if existing > 0:
    print(f"  Avg file size: {total_size / existing / (1024**3):.3f} GB")

print("\n=== BUILDING DEDUPLICATED MASTER ===")
best_versions = {}
for fname, versions in filename_map.items():
    existing_v = [v for v in versions if v['exists']]
    if not existing_v:
        best_versions[fname] = versions[0]
    else:
        existing_v.sort(key=lambda x: (-x['resolution'], -x['size']))
        best_versions[fname] = existing_v[0]

master_list = sorted(best_versions.values(), key=lambda x: (-x['resolution'], -x['size']))
print(f"  Master playlist: {len(master_list)} unique tracks")

stats = {
    'total_in_original': len(tracks_raw),
    'unique_files': len(set(p['filename'] for p in parsed)),
    'master_tracks': len(master_list),
    'duplicates_removed': len(tracks_raw) - len(master_list),
    'missing_files': missing_count,
    'existing_files': existing,
    'by_resolution': {str(k): v for k, v in sorted(res_counts.items(), reverse=True)},
    'by_drive': dict(drive_counts),
    'total_size_gb': round(total_size / (1024**3), 2),
}

with open(r"C:\Users\sirch\Desktop\PLAYLIST_STATS.json", "w") as f:
    json.dump(stats, f, indent=2)
print("Stats saved to PLAYLIST_STATS.json")

xspf_parts = []
xspf_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
xspf_parts.append('<playlist xmlns="http://xspf.org/ns/0/" xmlns:vlc="http://www.videolan.org/vlc/playlist/ns/0/" version="1">')
xspf_parts.append('\t<title>ABRASAX MASTER — Deduplicated & Optimized by OSIRISBLXCK</title>')
xspf_parts.append('\t<trackList>')
for i, track in enumerate(master_list):
    xspf_parts.append('\t\t<track>')
    xspf_parts.append(f'\t\t\t<location>file:///{track["path"]}</location>')
    xspf_parts.append(f'\t\t\t<title>{track["filename"]}</title>')
    xspf_parts.append('\t\t\t<extension application="http://www.videolan.org/vlc/playlist/0">')
    xspf_parts.append(f'\t\t\t\t<vlc:id>{i}</vlc:id>')
    xspf_parts.append('\t\t\t</extension>')
    xspf_parts.append('\t\t</track>')
xspf_parts.append('\t</trackList>')
xspf_parts.append('</playlist>')

with open(r"C:\Users\sirch\Desktop\ALL_VIDEOS_MASTER.xspf", "w", encoding="utf-8") as f:
    f.write('\n'.join(xspf_parts))
print(f"Master XSPF saved: {len(master_list)} tracks")
print("\n=== DONE ===")
