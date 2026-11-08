"""deploy_layers.py -- bring every ABRASAX layer up, in dependency order, and prove it.

Layers
    L1  LM Studio server + 9B (vision/tools) + nomic embedder
    L2  S25 (adb; wireless mDNS or USB)
    L3  ABRASAX service stack (supervisor -> gateway :9001, UI :8090, brain :9626)
    L4  local_agent brainstorm loop (exactly one)
    L5  corpus / notes

Why a script and not a checklist: the box has one 6 GB GPU and several GPU
consumers. The 9B at full offload (5.15 GiB) leaves nothing for the stack, and the
supervisor then declares live services dead, restarts them, and leaves duplicates
bound to :9624. `--vram balanced` loads the model at 0.80 so the stack has headroom.

Usage
    python SCRIPTS/deploy_layers.py            # inspect only
    python SCRIPTS/deploy_layers.py --apply    # start/repair what is missing
    python SCRIPTS/deploy_layers.py --apply --vram full
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "GATEWAY"))

LMS = str(Path.home() / ".lmstudio" / "bin" / "lms.exe")
MODEL = "huihui-qwen3.5-9b-abliterated@q3_k_m"
EMBED = "text-embedding-nomic-embed-text-v1.5"
STATE = ROOT / "DEPLOY-STATE.json"
LOG = ROOT / "BRAINSTORM" / "loop.log"
PHONE_SERIAL = "R5CY308WZVK"
PHONE_MDNS = "192.168.1.209:41625"

results: list[dict] = []


def sh(cmd: str, timeout: int = 180) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=str(ROOT))
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"


def http(url: str, timeout: float = 4.0, headers: dict | None = None) -> tuple[int, str]:
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(400).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(200).decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}"


def record(layer: str, ok: bool, detail: str, fixed: str = "") -> None:
    results.append({"layer": layer, "ok": ok, "detail": detail, "fixed": fixed})
    print(f"[{'OK  ' if ok else 'FAIL'}] {layer:22s} {detail}" + (f"  -> {fixed}" if fixed else ""))


def vram() -> str:
    _, out = sh('nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader', 30)
    return out.strip()


# ------------------------------------------------------------------ L1 LM Studio
def layer_lmstudio(apply: bool, vram_mode: str) -> None:
    key = os.environ.get("LM_STUDIO_API_KEY") or os.environ.get("LM_API_KEY") or ""
    code, body = http("http://127.0.0.1:1234/v1/models", headers={"Authorization": f"Bearer {key}"})
    if code != 200:
        if not apply:
            record("L1 lmstudio", False, f"server not answering ({code})")
            return
        rc, out = sh(f'"{LMS}" server start --port 1234', 180)
        time.sleep(4)
        code, body = http("http://127.0.0.1:1234/v1/models", headers={"Authorization": f"Bearer {key}"})
        note = "started server" if code == 200 else f"start failed rc={rc} {out[-120:]}"
        record("L1 lmstudio", code == 200, f"HTTP {code}", note)
        if code != 200:
            return
    else:
        record("L1 lmstudio", True, "server up")

    # model resident? `lms ps` is the truth: the API's loaded_instances id can be a
    # random label ("sb9b"), so matching m["key"] there reports a false negative.
    rc, ps_out = sh(f'"{LMS}" ps', 60)
    instances = [ln for ln in ps_out.splitlines() if "huihui-qwen3.5-9b-abliterated" in ln]
    resident = bool(instances)
    if resident and len(instances) == 1:
        record("L1 model", True, f"resident ({instances[0].split()[0]})")
    elif apply:
        gpu = "max" if vram_mode == "full" else "0.8"
        sh(f'"{LMS}" unload --all', 120)
        time.sleep(4)
        rc, out = sh(f'"{LMS}" load "{MODEL}" --gpu {gpu} --context-length 2048 --ttl 604800 -y', 600)
        rc, ps_out = sh(f'"{LMS}" ps', 60)
        instances = [ln for ln in ps_out.splitlines() if "huihui-qwen3.5-9b-abliterated" in ln]
        record("L1 model", bool(instances), f"gpu={gpu} ctx=2048 ttl=7d",
               "reloaded" if instances else out[-160:])
    else:
        record("L1 model", bool(resident), f"instances={len(instances)}")

    # embedder
    payload = json.dumps({"model": EMBED, "input": "phi"}).encode()
    req = urllib.request.Request("http://127.0.0.1:1234/v1/embeddings", data=payload,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.load(r)
        dim = len(d["data"][0]["embedding"])
        record("L1 embedder", dim == 768, f"{dim}-d")
    except Exception as e:  # noqa: BLE001
        record("L1 embedder", False, f"{type(e).__name__}: {e}")


# ----------------------------------------------------------------------- L2 phone
def layer_phone(apply: bool) -> None:
    rc, out = sh("adb devices", 60)
    # Wireless entries are IP:port; only a USB entry shows the serial. Confirm by model.
    endpoint_live = None
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            model = sh(f"adb -s {parts[0]} shell getprop ro.product.model", 20)[1].strip()
            if model == "SM-S938U":
                endpoint_live = parts[0]
                break
    if endpoint_live:
        record("L2 S25", True, f"{endpoint_live} SM-S938U")
        return
    # Wireless debugging rotates its port every session; ask mDNS for the current
    # endpoint instead of reusing a stale host:port from a previous run.
    endpoint = PHONE_MDNS
    rc, mdns = sh("adb mdns services", 30)
    m = re.search(rf"adb-{PHONE_SERIAL}-\S+\s+_adb-tls-connect\._tcp\s+(\S+)", mdns)
    if m:
        endpoint = m.group(1)
    if not apply:
        record("L2 S25", False, f"not attached (mdns {endpoint})")
        return
    sh("adb start-server", 60)
    sh(f"adb connect {endpoint}", 60)
    time.sleep(2)
    rc, out = sh(f"adb -s {endpoint} shell getprop ro.product.model", 30)
    ok = "SM-S938U" in out
    record("L2 S25", ok, f"{endpoint} {out.strip()[:24]}",
           "adb connect" if ok else "plug USB / enable wireless debugging")


# ----------------------------------------------------------------------- L3 stack
def layer_stack(apply: bool) -> None:
    hb = ROOT / "LOGS" / "supervisor-heartbeat.txt"
    age = None
    if hb.exists():
        txt = hb.read_text(encoding="utf-8", errors="replace").strip()
        m = re.search(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)", txt)
        if m:
            try:
                from datetime import datetime, timezone
                t = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - t).total_seconds()
            except ValueError:
                pass
    # A tick is interval + work: with the GPU busy, health probes and restarts can make
    # one tick ~90 s, so a 30 s interval yields ~120 s between heartbeats. 180 s is the
    # honest freshness bound; 90 s flagged a perfectly alive supervisor as dead.
    record("L3 supervisor", age is not None and age < 180, f"heartbeat {age:.0f}s" if age else "no heartbeat")

    checks = [("gateway", "http://127.0.0.1:9001/health"), ("ui", "http://127.0.0.1:8090/"),
              ("brain", "http://127.0.0.1:9626/health")]
    for name, url in checks:
        code, _ = http(url, timeout=8)
        if code == 0 and apply:
            time.sleep(12)  # one supervisor tick
            code, _ = http(url, timeout=8)
        record(f"L3 {name}", code != 0, f"HTTP {code}")

    for port in (9624, 9626):
        rc, out = sh(f'netstat -ano | grep LISTENING | grep ":{port} " | wc -l', 30)
        n = int(out.strip() or 0)
        record(f"L3 :{port} listeners", n <= 1, f"{n} processes bound",
               "duplicates from restart loop" if n > 1 else "")


# ----------------------------------------------------------------------- L4 agent
def loop_pids() -> list[int]:
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*local_agent*' "
          "-and $_.Name -eq 'python.exe' } | ForEach-Object { $_.ProcessId }")
    rc, out = sh(f'powershell -NoProfile -Command "{ps}"', 60)
    return [int(x) for x in re.findall(r"\d+", out)]


def layer_agent(apply: bool) -> None:
    pids = loop_pids()
    if len(pids) > 1 and apply:
        for pid in pids[1:]:
            sh(f"taskkill /PID {pid} /F", 30)
        time.sleep(1)
        pids = loop_pids()
        record("L4 agent loop", len(pids) == 1, f"killed extras, {len(pids)} left")
    elif not pids and apply:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        py = str(ROOT / "PYTHON" / ".venv_gui" / "Scripts" / "python.exe")
        with LOG.open("a", encoding="utf-8") as fh:
            p = subprocess.Popen([py, str(ROOT / "GATEWAY" / "local_agent.py"), "--loop", "0", "--limit", "3"],
                                 cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT,
                                 creationflags=0x00000008 | 0x00000200)  # DETACHED_PROCESS|NEW_GROUP
        time.sleep(3)
        record("L4 agent loop", True, f"spawned pid {p.pid}")
    else:
        record("L4 agent loop", len(pids) == 1, f"{len(pids)} process(es)")

    corpus = ROOT / "BRAINSTORM" / "corpus.jsonl"
    rows = 0
    if corpus.exists():
        rows = sum(1 for line in corpus.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())
    notes = len(list((ROOT / "BRAINSTORM" / "notes").glob("*.md"))) if (ROOT / "BRAINSTORM" / "notes").is_dir() else 0
    record("L5 corpus", rows > 0, f"{rows} rows, {notes} notes")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--vram", choices=["balanced", "full"], default="balanced")
    a = ap.parse_args()

    print(f"VRAM before: {vram()}")
    layer_lmstudio(a.apply, a.vram)
    layer_phone(a.apply)
    layer_stack(a.apply)
    layer_agent(a.apply)
    print(f"VRAM after:  {vram()}")

    failed = [r for r in results if not r["ok"]]
    STATE.write_text(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                 "apply": a.apply, "vram": vram(), "layers": results,
                                 "failed": len(failed)}, indent=2) + "\n", encoding="utf-8")
    print(f"\n{len(results) - len(failed)}/{len(results)} layers OK -> {STATE}")


if __name__ == "__main__":
    raise SystemExit(main())
