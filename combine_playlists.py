import os, xml.etree.ElementTree as ET, hashlib, json
from datetime import datetime

playlist_dir = r'C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX_SCRIPTS\vlc\playlists'
output_file = os.path.join(playlist_dir, 'VLC_ABRASAX_MASTER_COMBINED.xspf')

seen = set()
all_tracks = []
stats = {'files_processed': 0, 'tracks_found': 0, 'duplicates_skipped': 0}

for fname in sorted(os.listdir(playlist_dir)):
    if not fname.endswith('.xspf'):
        continue
    fpath = os.path.join(playlist_dir, fname)
    stats['files_processed'] += 1
    try:
        tree = ET.parse(fpath)
        root = tree.getroot()
        ns = {'ns': 'http://xspf.org/ns/0/'}
        track_list = root.find('.//ns:trackList', ns)
        if track_list is None:
            track_list = root.find('.//trackList')
        if track_list is None:
            print(f'  WARN: No trackList in {fname}')
            continue
        for track in track_list.findall('track'):
            location = track.find('location')
            if location is not None and location.text:
                loc = location.text.strip()
                h = hashlib.md5(loc.encode()).hexdigest()
                if h not in seen:
                    seen.add(h)
                    all_tracks.append(track)
                    stats['tracks_found'] += 1
                else:
                    stats['duplicates_skipped'] += 1
    except Exception as e:
        print(f'  ERROR parsing {fname}: {e}')

# Build new XSPF
ns_uri = 'http://xspf.org/ns/0/'
ET.register_namespace('', ns_uri)
new_root = ET.Element('{' + ns_uri + '}playlist', version='1')
new_root.set('xmlns', ns_uri)
title = ET.SubElement(new_root, '{' + ns_uri + '}title')
title.text = 'ABRASAX MASTER COMBINED - {} tracks - {}'.format(
    stats['tracks_found'], datetime.now().strftime('%Y-%m-%d %H:%M'))
track_list = ET.SubElement(new_root, '{' + ns_uri + '}trackList')
for t in all_tracks:
    track_list.append(t)

tree_out = ET.ElementTree(new_root)
tree_out.write(output_file, encoding='utf-8', xml_declaration=True)
print(json.dumps(stats, indent=2))
print('MASTER PLAYLIST: ' + output_file)
print('Size: {} bytes'.format(os.path.getsize(output_file)))
