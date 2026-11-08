"""PC freeze flight recorder: write down what was happening *before* the hang.

The machine hung five times in 25 hours (Kernel-Power 41 x5, one bugcheck
0x162 nt!KeAbPostRelease, 143 nvlddmkm event-153 resets). Everything Windows
records about a hang is written *after* the reboot -- the state that caused it
is gone. So this samples the box every few seconds and fsyncs a heartbeat. On
the next start it compares the last heartbeat against the boot time and turns
the gap into an incident record carrying the exact pre-hang state: GPU temp and
clocks, power draw, which processes held the GPU, which python command line was
live, how much RAM was free, and the marker text that was set before the heavy
job started.

Design rules that matter:

  * it must not be the reason the box hangs -> no busy loops, sampling cost is
    bounded, every subprocess has a timeout and is optional
  * a sample is worthless unless it reaches the disk -> heartbeat is written to
    a temp file and os.replace'd, which is atomic on NTFS, plus fsync
  * a missing sample is data, not a failure -> gaps are recorded, never raised
  * self-describing incidents -> one JSON object per line, no schema drift

Usage:
    python SCRIPTS/automation/pc_freeze_recorder.py run [--interval 10]
    python SCRIPTS/automation/pc_freeze_recorder.py mark "7d crystal stress"
    python SCRIPTS/automation/pc_freeze_recorder.py status
    python SCRIPTS/automation/pc_freeze_recorder.py install|uninstall
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
import traceback
import urllib.request
import datetime as dt

ROOT = r"C:\abrasax"
OUT = os.path.join(ROOT, "LOGS", "freeze")
FLIGHT = os.path.join(OUT, "flight.jsonl")
LAST = os.path.join(OUT, "last_alive.json")
INCIDENTS = os.path.join(OUT, "incidents.jsonl")
MARKERS = os.path.join(OUT, "markers.jsonl")
LOG = os.path.join(OUT, "recorder.log")
ENV_PATH = os.path.join(ROOT, ".env")  # telegram notify only; never logged
TASK = "AbrasaxFreezeRecorder"

CREATE_NO_WINDOW = 0x08000000

GPU_FIELDS = ("timestamp,name,temperature.gpu,utilization.gpu,utilization.memory,"
              "memory.used,memory.total,power.draw,clocks.sm,clocks.mem,pstate,"
              "clocks_throttle_reasons.active")


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def ensure_dir() -> None:
    os.makedirs(OUT, exist_ok=True)


def note(msg: str) -> None:
    try:
        ensure_dir()
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write("%s %s\n" % (now_iso(), msg))
    except OSError:
        pass


def append_jsonl(path: str, rec: dict) -> None:
    ensure_dir()
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def write_atomic(path: str, rec: dict) -> None:
    ensure_dir()
    tmp = path + ".tmp"
    data = json.dumps(rec, sort_keys=True)
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def read_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def run(cmd: list[str], timeout: float = 8.0) -> str:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           creationflags=CREATE_NO_WINDOW)
        return (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.SubprocessError):
        return ""


def boot_time() -> float | None:
    try:
        import psutil
        return psutil.boot_time()
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- sampling ---

def gpu_sample() -> dict:
    out = run(["nvidia-smi", "--query-gpu=" + GPU_FIELDS,
               "--format=csv,noheader,nounits"], timeout=6)
    line = out.strip().splitlines()[0] if out.strip() else ""
    if not line:
        return {"ok": False}
    parts = [p.strip() for p in line.split(",")]
    keys = [k.strip() for k in GPU_FIELDS.split(",")]
    rec = {"ok": True}
    for k, v in zip(keys, parts):
        if k == "timestamp":
            rec["gpu_ts"] = v
        elif k == "name":
            rec["gpu"] = v
        else:
            try:
                rec[k] = float(v)
            except ValueError:
                rec[k] = v
    return rec


def gpu_processes() -> list[str]:
    out = run(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory",
               "--format=csv,noheader"], timeout=6)
    return [ln.strip() for ln in out.splitlines() if ln.strip()][:12]


def proc_sample(prev: dict, interval: float) -> tuple[dict, dict]:
    """Top CPU and top RSS processes, plus every python cmdline in flight."""
    try:
        import psutil
    except ImportError:
        return {}, prev
    cur = {}
    tops = []
    rss = []
    pythons = []
    for p in psutil.process_iter(["pid", "name", "cmdline", "memory_info",
                                 "create_time"]):
        try:
            info = p.info
            pid = info["pid"]
            ti = p.cpu_times()
            cpu = ti.user + ti.system
            cur[pid] = cpu
            delta = cpu - prev.get(pid, cpu)
            rate = max(0.0, delta) / max(0.5, interval) * 100.0
            name = info["name"] or "?"
            tops.append((rate, pid, name))
            mem = info["memory_info"]
            if mem is not None:
                rss.append((mem.rss, pid, name))
                if "python" in name.lower():
                    cmd = " ".join(info["cmdline"] or [])[:220]
                    pythons.append({"pid": pid, "rss_mb": int(mem.rss / 1048576),
                                    "cpu_pct": round(rate, 1),
                                    "started": dt.datetime.fromtimestamp(
                                        info["create_time"]).isoformat(timespec="seconds"),
                                    "cmd": cmd})
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
    tops.sort(reverse=True)
    rss.sort(reverse=True)
    vm = psutil.virtual_memory()
    sysd = {
        "cpu_pct": round(psutil.cpu_percent(interval=None), 1),
        "mem_pct": vm.percent,
        "mem_free_mb": int(vm.available / 1048576),
        "proc_count": len(cur),
        "top_cpu": [{"pct": round(r, 1), "pid": i, "name": n} for r, i, n in tops[:5]],
        "top_rss": [{"mb": int(m / 1048576), "pid": i, "name": n} for m, i, n in rss[:5]],
        "python": sorted(pythons, key=lambda d: d["rss_mb"], reverse=True)[:8],
    }
    return sysd, cur


def disk_sample() -> dict:
    """Every fixed/removable volume, plus which expected drives are missing.

    The external TOSHIBA (E:) throws controller errors under load, so its
    disappearance between samples is evidence, not noise.
    """
    out = {"drives": {}, "missing": []}
    try:
        import psutil
        parts = [p for p in psutil.disk_partitions(all=False) if p.device]
    except Exception:  # noqa: BLE001
        return out
    for p in parts:
        letter = p.device.rstrip("\\")
        try:
            import shutil
            t = shutil.disk_usage(p.mountpoint)
            out["drives"][letter] = {
                "free_gb": round(t.free / 1073741824, 1),
                "used_pct": round(100.0 * t.used / t.total, 1),
                "fstype": p.fstype,
            }
        except OSError:
            out["drives"][letter] = {"error": "usage unavailable"}
    for letter in ("C:", "E:", "G:"):
        if letter not in out["drives"]:
            out["missing"].append(letter)
    return out


EVENT_SCRIPT = (
    "$ids=41,6008,1001,4101,153,11,129,157,7,51;"
    "$o=@();"
    "foreach($i in $ids){"
    " $e=Get-WinEvent -FilterHashtable @{LogName='System';Id=$i;"
    "StartTime=(Get-Date).AddMinutes(-30)} -ErrorAction SilentlyContinue | "
    " Select-Object -First 1 TimeCreated;"
    " if($e){$o+=@{id=$i;t=$e.TimeCreated.ToString('o')}}}"
    "[pscustomobject]@{events=$o;now=(Get-Date).ToString('o')}|ConvertTo-Json -Compress -Depth 4"
)


def event_sample() -> dict:
    out = run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
               EVENT_SCRIPT], timeout=25)
    out = out.strip()
    if not out.startswith("{"):
        return {}
    try:
        return json.loads(out)
    except ValueError:
        return {}


def unavailable_reason() -> str:
    """Why a sample can be missing -- named, never silently dropped."""
    return "sampling failure; see recorder.log"


# ---------------------------------------------------------------- incidents ---

def previous_shutdown(boot: float) -> dict:
    """Classify the shutdown that preceded this boot from the event log."""
    script = (
        "$b=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime;"
        "$r=@{};"
        "$e=Get-WinEvent -FilterHashtable @{LogName='System';Id=1001;"
        "StartTime=$b.AddMinutes(-30)} -ErrorAction SilentlyContinue | Select-Object -First 1;"
        "if($e){$r.bugcheck=$e.Message}"
        "$e2=Get-WinEvent -FilterHashtable @{LogName='System';Id=6008;"
        "StartTime=$b.AddMinutes(-10)} -ErrorAction SilentlyContinue | Select-Object -First 1;"
        "if($e2){$r.unexpected=$e2.Message}"
        "$e3=Get-WinEvent -FilterHashtable @{LogName='System';Id=1074;"
        "StartTime=$b.AddMinutes(-30)} -ErrorAction SilentlyContinue | Select-Object -First 1;"
        "if($e3){$r.clean_initiated=$e3.Message}"
        "[pscustomobject]$r|ConvertTo-Json -Compress -Depth 4"
    )
    out = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
              timeout=30).strip()
    if not out.startswith("{"):
        return {"classified": False, "note": "event query failed"}
    try:
        rec = json.loads(out)
    except ValueError:
        return {"classified": False, "note": "event query unparseable"}
    rec["classified"] = True
    return rec


def telegram_notify(text: str) -> bool:
    """Send one message to the configured chat. False on any failure."""
    if os.environ.get("ABRASAX_FREEZE_NOTIFY", "1") == "0":
        note("telegram notify disabled by ABRASAX_FREEZE_NOTIFY=0")
        return False
    tok = chat = ""
    try:
        with open(ENV_PATH, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if line.startswith("ABRASAX_TELEGRAM_TOKEN="):
                    tok = line.split("=", 1)[1].strip().strip('"')
                elif line.startswith("ABRASAX_TELEGRAM_CHAT_ID="):
                    chat = line.split("=", 1)[1].strip().strip('"')
    except OSError:
        return False
    if not tok or not chat:
        return False
    body = json.dumps({"chat_id": chat, "text": text,
                       "disable_web_page_preview": True}).encode()
    req = urllib.request.Request("https://api.telegram.org/bot%s/sendMessage" % tok,
                                 data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return bool(json.loads(resp.read().decode()).get("ok"))
    except Exception as exc:  # noqa: BLE001
        note("telegram notify failed: %s: %s" % (type(exc).__name__, exc))
        return False


def check_previous_run(last: dict | None = None) -> dict | None:
    if last is None:
        last = read_json(LAST)
    if not last:
        return None
    boot = boot_time()
    if boot is None:
        return None
    last_ts = last.get("ts", 0)
    if last_ts >= boot - 1:
        return None  # same boot, nothing to explain
    gap = boot - last_ts
    inc = {
        "kind": "freeze" if gap > 60 else "restart",
        "detected_at": now_iso(),
        "last_alive": last,
        "last_alive_iso": dt.datetime.fromtimestamp(last_ts).astimezone()
        .isoformat(timespec="seconds"),
        "boot": dt.datetime.fromtimestamp(boot).astimezone().isoformat(timespec="seconds"),
        "dead_seconds_before_boot": round(gap, 1),
        "previous_shutdown": previous_shutdown(boot),
        "recent_markers": tail_jsonl(MARKERS, 5),
    }
    append_jsonl(INCIDENTS, inc)
    return inc


def tail_jsonl(path: str, n: int) -> list[dict]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()[-n:]
    except OSError:
        return []
    out = []
    for ln in lines:
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out


def tail_events(n: int) -> list[dict]:
    return tail_jsonl(FLIGHT, n)


# ------------------------------------------------------------------- commands ---

def cmd_run(interval: float) -> int:
    ensure_dir()
    inc = check_previous_run()
    if inc:
        print("PREVIOUS RUN ENDED WITHOUT SHUTTING DOWN: %s" % inc["kind"])
        print("  last heartbeat %s -> boot %s (%.0fs dark)"
              % (inc["last_alive_iso"], inc["boot"], inc["dead_seconds_before_boot"]))
        bc = (inc.get("previous_shutdown") or {}).get("bugcheck")
        if bc:
            print("  bugcheck: %s" % bc.splitlines()[0][:120])
        la = inc.get("last_alive") or {}
        head = ("ABRASAX freeze\n%s -- %.0fs dark\nlast alive %s\n"
                "gpu %sC %s%% %sW\n%s"
                % (inc["kind"], inc["dead_seconds_before_boot"],
                   inc.get("last_alive_iso"),
                   (la.get("gpu") or {}).get("temperature.gpu", "?"),
                   (la.get("gpu") or {}).get("utilization.gpu", "?"),
                   (la.get("gpu") or {}).get("power.draw", "?"),
                   (bc or "").splitlines()[0][:140] if bc else "no bugcheck"))
        note("incident notify: %s" % ("sent" if telegram_notify(head) else "not sent"))
    note("recorder start pid=%d interval=%ss" % (os.getpid(), interval))
    prev_cpu: dict = {}
    last_events = 0.0
    last_marker_count = -1
    while True:
        t0 = time.time()
        try:
            gpu = gpu_sample()
            sysd, prev_cpu = proc_sample(prev_cpu, interval)
            sample = {
                "ts": t0,
                "iso": now_iso(),
                "pid": os.getpid(),
                "boot": boot_time(),
                "gpu": gpu,
                "gpu_procs": gpu_processes(),
                "sys": sysd,
                "disk": disk_sample(),
            }
            if time.time() - last_events > 55:
                ev = event_sample()
                if ev:
                    sample["events"] = ev
                last_events = time.time()
            markers = tail_jsonl(MARKERS, 1)
            if markers and last_marker_count != len(markers):
                sample["marker"] = markers[-1]
                last_marker_count = len(markers)
            append_jsonl(FLIGHT, sample)
            write_atomic(LAST, {"ts": t0, "iso": sample["iso"], "gpu": gpu,
                                "sys": {k: sysd.get(k) for k in
                                        ("cpu_pct", "mem_pct", "mem_free_mb")},
                                "disk": sample["disk"],
                                "python": sysd.get("python"),
                                "last_marker": (markers[-1]["text"]
                                                if markers else None)})
        except Exception:  # noqa: BLE001 -- a recorder that dies is worse
            note("sample error: " + traceback.format_exc(limit=3).replace("\n", " | "))
        dt_sleep = interval - (time.time() - t0)
        if dt_sleep > 0:
            time.sleep(dt_sleep)
    return 0


def cmd_mark(text: str) -> int:
    append_jsonl(MARKERS, {"ts": time.time(), "iso": now_iso(), "text": text})
    gpu = gpu_sample()
    print("marked: %s | gpu %sC %s%% %sW" % (text, gpu.get("temperature.gpu", "?"),
                                            gpu.get("utilization.gpu", "?"),
                                            gpu.get("power.draw", "?")))
    return 0


def cmd_status() -> int:
    last = read_json(LAST)
    print("last heartbeat: %s (%.0fs ago)" % (last.get("iso", "never"),
                                              time.time() - last.get("ts", 0)))
    incs = tail_jsonl(INCIDENTS, 10)
    print("incidents: %d (last %d shown)" % (len(tail_jsonl(INCIDENTS, 10**6)), len(incs)))
    for i in incs:
        print("  %s  %-6s dark=%.0fs  %s" % (i.get("last_alive_iso"), i.get("kind"),
                                             i.get("dead_seconds_before_boot", 0),
                                             (i.get("previous_shutdown") or {})
                                             .get("bugcheck", "")[:60]))
    marks = tail_jsonl(MARKERS, 5)
    if marks:
        print("markers:")
        for m in marks:
            print("  %s %s" % (m.get("iso"), m.get("text")))
    return 0


def cmd_install() -> int:
    py = sys.executable.replace("python.exe", "pythonw.exe")
    script = os.path.abspath(__file__)
    ps = ("$a=New-ScheduledTaskAction -Execute '%s' -Argument '%s' -WorkingDirectory '%s';"
          "$t=New-ScheduledTaskTrigger -AtLogOn;"
          "$s=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries "
          "-DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) "
          "-RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1);"
          "Register-ScheduledTask -TaskName '%s' -Action $a -Trigger $t -Settings $s "
          "-Description 'ABRASAX freeze flight recorder' -Force | Out-Null;"
          "Get-ScheduledTask -TaskName '%s' | Select-Object TaskName,State | "
          "Format-Table -AutoSize | Out-String"
          % (py, '"%s" run' % script, ROOT, TASK, TASK))
    print(run(["powershell", "-NoProfile", "-Command", ps], timeout=60))
    return 0


def cmd_uninstall() -> int:
    print(run(["powershell", "-NoProfile", "-Command",
               "Unregister-ScheduledTask -TaskName '%s' -Confirm:$false" % TASK],
              timeout=60))
    return 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "run":
        interval = 10.0
        if "--interval" in sys.argv:
            interval = float(sys.argv[sys.argv.index("--interval") + 1])
        return cmd_run(interval)
    if cmd == "mark":
        return cmd_mark(" ".join(sys.argv[2:]) or "unnamed")
    if cmd == "status":
        return cmd_status()
    if cmd == "install":
        return cmd_install()
    if cmd == "uninstall":
        return cmd_uninstall()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
