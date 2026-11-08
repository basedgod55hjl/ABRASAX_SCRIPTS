"""External drive re-index walker (wave-1 redo).

Walks each external drive root with os.scandir (no hashing), records
per-top-level-dir file counts + bytes and the top-20 largest files per
drive. Writes per-drive JSON and an incrementally updated combined JSON
to C:\\abrasax\\DATA. Regenerates agent_drives.md on completion.

Usage: python drive_walk.py [ts]
"""
import os
import sys
import json
import time
import heapq
import subprocess
import traceback

# D: removed per user directive 2026-11-01 ("REMOVE ONE DRIVE") — it is an
# empty removable slot that only burns walk time and error entries.
DRIVE_LETTERS = ["E", "F", "G", "H", "I"]
PER_DRIVE_TIMEOUT_SEC = 25 * 60
TOP_N = 20
HEARTBEAT_SEC = 60.0
SKIP_DIR_NAMES = {
    "$Recycle.Bin", "$RECYCLE.BIN", "$WinRecycle.Bin",
    "System Volume Information", "RECYCLER", "RECYCLED",
    "found.000", "Found.000",
}
DATA_DIR = r"C:\abrasax\DATA"
SCRIPTS_DIR = r"C:\abrasax\scripts"
LOGS_SUBDIR = r"C:\abrasax\LOGS\subagents"


class DeadlineExceeded(Exception):
    pass


def iso_now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def combined_path(ts):
    return os.path.join(DATA_DIR, "drive_inventory_%s.json" % ts)


def write_json_atomic(path, obj):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8", errors="replace") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except OSError as e:
        print("WARN: failed to write %s: %s" % (path, e), flush=True)


def is_link(entry):
    try:
        if entry.is_symlink():
            return True
    except OSError:
        return True
    try:
        if entry.is_junction(follow_symlinks=False):
            return True
    except (OSError, TypeError, AttributeError):
        pass
    return False


def walk_tree(path, st, deadline, hb):
    """Iterative scandir walk of a tree. st: mutable stats dict."""
    stack = [path]
    while stack:
        if time.time() > deadline:
            raise DeadlineExceeded()
        d = stack.pop()
        try:
            it = os.scandir(d)
        except OSError:
            st["errors"] += 1
            continue
        st["dirs"] += 1
        with it:
            try:
                for entry in it:
                    try:
                        if entry.name in SKIP_DIR_NAMES:
                            continue
                        if is_link(entry):
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        else:
                            try:
                                size = entry.stat(follow_symlinks=False).st_size
                            except OSError:
                                st["errors"] += 1
                                continue
                            st["files"] += 1
                            st["bytes"] += size
                            hp = st["heap"]
                            if len(hp) < TOP_N:
                                heapq.heappush(hp, (size, entry.path))
                            elif size > hp[0][0]:
                                heapq.heapreplace(hp, (size, entry.path))
                    except OSError:
                        st["errors"] += 1
            except OSError:
                # iterator itself failed (corrupted directory): skip dir, keep walking
                st["errors"] += 1
        hb(st["files"], st["bytes"], st["dirs"], d)


