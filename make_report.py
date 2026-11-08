"""Regenerate C:\\abrasax\\LOGS\\subagents\\agent_drives.md from walk JSON + baseline summary."""
import os
import sys
import json
import glob
import re

DATA_DIR = r"C:\abrasax\DATA"
LOGS_SUB = r"C:\abrasax\LOGS\subagents"
MD_PATH = os.path.join(LOGS_SUB, "agent_drives.md")
BASELINE_REF = r"C:\abrasax\logs\drive_inventory.jsonl"


def human(n):
    try:
        n = float(n)
    except (TypeError, ValueError):
        return str(n)
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0
    while n >= 1024.0 and i < len(units) - 1:
        n /= 1024.0
        i += 1
    return ("%d B" % int(n)) if i == 0 else ("%.2f %s" % (n, units[i]))


def ddelta(new, old):
    try:
        return int(new) - int(old)
    except (TypeError, ValueError):
        return None


def fmt_delta(d):
    if d is None:
        return "n/a"
    return ("+%d" % d) if d > 0 else str(d)


def latest_matching(pattern):
    hits = glob.glob(pattern)
    return sorted(hits)[-1] if hits else None


def pick_combined(ts):
    if ts:
        p = os.path.join(DATA_DIR, "drive_inventory_%s.json" % ts)
        if os.path.exists(p):
            return p
    cands = [p for p in glob.glob(os.path.join(DATA_DIR, "drive_inventory_*.json"))
             if re.match(r"^drive_inventory_\d{8}_\d{6}\.json$", os.path.basename(p))]
    return sorted(cands)[-1] if cands else None


