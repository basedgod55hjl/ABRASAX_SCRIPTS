"""
ABRASAX SWARM COORDINATOR — Launches all 4 agents simultaneously
Each agent runs in its own PowerShell window.
All query Gemma-4 at the same time via LM Studio API.
Non-stop autonomous swarm operation.
"""
import subprocess
import time
import os
import sys
from datetime import datetime

SCRIPTS_DIR = r"C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX_SCRIPTS"

AGENTS = {
    "Ultimate Master": os.path.join(SCRIPTS_DIR, "agent_ultimate_master.py"),
    "Resource Monitor": os.path.join(SCRIPTS_DIR, "agent_resource_monitor.py"),
    "VLC Orchestrator": os.path.join(SCRIPTS_DIR, "agent_vlc_orchestrator.py"),
    "System Optimizer": os.path.join(SCRIPTS_DIR, "agent_system_optimizer.py"),
    "Chat Interface": os.path.join(SCRIPTS_DIR, "agent_chat.py"),
}

def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    print(f"[{t}] SWARM: {msg}")

def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║     ABRASAX 5-AGENT SWARM — Gemma-4 Powered            ║
║     Master + Resource + VLC + Optimizer + Chat         ║
║     AMD Ryzen 7 4800H | GTX 1660 Ti | Radeon           ║
║     Full PC Control | Web | Downloads | Self-Learning  ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    processes = {}
    
    # Verify all agent files exist
    for name, path in AGENTS.items():
        if not os.path.exists(path):
            log(f"ERROR: {name} not found at {path}")
            return
        log(f"Found: {name}")
    
    log("Launching all agents in separate windows...")
    time.sleep(1)
    
    for name, path in AGENTS.items():
        try:
            # Launch each agent in its own PowerShell window
            if name == "Chat Interface":
                # Chat runs in the current window (interactive)
                proc = subprocess.Popen(
                    ["powershell", "-NoExit", "-Command", f"python '{path}'"],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                # Background agents in their own windows
                proc = subprocess.Popen(
                    ["powershell", "-NoExit", "-Command", f"python '{path}'"],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            processes[name] = proc
            log(f"Launched: {name} (PID: {proc.pid})")
            time.sleep(1)  # Stagger launches slightly
        except Exception as e:
            log(f"Failed to launch {name}: {e}")
    
    log(f"\nAll {len(processes)} agents launched!")
    log("Each agent is querying Gemma-4 independently.")
    log("Resource Monitor: checks every 3s, offloads RAM > 80%")
    log("VLC Orchestrator: manages VLC, combines playlists, auto-restart")
    log("System Optimizer: keeps PC fast, kills bloat, GPU optimization")
    log("Chat Interface: interactive chat with full agent context")
    log("\nPress Ctrl+C to terminate all agents.\n")
    
    try:
        # Keep coordinator alive, monitor agents
        while True:
            for name, proc in list(processes.items()):
                if proc.poll() is not None:
                    log(f"WARNING: {name} exited (code {proc.returncode}) - restarting...")
                    new_proc = subprocess.Popen(
                        ["powershell", "-NoExit", "-Command", f"python '{AGENTS[name]}'"],
                        creationflags=subprocess.CREATE_NEW_CONSOLE
                    )
                    processes[name] = new_proc
                    log(f"Restarted: {name} (PID: {new_proc.pid})")
            
            time.sleep(10)
            
    except KeyboardInterrupt:
        log("\nShutting down swarm...")
        for name, proc in processes.items():
            try:
                proc.terminate()
                log(f"Terminated: {name}")
            except:
                pass
        log("Swarm shutdown complete.")

if __name__ == "__main__":
    main()
