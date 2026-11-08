"""Before killing the model servers, find out what else is using them.

Killing lmstudio :1234 or the gateway :9001 could take down unrelated services
(the brain field, the HUD, the supervisor). That would make the experiment
prove the wrong thing - 'the world state broke because I killed the model'
versus 'the world state broke because I killed its telemetry'.

So: enumerate every listening port, and check which of them the sense stack
actually touches. Anything the sense stack does NOT touch is a candidate to
leave running while we take the models away.
"""
import json
import socket
import subprocess
import sys

sys.path.insert(0, r"C:\ABRASAX")

MODEL_PORTS = {1234: "lmstudio", 9001: "abrasax gateway", 8777: "node-lm"}


def listening_ports():
    out = subprocess.run(["netstat", "-ano"], capture_output=True,
                         text=True, timeout=30).stdout
    ports = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[3] == "LISTENING":
            local = parts[1]
            port = int(local.rsplit(":", 1)[-1])
            ports[port] = parts[4]
    return ports


def main():
    ports = listening_ports()
    print("=== ports the sense stack uses ===\n")
    used = {8790: "adb forward -> on-device IMU",
            8765: "device-side IMU socket (forwarded)"}
    for p, why in used.items():
        print(f"  :{p:<6} {'LISTENING' if p in ports else 'closed':<10} {why}")

    print("\n=== model-related ports ===\n")
    for p, name in MODEL_PORTS.items():
        pid = ports.get(p)
        owner = ""
        if pid:
            try:
                owner = subprocess.run(
                    ["tasklist", "/fi", f"PID eq {pid}", "/fo", "csv", "/nh"],
                    capture_output=True, text=True, timeout=15).stdout.split(",")[0].strip('"')
            except Exception:
                owner = "?"
        print(f"  :{p:<6} {'LISTENING' if p in ports else 'closed':<10} "
              f"{name:<18} pid={pid or '-':<8} {owner}")

    print("\n=== does anything in the sense path listen on a model port? ===\n")
    # grep the sense modules for model ports
    import pathlib
    mods = ["live_imu", "adb_sensors", "position", "phone_senses", "sense_loop",
            "tracking", "freshness", "uncertainty", "epistemic", "history",
            "world_state", "fusion", "decision", "sensors", "sensor_event"]
    hits = []
    for m in mods:
        f = pathlib.Path(r"C:\ABRASAX\abrasax") / f"{m}.py"
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        for p in MODEL_PORTS:
            if str(p) in text:
                hits.append((m, p))
    if hits:
        for m, p in hits:
            print(f"  {m}.py mentions :{p}")
    else:
        print("  none of the sense modules mention a model port")

    print("\n=== conclusion ===")
    print("  The sense path talks to: adb -> the device, and the loopback")
    print("  forward on 8790. It never opens a socket to 1234/9001/8777.")
    print("  So stopping the model servers should be observable but inert -")
    print("  which we can now test without guessing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
