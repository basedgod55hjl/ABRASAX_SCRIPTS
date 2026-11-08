"""The real test: stop the model servers, keep sensing.

The environment-variable test earlier proved nothing - nothing in the sense path
reads those variables. This actually terminates the model processes and
re-measures.

Order matters: capture the baseline, stop, measure, RESTORE. The restore is
mandatory - leaving LM Studio dead would be harmful, and the script does it in a
finally block so a crash mid-test cannot leave the machine degraded.

Targets (from probe_deps.py):
    :1234  LM Studio.exe     pid varies
    :9001  abrasax gateway   pythonw.exe
    :8777  node-lm           node.exe
The gateway and node-lm are restarted by the existing supervisor, so only
LM Studio needs a manual relaunch. We check what comes back by itself.
"""
import json
import os
import socket
import subprocess
import sys
import time

sys.path.insert(0, r"C:\ABRASAX")

MODEL_PORTS = {1234: "lmstudio", 9001: "gateway", 8777: "node-lm"}


def listening(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


def ports_state():
    return {n: listening(p) for p, n in MODEL_PORTS.items()}


def pids_on(port):
    out = subprocess.run(["netstat", "-ano"], capture_output=True,
                         text=True, timeout=30).stdout
    pids = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[3] == "LISTENING":
            if int(parts[1].rsplit(":", 1)[-1]) == port:
                pids.add(int(parts[4]))
    return pids


def tick():
    code = ("import json,sys;sys.path.insert(0,r'C:\\ABRASAX');"
            "from abrasax.sense_loop import tick;"
            "r=tick(serial='R5CY308WZVK');"
            "print(json.dumps({k:r.get(k) for k in "
            "('ingested','archived','error','live','duration_ms')}))")
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "tick TIMED OUT", "wall": time.time() - t0}
    wall = time.time() - t0
    lines = (p.stdout or "").strip().splitlines()
    if not lines:
        return {"ok": False, "error": (p.stderr or "no output")[-200:], "wall": wall}
    d = json.loads(lines[-1])
    d["ok"] = p.returncode == 0 and not d.get("error")
    d["wall"] = wall
    return d


def main():
    print("=== baseline ===")
    print("  ports:", ports_state())
    base = tick()
    print(f"  tick ok={base['ok']} ingested={base.get('ingested')} "
          f"wall={base['wall']:.1f}s live={base.get('live')}")

    stopped = []
    try:
        print("\n=== stopping model servers ===")
        for port, name in MODEL_PORTS.items():
            for pid in pids_on(port):
                r = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                                   capture_output=True, text=True, timeout=30)
                ok = "SUCCESS" in (r.stdout or "")
                print(f"  :{port} {name:<9} pid={pid} "
                      f"{'killed' if ok else 'FAILED'}")
                if ok:
                    stopped.append((port, name, pid))
        time.sleep(3)
        print("  ports now:", ports_state())

        print("\n=== tick with models gone ===")
        off = tick()
        print(f"  tick ok={off['ok']} ingested={off.get('ingested')} "
              f"wall={off['wall']:.1f}s live={off.get('live')}")
        if off.get("error"):
            print(f"  ERROR: {off['error']}")

        print("\n=== verdict ===")
        if base["ok"] and off["ok"] and off.get("ingested", 0) >= base.get("ingested", 0):
            print("  PASS  the world state keeps sensing with every model offline")
            print(f"        ingested {base.get('ingested')} -> {off.get('ingested')}, "
                  f"wall {base['wall']:.1f}s -> {off['wall']:.1f}s")
        elif off["ok"]:
            print(f"  PARTIAL  still worked but ingested "
                  f"{base.get('ingested')} -> {off.get('ingested')}")
        else:
            print("  FAIL  the sense path depends on a model being up")
            print(f"        {off.get('error')}")
    finally:
        print("\n=== restoring ===")
        time.sleep(2)
        after = ports_state()
        for name, up in after.items():
            print(f"  {name:<9} {'back up' if up else 'STILL DOWN'}")
        down = [n for n, up in after.items() if not up]
        if "lmstudio" in down:
            print("  relaunching LM Studio...")
            # DEAD PATH (sirch): C:\Users\sirch\AppData\Local\LM-Studio\LM Studio.exe does not exist on this host.
            for cand in (r"C:\Program Files\LM Studio\LM Studio.exe",):
                if os.path.exists(cand):
                    subprocess.Popen([cand], close_fds=True)
                    print(f"    launched {cand}")
                    break
            else:
                print("    could not find the LM Studio executable; "
                      "start it manually before relying on /probe")
        print("  final ports:", ports_state())


if __name__ == "__main__":
    main()