def main():
    ts = sys.argv[1] if len(sys.argv) > 1 else None
    cp = pick_combined(ts)
    if not cp:
        print("no combined inventory found in %s" % DATA_DIR)
        sys.exit(1)
    with open(cp, "r", encoding="utf-8", errors="replace") as f:
        inv = json.load(f)
    wts = inv.get("ts", os.path.basename(cp))
    baseline = None
    bs = latest_matching(os.path.join(DATA_DIR, "baseline_summary_*.json"))
    if bs:
        try:
            with open(bs, "r", encoding="utf-8") as f:
                baseline = json.load(f)
        except Exception as e:
            print("baseline load failed: %s" % e)
    base_per = {}
    if baseline:
        for k, v in baseline.get("per_drive", {}).items():
            key = (str(k) + ":").upper() if (isinstance(k, str) and len(k) == 1) else str(k).upper()
            base_per[key] = v
    lines = []
    add = lines.append
    add("# External Drive Re-Index — agent_drives")
    add("")
    status = inv.get("status", "running")
    if status == "complete":
        add("- **Status: COMPLETE** (walk finished %s)" % inv.get("finished", "?"))
    else:
        add("- **Status: IN PROGRESS** — numbers below are provisional; this file is "
            "regenerated automatically when the walk completes.")
    add("- Walk ts: `%s` | started: %s | pid: %s" % (wts, inv.get("started", "?"), inv.get("pid", "?")))
    add("- Combined inventory: `C:\\abrasax\\DATA\\drive_inventory_%s.json` (+ per-drive `drive_inventory_%s_<L>.json`)" % (wts, wts))
    add("- Walk logs: `C:\\abrasax\\LOGS\\subagents\\drive_walk_%s.out.log` / `.err.log`" % wts)
    add("- Baseline: `%s`" % BASELINE_REF)
    if baseline:
        add("- Baseline summary: `%s` (%d lines parsed, %d bad)" % (
            bs, baseline.get("lines", 0), baseline.get("bad_lines", 0)))
    add("")
    add("## Per-drive totals (new walk)")
    add("")
    add("| Drive | State | Files | Bytes | Top dirs | Largest file | Errors |")
    add("|---|---|---|---|---|---|---|")
    drives = inv.get("drives", {})
    for dkey in sorted(drives):
        r = drives[dkey]
        st = r.get("state", "?")
        partial = st == "walking"
        f = r.get("total_files", r.get("files_so_far", 0))
        b = r.get("total_bytes", r.get("bytes_so_far", 0))
        if r.get("present") is False:
            f, b = 0, 0
        td = "-"
        if r.get("top_dirs_total") is not None:
            td = "%s/%s" % (r.get("top_dirs_done", 0), r.get("top_dirs_total", 0))
        lf = ""
        if r.get("largest_files"):
            lf = "%s (%s)" % (os.path.basename(r["largest_files"][0]["path"]),
                              human(r["largest_files"][0]["size"]))
        notes = []
        if st == "timed_out":
            notes.append("timed_out (partial)")
        if r.get("error"):
            notes.append("error: %s" % str(r["error"]).splitlines()[0][:60])
        if partial:
            notes.append("walking")
        mark = "*" if partial else ""
        add("| %s | %s%s | %d%s | %s%s | %s | %s | %s |" % (
            dkey, st, (" — " + "; ".join(notes)) if notes else "",
            f, mark, human(b), mark, td, lf, r.get("errors", 0)))
    add("")
    add("## Largest files per drive (top 5 of 20)")
    add("")
    for dkey in sorted(drives):
        r = drives[dkey]
        lfs = r.get("largest_files") or []
        if not lfs:
            continue
        add("### %s" % dkey)
        for e in lfs[:5]:
            add("- `%s` — %s" % (e["path"], human(e["size"])))
    add("")
    add("## Diff vs baseline (%s)" % BASELINE_REF)
    add("")
    if not baseline:
        add("Baseline not available/parseable — no diff.")
    else:
        add("| Drive | Baseline files | New files | Δ files | Baseline bytes | New bytes | Δ bytes |")
        add("|---|---|---|---|---|---|---|")
        tbf = tnf = tbb = tnb = 0
        for dkey in sorted(drives):
            r = drives[dkey]
            f = r.get("total_files", r.get("files_so_far", 0)) if r.get("present") is not False else 0
            b = r.get("total_bytes", r.get("bytes_so_far", 0)) if r.get("present") is not False else 0
            bv = base_per.get(dkey.upper(), base_per.get(dkey, {}))
            bf = bv.get("files")
            bb = bv.get("bytes")
            if bf is None:
                continue
            tbf += bf
            tnf += f
            tbb += bb or 0
            tnb += b
            mark = "*" if r.get("state") == "walking" else ""
            add("| %s | %d | %d%s | %s | %s | %s%s | %s |" % (
                dkey, bf, f, mark, fmt_delta(ddelta(f, bf)),
                human(bb or 0), human(b), mark, fmt_delta(ddelta(b, bb or 0))))
        add("| **Total** | **%d** | **%d** | **%s** | **%s** | **%s** | **%s** |" % (
            tbf, tnf, fmt_delta(ddelta(tnf, tbf)), human(tbb), human(tnb),
            fmt_delta(ddelta(tnb, tbb))))
        missing_new = [k for k in base_per if k not in {str(d).upper() for d in drives}]
        if missing_new:
            add("")
            add("Baseline drives not in new walk: %s" % ", ".join(sorted(missing_new)))
    add("")
    add("## Notes")
    add("")
    add("- Method: `os.scandir`, no hashing; junctions/symlinks skipped; skipped dirs: "
        "`$Recycle.Bin`, `System Volume Information`, `RECYCLER`, `RECYCLED`, `found.000`.")
    add("- Per-drive timeout: 25 min; a drive marked `timed_out` has partial totals "
        "(see `skipped_top_dirs` in its JSON).")
    add("- Per-drive JSONs contain per-top-level-dir counts + bytes and top-20 largest files.")
    os.makedirs(LOGS_SUB, exist_ok=True)
    with open(MD_PATH, "w", encoding="utf-8", errors="replace") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote %s" % MD_PATH)


if __name__ == "__main__":
    main()
