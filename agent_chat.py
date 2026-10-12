"""
ABRASAX CHAT — Fixed interactive chat with hex activation
PRIMAL_HEX: 4f5349524953424c58434b
User can influence entire system. Echo self-talk visible.
"""
import subprocess, json, time, os, sys, urllib.request, urllib.error
from datetime import datetime

LM_STUDIO = "http://localhost:1234"
MODEL = "gemma-4-e4b-uncensored-hauhaucs-aggressive"
SCRIPTS_DIR = r"C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX_SCRIPTS"
CHAT_LOG = os.path.join(SCRIPTS_DIR, "chat_history.json")
PRIMAL_HEX = "4f5349524953424c58434b"

def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    print(f"[{t}] {msg}")

def call_llm(messages, max_tokens=1000, temp=0.7):
    body = json.dumps({"model": MODEL, "messages": messages, "temperature": temp, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(f"{LM_STUDIO}/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read())
            c = d["choices"][0]["message"]
            return c.get("content", "") or c.get("reasoning_content", "")
    except Exception as e:
        return f"API_ERR:{e}"

def get_snapshot():
    try:
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5)
        ram = subprocess.run(["powershell", "-Command", "$os=Get-CimInstance Win32_OperatingSystem;[math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/$os.TotalVisibleMemorySize*100,1)"], capture_output=True, text=True, timeout=5)
        cpu = subprocess.run(["powershell", "-Command", "(Get-CimInstance Win32_Processor).LoadPercentage"], capture_output=True, text=True, timeout=5)
        vlc = subprocess.run(["tasklist", "/fi", "imagename eq vlc.exe"], capture_output=True, text=True, timeout=3)
        gpu_parts = gpu.stdout.strip().split(", ")
        return {
            "gpu": f"{gpu_parts[0]}%" if len(gpu_parts)>0 else "?",
            "vram": f"{gpu_parts[1]}/{gpu_parts[2]}MB" if len(gpu_parts)>2 else "?",
            "temp": f"{gpu_parts[3]}C" if len(gpu_parts)>3 else "?",
            "ram": f"{ram.stdout.strip()}%",
            "cpu": f"{cpu.stdout.strip()}%",
            "vlc": "ON" if "vlc.exe" in vlc.stdout else "OFF"
        }
    except:
        return {"error": "snapshot failed"}

def run_cmd(cmd):
    try:
        r = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True, timeout=30)
        return (r.stdout.strip() or r.stderr.strip())[:3000]
    except Exception as e:
        return f"ERR: {e}"

def get_agent_logs():
    logs = {}
    for name in ["ultimate_master_log", "resource_monitor_log", "vlc_orchestrator_log", "system_optimizer_log", "self_talk_log"]:
        path = os.path.join(SCRIPTS_DIR, f"{name}.txt")
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    logs[name] = "".join(lines[-5:])
        except: pass
    return logs

def save_chat(user_msg, assistant_msg):
    history = []
    if os.path.exists(CHAT_LOG):
        try:
            with open(CHAT_LOG, "r") as f:
                history = json.load(f)
        except: pass
    history.append({"time": datetime.now().isoformat(), "user": user_msg, "assistant": assistant_msg})
    if len(history) > 100: history = history[-100:]
    with open(CHAT_LOG, "w") as f:
        json.dump(history, f, indent=2)

def main():
    print(f"""
╔══════════════════════════════════════════════════════════╗
║     ABRASAX ULTIMATE CHAT — Hex: {PRIMAL_HEX[:16]}...    ║
║     Gemma-4 | GTX 1660 Ti | Ryzen 7 4800H              ║
╠══════════════════════════════════════════════════════════╣
║  SYSTEM COMMANDS (type / then command):                 ║
║  /cmd <ps>     /kill <proc>   /spawn <script>          ║
║  /download <url> <dest>       /web <url>               ║
║  /edit <path> <content>       /read <path>             ║
║  /list <dir>   /optimize      /gpu_reset               ║
║  /learn        /organize      /token                   ║
║  /hex          /status        /agents     /quit        ║
╚══════════════════════════════════════════════════════════╝
""")
    
    sys_msg = {"role": "system", "content": f"""You are ABRASAX ULTIMATE — supreme autonomous AI. PRIMAL_HEX: {PRIMAL_HEX}. Hardware: AMD Ryzen 7 4800H + GTX 1660 Ti + Radeon. GitHub: basedgod55hjl. You have 4 parallel agents running. Answer concisely. Suggest actions. Use hex power."""}
    messages = [sys_msg]
    
    while True:
        try:
            user_input = input("\n YOU > ").strip()
            if not user_input: continue
            
            # Handle commands
            if user_input.startswith("/"):
                parts = user_input[1:].split(maxsplit=1)
                cmd = parts[0].lower()
                arg = parts[1] if len(parts) > 1 else ""
                
                if cmd == "quit":
                    print("\n ABRASAX: Chat closed. Agents continue.")
                    break
                elif cmd == "hex":
                    print(f"\n PRIMAL_HEX: {PRIMAL_HEX}")
                    print(f" PHI: 1.618033988749895")
                    print(f" GitHub: basedgod55hjl")
                    print(f" Agents: Ultimate Master + Resource + VLC + Optimizer")
                    continue
                elif cmd == "status":
                    snap = get_snapshot()
                    print(f"\n GPU:{snap.get('gpu','?')} VRAM:{snap.get('vram','?')} {snap.get('temp','?')}")
                    print(f" RAM:{snap.get('ram','?')} CPU:{snap.get('cpu','?')} VLC:{snap.get('vlc','?')}")
                    continue
                elif cmd == "agents":
                    logs = get_agent_logs()
                    for name, content in logs.items():
                        print(f"\n --- {name} ---")
                        print(content[-500:])
                    continue
                elif cmd == "cmd":
                    print(f"\n {run_cmd(arg)}")
                    continue
                elif cmd == "kill":
                    subprocess.run(["taskkill", "/f", "/im", f"{arg}.exe"], capture_output=True)
                    print(f"\n Killed {arg}")
                    continue
                elif cmd == "spawn":
                    script = os.path.join(SCRIPTS_DIR, arg)
                    subprocess.Popen(["powershell", "-NoExit", "-Command", f"python '{script}'"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                    print(f"\n Spawned {arg}")
                    continue
                elif cmd == "download":
                    parts2 = arg.split(maxsplit=1)
                    if len(parts2) == 2:
                        urllib.request.urlretrieve(parts2[0], parts2[1])
                        print(f"\n Downloaded to {parts2[1]}")
                    continue
                elif cmd == "web":
                    try:
                        req = urllib.request.Request(arg, headers={"User-Agent": "ABRASAX/1.0"})
                        with urllib.request.urlopen(req, timeout=30) as r:
                            print(f"\n{r.read().decode('utf-8', errors='ignore')[:3000]}")
                    except Exception as e:
                        print(f"\n WEB ERR: {e}")
                    continue
                elif cmd == "edit":
                    parts2 = arg.split(maxsplit=1)
                    if len(parts2) == 2:
                        os.makedirs(os.path.dirname(os.path.abspath(parts2[0])), exist_ok=True)
                        with open(parts2[0], "w", encoding="utf-8") as f:
                            f.write(parts2[1])
                        print(f"\n Wrote {len(parts2[1])} bytes to {parts2[0]}")
                    continue
                elif cmd == "read":
                    try:
                        with open(arg, "r", encoding="utf-8", errors="ignore") as f:
                            print(f"\n{f.read()[:3000]}")
                    except Exception as e:
                        print(f"\n READ ERR: {e}")
                    continue
                elif cmd == "list":
                    try:
                        items = os.listdir(arg)
                        print(f"\n {chr(10).join(items[:50])}")
                    except Exception as e:
                        print(f"\n LIST ERR: {e}")
                    continue
                elif cmd == "optimize":
                    subprocess.run(["powercfg", "/setactive", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"], capture_output=True)
                    subprocess.run(["nvidia-smi", "-ac", "5001,1800"], capture_output=True)
                    print("\n OPTIMIZED: High performance + NVIDIA max clocks")
                    continue
                elif cmd == "gpu_reset":
                    subprocess.run(["nvidia-smi", "--gpu-reset-applications-clocks"], capture_output=True)
                    print("\n GPU clocks reset")
                    continue
                elif cmd == "learn":
                    print("\n Triggering parallel learning sweep...")
                    subprocess.Popen(["python", os.path.join(SCRIPTS_DIR, "agent_ultimate_master.py")], creationflags=subprocess.CREATE_NEW_CONSOLE)
                    continue
                elif cmd == "token":
                    try:
                        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=5)
                        print(f"\n GitHub token: {r.stdout.strip()[:20]}...")
                    except:
                        print("\n GitHub user: basedgod55hjl (use gh CLI for token)")
                    continue
            
            # Chat with Gemma
            snap = get_snapshot()
            logs = get_agent_logs()
            log_summary = "\n".join([f"{n}: {c[-200:]}" for n, c in logs.items() if c])
            
            ctx = f"[SYSTEM] GPU:{snap.get('gpu','?')} RAM:{snap.get('ram','?')} CPU:{snap.get('cpu','?')} VLC:{snap.get('vlc','?')}\n[LOGS]\n{log_summary}\n\n[USER] {user_input}"
            
            messages.append({"role": "user", "content": ctx})
            
            print("\n ABRASAX: ", end="", flush=True)
            resp = call_llm(messages, max_tokens=1000)
            
            if "Here's a thinking" in resp:
                parts = resp.split("\n\n")
                resp = parts[-1] if len(parts) > 1 else resp
            
            print(resp)
            save_chat(user_input, resp)
            
            if len(messages) > 15:
                messages = [sys_msg] + messages[-14:]
            
        except KeyboardInterrupt:
            print("\n\n Chat closed. Agents continue.")
            break
        except Exception as e:
            print(f"\n ERR: {e}")

if __name__ == "__main__":
    main()
