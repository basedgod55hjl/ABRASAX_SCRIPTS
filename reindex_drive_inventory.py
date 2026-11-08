#!/usr/bin/env python3
"""ABRASAX drive inventory re-indexer.

Walks every mounted drive (except C: and CD-ROMs) with os.scandir,
aggregates files/bytes per top-level directory, keeps the 20 largest files
per drive, writes everything incrementally, and diffs against the previous
full-file inventory (C:\\abrasax\\logs\\drive_inventory.jsonl).

Subcommands:
  walk       Walk all drives. Writes per-drive path lists + jsonl archives +
             progress files to --scratch (incremental; survives aborts).
  split-old  Stream previous inventory jsonl into per-drive path lists.
  diff       Sort + merge-join old/new per-drive path lists -> added/removed.
  finalize   Build inventory JSON (C:\\abrasax\\DATA\\drive_inventory_<ts>.json),
             human summary (C:\\abrasax\\LOGS\\subagents\\agent_drives.md),
             rotate the canonical full-list jsonl, append drive_scan.log.

Skip rules: recycle-bin/system dirs by name, all symlinks/junctions
(reparse points) via is_symlink()/follow_symlinks=False, permission errors
tolerated (counted). Per-drive time cap default 20 min.
"""
import argparse
import ctypes
import faulthandler
import heapq
import json
import os
import shutil
import subprocess
import sys
import time
import traceback

SKIP_DIR_NAMES = {
    '$recycle.bin', 'recycler', 'system volume information',
    '$sysreset', '$windows.~bt', '$winreagent',
}
DRIVE_TYPES = {2: 'REMOVABLE', 3: 'FIXED', 4: 'NETWORK', 5: 'CDROM', 6: 'RAMDISK'}
TIME_CAP_S = 20 * 60
TOP_N = 20
TOP_DIRS_KEEP = 2000
DIFF_SAMPLES = 25


def log(msg):
    print(msg, flush=True)


def human_size(n):
    if n is None:
        return '?'
    n = float(n)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB', 'PB'):
        if n < 1024 or unit == 'PB':
            return f'{n:.1f} {unit}' if unit != 'B' else f'{int(n)} B'
        n /= 1024


def list_drives(include=()):
    """Return [(letter, drivetype)] for mounted drives except C:/CD-ROMs."""
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    out = []
    for i in range(26):
        if bitmask & (1 << i):
            c = chr(65 + i)
            if c == 'C':
                continue
            t = ctypes.windll.kernel32.GetDriveTypeW(c + ':\\')
            if t == 5:  # CD-ROM
                continue
            out.append((c, t))
    by_letter = {c: (c, t) for c, t in out}
    ordered = [by_letter.pop(c) for c in include if c in by_letter]
    ordered += sorted(by_letter.values())
    return ordered


