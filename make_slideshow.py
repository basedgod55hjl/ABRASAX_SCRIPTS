#!/usr/bin/env python3
import os

aeon_dir = r'C:\Users\sirch\Desktop\ABRASAX\aeon'
out_dir = r'C:\Users\sirch\Desktop'

files = [f for f in os.listdir(aeon_dir) if f.startswith('art_epoch_') and f.endswith('.ppm')]
epochs = []
for f in files:
    parts = f.replace('art_epoch_', '').replace('.ppm', '').split('_', 1)
    epoch_num = int(parts[0])
    seed_name = parts[1] if len(parts) > 1 else 'unknown'
    epochs.append((epoch_num, seed_name, f))
epochs.sort(key=lambda x: x[0])

with open(os.path.join(out_dir, 'slideshow_input.txt'), 'w') as f:
    f.write('ffconcat version 1.0\n')
    for epoch_num, seed_name, fname in epochs:
        full_path = os.path.join(aeon_dir, fname).replace(os.sep, '/')
        f.write("file '" + full_path + "'\n")
        f.write('duration 1.5\n')

print('Created slideshow_input.txt with 16 epochs, 1.5s each')
print('Total: ' + str(16 * 1.5) + 's = ' + str(16 * 1.5 / 60) + ' min')
for e, s, _ in epochs:
    print('  Epoch {:2d} = {}'.format(e, s))