def scan_drive(letter, ts, state):
    root = letter + ":\\"
    rec = {
        "drive": letter + ":", "root": root, "present": True, "state": "walking",
        "started": iso_now(), "top_dirs": [], "top_dirs_done": 0,
        "root_files": 0, "root_bytes": 0,
        "files_so_far": 0, "bytes_so_far": 0, "dirs_so_far": 0, "errors": 0,
    }
    state["drives"][letter + ":"] = rec
    heap = []
    last_hb = [time.time()]

    def hb(cur_files, cur_bytes, cur_dirs, where):
        now = time.time()
        if now - last_hb[0] >= HEARTBEAT_SEC:
            last_hb[0] = now
            rec["files_so_far"] = rec["root_files"] + sum(t["files"] for t in rec["top_dirs"]) + cur_files
            rec["bytes_so_far"] = rec["root_bytes"] + sum(t["bytes"] for t in rec["top_dirs"]) + cur_bytes
            rec["dirs_so_far"] = sum(t["dirs"] for t in rec["top_dirs"]) + cur_dirs
            rec["progress"] = {"where": where, "files": rec["files_so_far"],
                               "bytes": rec["bytes_so_far"], "dirs": rec["dirs_so_far"]}
            print("heartbeat %s drive=%s files=%d bytes=%d dirs=%d where=%s" % (
                time.strftime("%H:%M:%S"), letter + ":", rec["files_so_far"],
                rec["bytes_so_far"], rec["dirs_so_far"], where), flush=True)
            write_json_atomic(combined_path(ts), state)

    try:
        entries = list(os.scandir(root))
    except OSError as e:
        rec["state"] = "error"
        rec["error"] = "%s: %s" % (type(e).__name__, e)
        return rec
    topdirs = []
    for e in entries:
        try:
            if e.name in SKIP_DIR_NAMES or is_link(e):
                continue
            if e.is_dir(follow_symlinks=False):
                topdirs.append(e.path)
            else:
                try:
                    size = e.stat(follow_symlinks=False).st_size
                except OSError:
                    rec["errors"] += 1
                    continue
                rec["root_files"] += 1
                rec["root_bytes"] += size
                if len(heap) < TOP_N:
                    heapq.heappush(heap, (size, e.path))
                elif size > heap[0][0]:
                    heapq.heapreplace(heap, (size, e.path))
        except OSError:
            rec["errors"] += 1
        hb(0, 0, 0, root)
    rec["top_dirs_total"] = len(topdirs)
    print("%s DRIVE %s root listed: root_files=%d topdirs=%d" % (
        iso_now(), letter + ":", rec["root_files"], len(topdirs)), flush=True)
    deadline = time.time() + PER_DRIVE_TIMEOUT_SEC
    for i, td in enumerate(topdirs):
        if time.time() > deadline:
            rec["state"] = "timed_out"
            rec["skipped_top_dirs"] = topdirs[i:]
            break
        st = {"files": 0, "bytes": 0, "dirs": 0, "errors": 0, "heap": heap}
        td_rec = {"path": td, "files": 0, "bytes": 0, "dirs": 0, "timed_out": False}
        try:
            walk_tree(td, st, deadline, hb)
        except DeadlineExceeded:
            td_rec["timed_out"] = True
            rec["state"] = "timed_out"
            rec["skipped_top_dirs"] = topdirs[i + 1:]
        td_rec["files"] = st["files"]
        td_rec["bytes"] = st["bytes"]
        td_rec["dirs"] = st["dirs"]
        rec["top_dirs"].append(td_rec)
        rec["top_dirs_done"] = i + 1
        rec["errors"] += st["errors"]
        rec["files_so_far"] = rec["root_files"] + sum(t["files"] for t in rec["top_dirs"])
        rec["bytes_so_far"] = rec["root_bytes"] + sum(t["bytes"] for t in rec["top_dirs"])
        rec["dirs_so_far"] = sum(t["dirs"] for t in rec["top_dirs"])
        print("%s DRIVE %s topdir done: %s files=%d bytes=%d dirs=%d" % (
            iso_now(), letter + ":", td, st["files"], st["bytes"], st["dirs"]), flush=True)
        write_json_atomic(combined_path(ts), state)
        if td_rec["timed_out"]:
            break
    else:
        if rec["state"] == "walking":
            rec["state"] = "done"
    rec["finished"] = iso_now()
    rec["total_files"] = rec["root_files"] + sum(t["files"] for t in rec["top_dirs"])
    rec["total_bytes"] = rec["root_bytes"] + sum(t["bytes"] for t in rec["top_dirs"])
    rec["total_dirs"] = sum(t["dirs"] for t in rec["top_dirs"])
    rec["files_so_far"] = rec["total_files"]
    rec["bytes_so_far"] = rec["total_bytes"]
    rec["dirs_so_far"] = rec["total_dirs"]
    rec["largest_files"] = [{"path": p, "size": s} for s, p in sorted(heap, reverse=True)]
    print("%s DRIVE %s FINISHED state=%s files=%d bytes=%d" % (
        iso_now(), letter + ":", rec["state"], rec["total_files"], rec["total_bytes"]), flush=True)
    return rec