def walk_drive(drive, drive_type, scratch, archive=True, cap_s=TIME_CAP_S):
    root = drive + ':\\'
    res = {
        'drive': drive, 'type': DRIVE_TYPES.get(drive_type, str(drive_type)),
        'root': root, 'start': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'files': 0, 'bytes': 0, 'dirs': 0, 'errors': 0,
        'skipped_links': 0, 'skipped_dirs': 0,
        'aborted': False, 'error': None,
        'disk_total': None, 'disk_used': None, 'disk_free': None,
    }
    t0 = time.monotonic()
    deadline = t0 + cap_s
    try:
        du = shutil.disk_usage(root)
        res['disk_total'], res['disk_used'], res['disk_free'] = du
    except OSError:
        pass

    top = {}          # name -> [files, bytes]
    heap = []         # (size, path) top-20
    tick = [0]

    pathf_path = os.path.join(scratch, f'new_{drive}.txt')
    arch_path = os.path.join(scratch, f'arch_{drive}.jsonl') if archive else None

    try:
        probe = os.scandir(root)
        probe.close()
    except OSError as ex:
        res['error'] = f'root not readable: {ex}'
        res['elapsed_s'] = round(time.monotonic() - t0, 1)
        return res

    def walk(path, bucket, depth, pf, af):
        if res['aborted']:
            return
        tick[0] += 1
        if tick[0] & 1023 == 0 and time.monotonic() > deadline:
            res['aborted'] = True
            return
        try:
            it = os.scandir(path)
        except OSError:
            res['errors'] += 1
            return
        i = 0
        with it:
            try:
                for e in it:
                    if res['aborted']:
                        break
                    i += 1
                    if i & 4095 == 0 and time.monotonic() > deadline:
                        res['aborted'] = True
                        break
                    if e.name.lower() in SKIP_DIR_NAMES:
                        res['skipped_dirs'] += 1
                        continue
                    try:
                        is_sym = e.is_symlink()
                    except OSError:
                        is_sym = False
                    if is_sym:
                        res['skipped_links'] += 1
                        continue
                    try:
                        is_d = e.is_dir(follow_symlinks=False)
                    except OSError:
                        is_d = False
                    if is_d:
                        res['dirs'] += 1
                        if depth == 0:
                            nb = top.setdefault(e.name, [0, 0])
                            walk(e.path, nb, 1, pf, af)
                        else:
                            walk(e.path, bucket, depth + 1, pf, af)
                        continue
                    try:
                        is_f = e.is_file(follow_symlinks=False)
                    except OSError:
                        is_f = True  # unknown: treat as file attempt
                    if not is_f:
                        res['skipped_links'] += 1
                        continue
                    try:
                        st = e.stat(follow_symlinks=False)
                    except OSError:
                        st = None
                        res['errors'] += 1
                    sz = st.st_size if st is not None else 0
                    res['files'] += 1
                    res['bytes'] += sz
                    bkt = bucket if depth > 0 else top.setdefault('__root__', [0, 0])
                    bkt[0] += 1
                    bkt[1] += sz
                    pf.write(e.path + '\n')
                    if af is not None:
                        try:
                            t = int(st.st_mtime) if st is not None else 0
                        except Exception:
                            t = 0
                        af.write(json.dumps(
                            {'d': drive, 'p': e.path, 'b': sz, 't': t},
                            ensure_ascii=False) + '\n')
                    if len(heap) < TOP_N:
                        heapq.heappush(heap, (sz, e.path))
                    elif sz > heap[0][0]:
                        heapq.heapreplace(heap, (sz, e.path))
            except OSError:
                # directory corrupted/unreadable mid-iteration (e.g. WinError 1392)
                res['errors'] += 1

    with open(pathf_path, 'w', encoding='utf-8', errors='surrogateescape',
              buffering=1 << 20) as pf:
        af = None
        if arch_path:
            af = open(arch_path, 'w', encoding='utf-8', errors='surrogateescape',
                      buffering=1 << 20)
        try:
            walk(root, None, 0, pf, af)
        finally:
            if af is not None:
                af.flush()
                af.close()

    res['elapsed_s'] = round(time.monotonic() - t0, 1)
    res['top_dirs_total'] = len(top)
    res['top_dirs'] = sorted(
        ({'name': n, 'files': v[0], 'bytes': v[1]} for n, v in top.items()),
        key=lambda x: (-x['bytes'], x['name']))[:TOP_DIRS_KEEP]
    res['largest'] = [
        {'path': p, 'size': s} for s, p in
        sorted(heap, key=lambda x: (-x[0], x[1]))]
    return res


