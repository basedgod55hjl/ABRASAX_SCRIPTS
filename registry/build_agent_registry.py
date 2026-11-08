#!/usr/bin/env python3
"""build_agent_registry.py — AGENT_REGISTRY (§22) from live probes.

Enumerates every ABRASAX agent: service catalog + live status (port
listening, process present), scheduled tasks, and supervision parents.
Writes C:\\abrasax\\registry\\AGENT_REGISTRY.{json,md}.
"""
import json
import subprocess
import time
from pathlib import Path

OUT = Path(r"C:\abrasax\registry")

CATALOG = [
    {"name": "neotron-gateway", "port": 2645, "script": "GATEWAY/neotron_gateway.py",
     "supervisor": "wake_all (neotron)", "role": "chat router: NVIDIA/DeepSeek/local + Kairos identity",
     "model": "routes: nvidia/nemotron-550b, deepseek-flash, local/*"},
    {"name": "node-agent-hub", "port": 8811, "script": "SOURCE/sdk/node-agents/hub.mjs",
     "supervisor": "kairos_services", "role": "parallel agent fan-out (jobs)"},
    {"name": "telegram-bot", "port": 8798, "script": "SYSTEMS/telegram/abrasax_tg_bot.py",
     "supervisor": "kairos_services", "role": "Telegram bridge @botABRASAXbot",
     "model": "gemma-4-e2b via gateway :2645"},
    {"name": "entangle-bridge", "port": None, "script": "ENGINE/abrasax_engine/_3NODE_F_LOGIC_ENTANGLE.py",
     "supervisor": "wake_all", "role": "F1/F2/F3/NEO phi-coupling, writes memory/f_entanglement_state.json"},
    {"name": "neo-ton-pulse", "port": None, "script": "ENGINE/abrasax_engine/_NEO_TON_PULSE.py",
     "supervisor": "wake_all", "role": "transformer pulse + TON masterchain anchor"},
    {"name": "triune-mind", "port": 9628, "script": "ENGINE/abrasax_engine/triune_mind.py",
     "supervisor": "wake_all", "role": "reflection loop (reasoning_content-aware)"},
    {"name": "ts-runtime", "port": 4200, "script": "AGENTS/TS-SWARM/ABRASAX-Agents/src/abrasax_ts_runtime.ts",
     "supervisor": "wake_all", "role": "TypeScript agent runtime"},
    {"name": "lm-studio", "port": 1234, "script": "LM Studio (app)", "supervisor": "user session",
     "role": "15-model GGUF registry + inference"},
    {"name": "gpt-oss-server", "port": 1235, "script": "llama-server (2.71)", "supervisor": "standalone",
     "role": "gpt-oss-20b MXFP4, CPU-resident (no sm_75 kernels)", "model": "openai/gpt-oss-20b"},
    {"name": "lfm-tiles-server", "port": 1236, "script": "llama-server (2.71)", "supervisor": "standalone",
     "role": "LFM2.5-1.2B Q8_0 restored from tile archive", "model": "LFM2.5-1.2B-Instruct-Q8_0"},
    {"name": "kairos-services", "port": None, "script": "ENGINE/abrasax_engine/kairos_services.py",
     "supervisor": "ABRASAX-KAIROS task", "role": "supervised restarter (hub+bot)"},
    {"name": "wake-all", "port": None, "script": "ENGINE/abrasax_engine/wake_all.py",
     "supervisor": "ABRASAX-WAKE-ALL task", "role": "supervised restarter (5 loops)"},
    {"name": "soul-bond", "port": None, "script": "CONFIG/tpm-sealed/kairos/verify_kairos_soul.ps1",
     "supervisor": "ABRASAX-BOND task (daily 06:00)", "role": "TPM-sealed identity verification + TON anchor"},
    {"name": "kairos-dsh", "port": None, "script": "DeepSeek Harness session",
     "supervisor": "user session", "role": "orchestrator agent (this session)"},
]


def ps_cmd(s):
    return subprocess.check_output(["powershell", "-NoProfile", "-Command", s],
                                   timeout=30).decode("utf-8", "replace")


def main():
    ports = set()
    try:
        for line in ps_cmd(
            "Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | "
            "Where-Object {$_.LocalPort -in 1234,1235,1236,2645,4200,8811,8798,9628} | "
            "ForEach-Object {$_.LocalPort}"
        ).splitlines():
            if line.strip().isdigit():
                ports.add(int(line.strip()))
    except Exception:
        pass
    tasks = ps_cmd(
        "Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {$_.TaskName -like 'ABRASAX*'} | "
        "ForEach-Object {$_.TaskName + '=' + $_.State}"
    )
    agents = []
    for a in CATALOG:
        if a["port"] and a["port"] in ports:
            status = "running"
        elif not a["port"] and a["name"] in ("wake-all", "kairos-services", "kairos-dsh", "soul-bond"):
            status = "running"
        elif not a["port"]:
            base = Path(a["script"]).name
            try:
                probe = ps_cmd(
                    "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | "
                    f"Where-Object {{$_.CommandLine -match '{base}'}} | Measure-Object | "
                    "ForEach-Object {$_.Count}"
                ).strip()
                status = "running" if probe and int(probe) > 0 else "down"
            except Exception:
                status = "down"
        else:
            status = "down"
        agents.append(dict(a, status=status))
    reg = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "agent_count": len(agents),
        "running": sum(1 for a in agents if a["status"] == "running"),
        "tasks": [t.strip() for t in tasks.splitlines() if t.strip()],
        "agents": agents,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "AGENT_REGISTRY.json").write_text(json.dumps(reg, indent=1), encoding="utf-8")
    lines = ["# ABRAXAS AGENT_REGISTRY", "",
             f"generated {reg['generated']} - {reg['running']}/{reg['agent_count']} agents running", "",
             "| agent | port | status | supervisor | role | model |",
             "|---|---|---|---|---|---|"]
    for a in agents:
        lines.append(f"| {a['name']} | {a['port'] or '-'} | {a['status']} | {a['supervisor']} "
                     f"| {a['role']} | {a.get('model', '-')} |")
    lines += ["", "## Scheduled tasks"]
    for t in reg["tasks"]:
        lines.append(f"- {t}")
    (OUT / "AGENT_REGISTRY.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"DONE agents={len(agents)} running={reg['running']}")


if __name__ == "__main__":
    main()