def main():
    ts = sys.argv[1] if len(sys.argv) > 1 else time.strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    for d in (DATA_DIR, SCRIPTS_DIR, LOGS_SUBDIR):
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            pass
    cp = combined_path(ts)
    state = {"ts": ts, "started": iso_now(), "pid": pid, "status": "running", "drives": {}}
    if os.path.exists(cp):  # resume support
        try:
            with open(cp, "r", encoding="utf-8", errors="replace") as f:
                old = json.load(f)
            if isinstance(old, dict) and isinstance(old.get("drives"), dict):
                state = old
                state["status"] = "running"
                state["pid"] = pid
                print("resuming ts=%s (terminal already: %s)" % (
                    ts, sorted(k for k, v in state["drives"].items()
                               if v.get("state") in ("done", "timed_out", "error", "missing"))), flush=True)
        except Exception as e:
            print("resume load failed, starting fresh: %s" % e, flush=True)
    pid_file = os.path.join(LOGS_SUBDIR, "drive_walk_%s.pid" % ts)
    try:
        with open(pid_file, "w") as f:
            f.write(str(pid))
    except OSError:
        pass
    write_json_atomic(cp, state)
    print("walk start ts=%s pid=%d drives=%s" % (ts, pid, DRIVE_LETTERS), flush=True)
    for letter in DRIVE_LETTERS:
        existing = state["drives"].get(letter + ":")
        if existing and existing.get("state") in ("done", "timed_out", "error", "missing"):
            print("%s DRIVE %s: already scanned (state=%s), skipping" % (
                iso_now(), letter + ":", existing.get("state")), flush=True)
            continue
        root = letter + ":\\"
        if not os.path.exists(root):
            rec = {"drive": letter + ":", "present": False, "state": "missing"}
            print("%s DRIVE %s: not present, skipped" % (iso_now(), letter + ":"), flush=True)
        else:
            try:
                rec = scan_drive(letter, ts, state)
            except Exception:
                # preserve partial stats gathered before the crash
                rec = state["drives"].get(letter + ":") or {}
                rec["drive"] = letter + ":"
                rec["present"] = True
                rec["state"] = "error"
                rec["error"] = traceback.format_exc()
                rec["finished"] = iso_now()
                print("DRIVE %s crashed:\n%s" % (letter + ":", rec["error"]), flush=True)
        state["drives"][letter + ":"] = rec
        write_json_atomic(cp, state)
        write_json_atomic(os.path.join(DATA_DIR, "drive_inventory_%s_%s.json" % (ts, letter)), rec)
    tot_f = sum(r.get("total_files", r.get("files_so_far", 0)) for r in state["drives"].values())
    tot_b = sum(r.get("total_bytes", r.get("bytes_so_far", 0)) for r in state["drives"].values())
    state["status"] = "complete"
    state["finished"] = iso_now()
    state["summary"] = {
        "total_files": tot_f, "total_bytes": tot_b,
        "per_drive": {k: {"files": v.get("total_files", v.get("files_so_far", 0)),
                          "bytes": v.get("total_bytes", v.get("bytes_so_far", 0)),
                          "state": v.get("state")}
                      for k, v in state["drives"].items()},
    }
    write_json_atomic(cp, state)
    print("WALK COMPLETE ts=%s total_files=%d total_bytes=%d" % (ts, tot_f, tot_b), flush=True)
    try:
        subprocess.call([sys.executable, os.path.join(SCRIPTS_DIR, "make_report.py"), ts], timeout=600)
    except Exception as e:
        print("report regeneration failed: %s" % e, flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("FATAL:\n%s" % traceback.format_exc(), flush=True)
        sys.exit(1)