def cmd_walk(args):
    scratch = args.scratch
    os.makedirs(scratch, exist_ok=True)
    faulthandler.enable()
    drives = list_drives(include=args.drives)
    log(f'Drives to walk: {[(d, DRIVE_TYPES.get(t, str(t))) for d, t in drives]}')
    summaries = []
    aborted_any = False
    for d, t in drives:
        marker = os.path.join(scratch, f'done_{d}.json')
        if args.resume and os.path.exists(marker):
            try:
                with open(marker, encoding='utf-8') as f:
                    prev = json.load(f)
            except Exception:
                prev = None
            if prev:
                log(f'[{d}] resume: already indexed '
                    f"({prev.get('files', 0)} files), skipping")
                summaries.append(prev)
                continue
        log(f'[{d}] starting ({DRIVE_TYPES.get(t, str(t))}) cap={args.cap_s}s')
        try:
            res = walk_drive(d, t, scratch, archive=not args.no_archive,
                             cap_s=args.cap_s)
        except Exception:
            res = {'drive': d, 'type': DRIVE_TYPES.get(t, str(t)),
                   'root': d + ':\\',
                   'start': time.strftime('%Y-%m-%dT%H:%M:%S'),
                   'files': 0, 'bytes': 0, 'dirs': 0, 'errors': 0,
                   'skipped_links': 0, 'skipped_dirs': 0,
                   'aborted': False,
                   'error': 'walker crashed: ' + traceback.format_exc()[-500:],
                   'disk_total': None, 'disk_used': None, 'disk_free': None,
                   'elapsed_s': 0}
            log(f'[{d}] WALKER CRASHED (continuing with next drive)')
        log(f"[{d}] done files={res['files']} bytes={res['bytes']} "
            f"dirs={res['dirs']} errors={res['errors']} "
            f"links_skipped={res['skipped_links']} dirs_skipped={res['skipped_dirs']} "
            f"aborted={res['aborted']} elapsed={res['elapsed_s']}s"
            + (f" error={res['error']}" if res['error'] else ''))
        summaries.append(res)
        with open(os.path.join(scratch, 'progress.jsonl'), 'a',
                  encoding='utf-8') as f:
            f.write(json.dumps(res, ensure_ascii=False) + '\n')
        tmp = os.path.join(scratch, 'progress.json.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(summaries, f, ensure_ascii=False, indent=1)
        os.replace(tmp, os.path.join(scratch, 'progress.json'))
        if not res.get('error'):
            with open(marker, 'w', encoding='utf-8') as f:
                json.dump(res, f, ensure_ascii=False)
        if res['aborted']:
            aborted_any = True
    log('WALK COMPLETE' if not aborted_any else 'WALK COMPLETE (aborted drive(s) at cap)')
    return 2 if aborted_any else 0


def cmd_split_old(args):
    scratch = args.scratch
    os.makedirs(scratch, exist_ok=True)
    fhs = {}
    counts = {}
    bad = 0
    with open(args.old, 'r', encoding='utf-8', errors='surrogateescape',
              buffering=1 << 20) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
                d, p = o['d'], o['p']
            except Exception:
                bad += 1
                continue
            fh = fhs.get(d)
            if fh is None:
                fh = open(os.path.join(scratch, f'old_{d}.txt'), 'w',
                          encoding='utf-8', errors='surrogateescape',
                          buffering=1 << 20)
                fhs[d] = fh
                counts[d] = 0
            fh.write(p + '\n')
            counts[d] += 1
    for fh in fhs.values():
        fh.close()
    with open(os.path.join(scratch, 'old_counts.json'), 'w',
              encoding='utf-8') as f:
        json.dump({'counts': counts, 'bad_lines': bad}, f, indent=1)
    log(f'split-old done: {counts} bad={bad}')


def run_sort(src, dst):
    env = dict(os.environ)
    env['LC_ALL'] = 'C'
    with open(dst, 'wb') as out:
        subprocess.run(['sort', '-u', '-S', '1G', src], stdout=out,
                       check=True, env=env)


def count_lines(path):
    n = 0
    with open(path, 'r', encoding='utf-8', errors='surrogateescape',
              buffering=1 << 20) as f:
        for _ in f:
            n += 1
    return n


def merge_diff(old_sorted, new_sorted, samples):
    removed = added = 0
    rem_samples, add_samples = [], []
    with open(old_sorted, 'r', encoding='utf-8', errors='surrogateescape',
              buffering=1 << 20) as o, \
         open(new_sorted, 'r', encoding='utf-8', errors='surrogateescape',
              buffering=1 << 20) as n:
        ol = o.readline()
        nl = n.readline()
        while ol and nl:
            if ol == nl:
                ol = o.readline()
                nl = n.readline()
            elif ol < nl:
                removed += 1
                if len(rem_samples) < samples:
                    rem_samples.append(ol.rstrip('\n'))
                ol = o.readline()
            else:
                added += 1
                if len(add_samples) < samples:
                    add_samples.append(nl.rstrip('\n'))
                nl = n.readline()
        while ol:
            removed += 1
            if len(rem_samples) < samples:
                rem_samples.append(ol.rstrip('\n'))
            ol = o.readline()
        while nl:
            added += 1
            if len(add_samples) < samples:
                add_samples.append(nl.rstrip('\n'))
            nl = n.readline()
    return added, removed, add_samples, rem_samples


def cmd_diff(args):
    scratch = args.scratch
    out = {}
    for d in args.drives:
        newf = os.path.join(scratch, f'new_{d}.txt')
        if not os.path.exists(newf):
            log(f'[{d}] no new path list, skipping')
            continue
        oldf = os.path.join(scratch, f'old_{d}.txt')
        olds = oldf + '.sorted'
        news = newf + '.sorted'
        run_sort(newf, news)
        if os.path.exists(oldf):
            run_sort(oldf, olds)
            prev = count_lines(olds)
        else:
            prev = 0
            with open(olds, 'w', encoding='utf-8') as f:
                pass
        newn = count_lines(news)
        added, removed, a_s, r_s = merge_diff(olds, news, args.samples)
        out[d] = {
            'prev_files': prev, 'new_files': newn,
            'added': added, 'removed': removed,
            'added_samples': a_s, 'removed_samples': r_s,
        }
        log(f'[{d}] prev={prev} new={newn} added={added} removed={removed}')
    with open(os.path.join(scratch, 'diff.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)


def build_markdown(inv, old_counts, raw_prev_total):
    ts = inv['timestamp']
    lines = []
    a = lines.append
    a(f'# ABRASAX Drive Inventory - {inv["generated"]}\n')
    t = inv['totals']
    a('## Totals')
    a(f"- Files: **{t['files']:,}** ({human_size(t['bytes'])}) across "
      f"{len(inv['drives'])} drives")
    a(f"- Walk errors tolerated: {t['errors']:,}")
    a(f"- Drives aborted at {inv['time_cap_s_per_drive']}s cap: "
      + (', '.join(t['aborted_drives']) if t['aborted_drives'] else 'none'))
    a(f"- Previous inventory: `{inv['previous_inventory']}` "
      f"({raw_prev_total:,} raw lines; deduped per drive when diffing)")
    a(f"- New full-list inventory: `C:\\abrasax\\logs\\drive_inventory.jsonl` "
      f"(rotated in place; previous kept as `drive_inventory_prev_{ts}.jsonl`)")
    a('')
    a('## Per-drive summary')
    a('')
    a('| Drive | Type | Files | Bytes | Dirs | Errors | Links skipped | Dirs skipped | Elapsed | Aborted |')
    a('|---|---|---|---|---|---|---|---|---|---|')
    for s in inv['drives']:
        err = s['error'] or ''
        a(f"| {s['drive']} | {s['type']} | {s['files']:,} | {human_size(s['bytes'])} "
          f"| {s['dirs']:,} | {s['errors']:,} | {s['skipped_links']:,} "
          f"| {s['skipped_dirs']:,} | {s['elapsed_s']}s | "
          f"{'YES' if s['aborted'] else ''} {err} |")
    a('')
    a('## Top directories per drive (top 8 by bytes)')
    for s in inv['drives']:
        if s['error']:
            continue
        a('')
        a(f"### {s['drive']}: ({s['top_dirs_total']} top-level dirs)")
        for td in s['top_dirs'][:8]:
            a(f"- `{td['name']}` - {td['files']:,} files, {human_size(td['bytes'])}")
    a('')
    a('## Largest files per drive (top 10 of 20 shown; full list in JSON)')
    for s in inv['drives']:
        if s['error'] or not s['largest']:
            continue
        a('')
        a(f"### {s['drive']}:")
        for lf in s['largest'][:10]:
            a(f"- {human_size(lf['size']):>10}  `{lf['path']}`")
    a('')
    a('## Diff vs previous inventory')
    a('')
    for s in inv['drives']:
        d = s.get('diff')
        if not d:
            continue
        a(f"### {s['drive']}:")
        if d['prev_files'] == 0:
            a(f"- NEW DRIVE (not in previous inventory): {d['new_files']:,} files "
              f"indexed, all {d['added']:,} counted as added")
        else:
            a(f"- Previous: {d['prev_files']:,} files -> now: {d['new_files']:,} "
              f"| **+{d['added']:,} added, -{d['removed']:,} removed**")
            if d['added_samples']:
                a(f"- Sample added ({len(d['added_samples'])} of {d['added']:,}):")
                for pth in d['added_samples'][:10]:
                    a(f"  - `{pth}`")
            if d['removed_samples']:
                a(f"- Sample removed ({len(d['removed_samples'])} of {d['removed']:,}):")
                for pth in d['removed_samples'][:10]:
                    a(f"  - `{pth}`")
    a('')
    a('## Notes')
    a('- Skipped by rule: symlinks/junctions (reparse points), '
      '$RECYCLE.BIN, System Volume Information and similar.')
    a('- Permission/IO errors are counted, never fatal; files whose size '
      'could not be read are counted with 0 bytes.')
    if old_counts:
        a(f"- Raw previous per-drive line counts (incl. duplicate runs): "
          + ', '.join(f'{k}={v:,}' for k, v in sorted(old_counts.items())))
    return '\n'.join(lines)


def cmd_finalize(args):
    scratch = args.scratch
    with open(os.path.join(scratch, 'progress.json'), encoding='utf-8') as f:
        summaries = json.load(f)
    diff = {}
    diff_path = os.path.join(scratch, 'diff.json')
    if os.path.exists(diff_path):
        with open(diff_path, encoding='utf-8') as f:
            diff = json.load(f)
    old_counts = {}
    old_counts_path = os.path.join(scratch, 'old_counts.json')
    if os.path.exists(old_counts_path):
        with open(old_counts_path, encoding='utf-8') as f:
            old_counts = json.load(f).get('counts', {})
    for s in summaries:
        d = diff.get(s['drive'])
        if d:
            s['diff'] = d
    ts = time.strftime('%Y%m%d_%H%M%S')
    inv = {
        'schema': 'abrasax-drive-inventory-v2',
        'generated': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'timestamp': ts,
        'previous_inventory': args.old,
        'time_cap_s_per_drive': args.cap_s,
        'totals': {
            'files': sum(s['files'] for s in summaries),
            'bytes': sum(s['bytes'] for s in summaries),
            'errors': sum(s['errors'] for s in summaries),
            'aborted_drives': [s['drive'] for s in summaries if s['aborted']],
        },
        'drives': summaries,
    }
    os.makedirs(args.out_dir, exist_ok=True)
    out_json = os.path.join(args.out_dir, f'drive_inventory_{ts}.json')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(inv, f, ensure_ascii=False, indent=1)
    # Rotate canonical full-list jsonl: old -> prev_<ts>, new per-drive
    # archives concatenated into the canonical path.
    prev_raw_total = 0
    if args.rotate and os.path.exists(args.old):
        prev_raw_total = count_lines(args.old)
        os.replace(args.old, os.path.join(
            os.path.dirname(args.old), f'drive_inventory_prev_{ts}.jsonl'))
    canon = args.old if args.rotate else os.path.join(
        os.path.dirname(args.old), f'drive_inventory_{ts}.jsonl')
    with open(canon, 'w', encoding='utf-8', buffering=1 << 20) as out:
        for s in summaries:
            arch = os.path.join(scratch, f"arch_{s['drive']}.jsonl")
            if os.path.exists(arch):
                with open(arch, 'r', encoding='utf-8', errors='surrogateescape',
                          buffering=1 << 20) as fh:
                    shutil.copyfileobj(fh, out)
    md = build_markdown(inv, old_counts, prev_raw_total)
    os.makedirs(args.md_dir, exist_ok=True)
    md_path = os.path.join(args.md_dir, 'agent_drives.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md)
    with open(args.scan_log, 'a', encoding='utf-8') as f:
        f.write(f'\n# DRIVE CRAWL {inv["generated"]}\n')
        for s in summaries:
            f.write(f"{s['drive']}: {s['files']} files in {s['elapsed_s']}s"
                    + (' (ABORTED AT CAP)' if s['aborted'] else '') + '\n')
        f.write(f"TOTAL {inv['totals']['files']} files -> {out_json}\n")
    log(f'finalized: {out_json}')
    log(f'markdown: {md_path}')
    log(f'canonical jsonl: {canon}')


def main():
    ap = argparse.ArgumentParser(description='ABRASAX drive inventory re-indexer')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('walk', help='walk all mounted drives')
    p.add_argument('--scratch', required=True)
    p.add_argument('--drives', nargs='*', default=[],
                   help='drive letters to prefer/order')
    p.add_argument('--cap-s', type=int, default=TIME_CAP_S)
    p.add_argument('--no-archive', action='store_true')
    p.add_argument('--resume', action='store_true',
                   help='skip drives with a done marker in scratch')
    p.set_defaults(fn=cmd_walk)

    p = sub.add_parser('split-old', help='split previous inventory jsonl per drive')
    p.add_argument('--scratch', required=True)
    p.add_argument('--old', required=True)
    p.set_defaults(fn=cmd_split_old)

    p = sub.add_parser('diff', help='diff old vs new per drive')
    p.add_argument('--scratch', required=True)
    p.add_argument('--drives', nargs='+', required=True)
    p.add_argument('--samples', type=int, default=DIFF_SAMPLES)
    p.set_defaults(fn=cmd_diff)

    p = sub.add_parser('finalize', help='build inventory JSON + markdown + rotate')
    p.add_argument('--scratch', required=True)
    p.add_argument('--old', required=True)
    p.add_argument('--out-dir', required=True)
    p.add_argument('--md-dir', required=True)
    p.add_argument('--scan-log', required=True)
    p.add_argument('--cap-s', type=int, default=TIME_CAP_S)
    p.add_argument('--no-rotate', action='store_false', dest='rotate', default=True)
    p.set_defaults(fn=cmd_finalize)

    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == '__main__':
    main()
