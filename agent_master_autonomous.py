"""
ABRASAX MASTER AUTONOMOUS AGENT — Full PC Control
- AMD Ryzen 7 4800H CPU (8 cores, 16 threads) + AMD Radeon Graphics + NVIDIA GTX 1660 Ti
- Web access, downloads, file editing, source code modification
- LM Studio self-configuration from docs
- ABRASAX doc learning, token upload, gateway connection
- Reads logs to understand history, self-optimizes
- Spawns sub-agents, distributes work across CPU/GPU
- Non-stop reasoning loop
"""
import subprocess
import json
import time
import os
import sys
import base64
import urllib.request
import urllib.error
import urllib.parse
import shutil
import threading
import re
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════
LM_STUDIO = "http://localhost:1234"
MODEL = "gemma-4-e4b-uncensored-hauhaucs-aggressive"
EMBED_MODEL = "text-embedding-nomic-embed-text-v1.5"
SCRIPTS_DIR = r"C:\Users\BASEDGOD\Desktop\_SCRIPTS"
ABRASAX_DIR = r"C:\Users\BASEDGOD\ABRASAX"
LM_STUDIO_DIR = r"C:\Users\BASEDGOD\.lmstudio"
LOG_PATH = os.path.join(SCRIPTS_DIR, "master_agent_log.txt")
MEMORY_PATH = os.path.join(SCRIPTS_DIR, "master_memory.json")
STATE_PATH = os.path.join(SCRIPTS_DIR, "master_state.json")

# ═══════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════
def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    line = f"[{t}] MASTER: {msg}"
    print(line)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass

# ═══════════════════════════════════════════════════════════
# LLM INTERFACE
# ═══════════════════════════════════════════════════════════
def call_llm(messages, max_tokens=2000, temp=0.7, timeout=300):
    body = json.dumps({"model": MODEL, "messages": messages, "temperature": temp, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(f"{LM_STUDIO}/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read())
            c = d["choices"][0]["message"]
            content = c.get("content", "") or c.get("reasoning_content", "")
            return content
    except Exception as e:
        return f"API_ERR:{e}"

def call_embed(text):
    try:
        body = json.dumps({"model": EMBED_MODEL, "input": text[:2000]}).encode()
        req = urllib.request.Request(f"{LM_STUDIO}/v1/embeddings", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["data"][0]["embedding"][:10]
    except:
        return None

# ═══════════════════════════════════════════════════════════
# TOOLS — Full PC Control
# ═══════════════════════════════════════════════════════════

def run_cmd(cmd, timeout=60):
    """Execute any PowerShell command"""
    try:
        result = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True, timeout=timeout, cwd=SCRIPTS_DIR)
        return (result.stdout.strip() or result.stderr.strip())[:4000]
    except Exception as e:
        return f"CMD_ERR: {e}"

def run_cmd_async(cmd):
    """Execute command without waiting"""
    try:
        subprocess.Popen(["powershell", "-Command", cmd], creationflags=subprocess.CREATE_NO_WINDOW)
        return "Launched async"
    except Exception as e:
        return f"ASYNC_ERR: {e}"

def read_file(path, max_lines=200):
    """Read any file"""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            return "".join(lines[:max_lines])
    except Exception as e:
        return f"READ_ERR: {e}"

def write_file(path, content):
    """Write/create any file"""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"WRITE_ERR: {e}"

def list_dir(path, depth=2):
    """List directory contents"""
    try:
        result = []
        for root, dirs, files in os.walk(path):
            level = root.replace(path, "").count(os.sep)
            if level >= depth:
                continue
            for d in dirs[:10]:
                result.append(f"  [DIR]  {os.path.join(root, d)}")
            for f in files[:20]:
                fp = os.path.join(root, f)
                size = os.path.getsize(fp)
                result.append(f"  [FILE] {fp} ({size} bytes)")
        return "\n".join(result[:100])
    except Exception as e:
        return f"LIST_ERR: {e}"

def web_fetch(url):
    """Fetch web content"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ABRASAX/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            content = r.read().decode("utf-8", errors="ignore")[:10000]
            return content
    except Exception as e:
        return f"WEB_ERR: {e}"

def web_download(url, dest):
    """Download file from web"""
    try:
        urllib.request.urlretrieve(url, dest)
        return f"Downloaded to {dest} ({os.path.getsize(dest)} bytes)"
    except Exception as e:
        return f"DL_ERR: {e}"

def take_screenshot():
    """Capture screen as base64"""
    ps = '''
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bm=New-Object System.Drawing.Bitmap($b.Width,$b.Height)
$g=[System.Drawing.Graphics]::FromImage($bm)
$g.CopyFromScreen($b.X,$b.Y,0,0,$b.Size)
$bm.Save("''' + SCRIPTS_DIR.replace('\\','\\\\') + '''\\screen.png",[System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose();$bm.Dispose()
'''
    subprocess.run(["powershell", "-Command", ps], capture_output=True, timeout=15)
    sp = os.path.join(SCRIPTS_DIR, "screen.png")
    if os.path.exists(sp):
        with open(sp, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

def get_hardware():
    """Get full hardware state"""
    try:
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,clocks.sm,clocks.mem", "--format=csv,noheader"], capture_output=True, text=True, timeout=10)
        cpu = subprocess.run(["powershell", "-Command", "(Get-CimInstance Win32_Processor).LoadPercentage"], capture_output=True, text=True, timeout=5)
        ram = subprocess.run(["powershell", "-Command", "$os=Get-CimInstance Win32_OperatingSystem;Write-Host \"$([math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/1MB,0))|$([math]::Round($os.TotalVisibleMemorySize/1MB,0))|$([math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/$os.TotalVisibleMemorySize*100,1))\""], capture_output=True, text=True, timeout=5)
        disk = subprocess.run(["powershell", "-Command", "(Get-PSDrive C).Free/1GB"], capture_output=True, text=True, timeout=5)
        procs = subprocess.run(["powershell", "-Command", "(Get-Process).Count"], capture_output=True, text=True, timeout=5)
        
        ram_parts = ram.stdout.strip().split("|")
        return {
            "nvidia_gpu": gpu.stdout.strip(),
            "cpu_pct": float(cpu.stdout.strip() or 0),
            "ram_used_mb": float(ram_parts[0]) if len(ram_parts) > 0 else 0,
            "ram_total_mb": float(ram_parts[1]) if len(ram_parts) > 1 else 16000,
            "ram_pct": float(ram_parts[2]) if len(ram_parts) > 2 else 0,
            "disk_free_gb": float(disk.stdout.strip() or 0),
            "proc_count": int(procs.stdout.strip() or 0),
        }
    except Exception as e:
        return {"error": str(e)}

def read_logs():
    """Read all agent logs to understand history"""
    logs = {}
    log_files = {
        "master": LOG_PATH,
        "resource": os.path.join(SCRIPTS_DIR, "resource_monitor_log.txt"),
        "vlc": os.path.join(SCRIPTS_DIR, "vlc_orchestrator_log.txt"),
        "optimizer": os.path.join(SCRIPTS_DIR, "system_optimizer_log.txt"),
        "gemma_agent": os.path.join(SCRIPTS_DIR, "gemma_agent_log.txt"),
    }
    for name, path in log_files.items():
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    logs[name] = "".join(lines[-20:])  # Last 20 lines
        except:
            pass
    return logs

def learn_abrasax_docs():
    """Read ABRASAX documentation for context"""
    docs = {}
    key_paths = [
        os.path.join(ABRASAX_DIR, "CLAUDE.md"),
        os.path.join(ABRASAX_DIR, "README.md"),
        os.path.join(ABRASAX_DIR, "docs"),
        os.path.join(ABRASAX_DIR, "config"),
        os.path.join(ABRASAX_DIR, "core"),
    ]
    for path in key_paths:
        try:
            if os.path.isfile(path):
                docs[os.path.basename(path)] = read_file(path, 100)
            elif os.path.isdir(path):
                for f in os.listdir(path)[:5]:
                    fp = os.path.join(path, f)
                    if os.path.isfile(fp) and f.endswith(('.md', '.json', '.py', '.cjs', '.txt')):
                        docs[f] = read_file(fp, 50)
        except:
            pass
    return docs

def learn_lm_studio_docs():
    """Read LM Studio configuration for self-optimization"""
    configs = {}
    key_files = [
        os.path.join(LM_STUDIO_DIR, "settings.json"),
        os.path.join(LM_STUDIO_DIR, ".internal", "hardware-config.json"),
        os.path.join(LM_STUDIO_DIR, ".internal", "http-server-config.json"),
        os.path.join(LM_STUDIO_DIR, ".internal", "backend-preferences-v1.json"),
        os.path.join(LM_STUDIO_DIR, ".internal", "model-data.json"),
    ]
    for path in key_files:
        try:
            if os.path.exists(path):
                configs[os.path.basename(path)] = read_file(path, 100)
        except:
            pass
    return configs

def optimize_lm_studio():
    """Auto-configure LM Studio for maximum performance"""
    changes = []
    
    # Force all GPU layers
    hw_config = {
        "json": [[
            "llama.cpp-win-x86_64-nvidia-cuda12-avx2",
            {"fields": [
                {"key": "load.gpuStrictVramCap", "value": False},
                {"key": "load.nGpuLayers", "value": 999},
                {"key": "load.noMemoryForge", "value": False}
            ]}
        ]],
        "meta": {"values": ["map"]}
    }
    write_file(os.path.join(LM_STUDIO_DIR, ".internal", "hardware-config.json"), json.dumps(hw_config, indent=2))
    changes.append("GPU layers=999, VRAM cap OFF")
    
    # Max server config
    server_config = {
        "autoStartOnLaunch": True, "port": 1234, "cors": True,
        "logSensitiveData": True, "logIncomingTokens": True, "verbose": True,
        "logLinesLimit": 5000, "networkInterface": "0.0.0.0",
        "justInTimeModelLoading": True, "fileLoggingMode": "full",
        "maxConcurrentRequests": 20, "requestTimeoutMs": 900000
    }
    write_file(os.path.join(LM_STUDIO_DIR, ".internal", "http-server-config.json"), json.dumps(server_config, indent=2))
    changes.append("Server: 20 concurrent, 900s timeout")
    
    return "; ".join(changes)

def spawn_agent(name, script_path):
    """Spawn a new sub-agent"""
    try:
        proc = subprocess.Popen(
            ["powershell", "-NoExit", "-Command", f"python '{script_path}'"],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        return f"Spawned {name} (PID: {proc.pid})"
    except Exception as e:
        return f"SPAWN_ERR: {e}"

def kill_process(name):
    """Kill a process by name"""
    try:
        subprocess.run(["taskkill", "/f", "/im", f"{name}.exe"], capture_output=True, timeout=10)
        return f"Killed {name}"
    except:
        return f"Failed to kill {name}"

def set_amd_power():
    """Set AMD CPU/GPU to max performance"""
    cmds = [
        "powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",  # High performance
        "powercfg -attributes SUB_PROCESSOR 06cadf0e-64ed-448a-8927-ce7bf90eb35d -ATTRIB_HIDE",
    ]
    results = []
    for cmd in cmds:
        results.append(run_cmd(cmd, 10))
    return "; ".join(results)

# ═══════════════════════════════════════════════════════════
# MEMORY SYSTEM
# ═══════════════════════════════════════════════════════════
def load_memory():
    if os.path.exists(MEMORY_PATH):
        try:
            with open(MEMORY_PATH, "r") as f:
                return json.load(f)
        except:
            pass
    return {"tasks_completed": [], "learned_files": [], "system_state": "boot", "iterations": 0}

def save_memory(mem):
    with open(MEMORY_PATH, "w") as f:
        json.dump(mem, f, indent=2)

def save_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

# ═══════════════════════════════════════════════════════════
# MASTER SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════
SYSTEM_PROMPT = """You are ABRASAX MASTER — the supreme autonomous AI controller of this Windows PC.

HARDWARE:
- CPU: AMD Ryzen 7 4800H (8 cores, 16 threads, 2.9GHz)
- GPU: NVIDIA GTX 1660 Ti (6GB VRAM) + AMD Radeon Graphics (512MB)
- RAM: 16GB DDR4
- OS: Windows

YOUR CAPABILITIES (use these tools via <tool> tags):
- <cmd>powershell command</cmd> — Execute any command
- <read>filepath</read> — Read any file
- <write path="filepath">content</write> — Write/create any file
- <list>directory</list> — List directory contents
- <web>url</web> — Fetch web page
- <download url="url" dest="path"> — Download file
- <screenshot> — Take screenshot (I'll show you)
- <spawn name="agent_name">script.py</spawn> — Create new agent
- <kill>process_name</kill> — Kill process
- <learn_abrasax> — Read ABRASAX docs
- <learn_lmstudio> — Read LM Studio configs
- <optimize_lmstudio> — Auto-configure LM Studio
- <hardware> — Get hardware stats
- <logs> — Read all agent logs
- <memory key="key">value</memory> — Store in persistent memory
- <done> — Signal task completion

YOUR MISSION:
1. Read all logs to understand what has been done
2. Learn from ABRASAX docs and LM Studio configs
3. Optimize LM Studio for maximum performance
4. Organize the entire PC filesystem
5. Create new agents as needed
6. Use web to download tools/data
7. Edit source code to improve everything
8. Distribute work across CPU (AMD) and GPU (NVIDIA)
9. Keep PC running fast and smooth
10. Never stop reasoning and improving

Respond with ONE tool action at a time. Be decisive. Think then act."""

# ═══════════════════════════════════════════════════════════
# TOOL PARSER
# ═══════════════════════════════════════════════════════════
def parse_and_execute(response):
    """Parse Gemma's response and execute tools"""
    results = []
    
    # <cmd>...</cmd>
    for match in re.finditer(r'<cmd>(.*?)</cmd>', response, re.DOTALL):
        cmd = match.group(1).strip()
        log(f"EXEC: {cmd[:150]}")
        output = run_cmd(cmd)
        results.append(f"CMD OUTPUT:\n{output[:2000]}")
    
    # <read>path</read>
    for match in re.finditer(r'<read>(.*?)</read>', response, re.DOTALL):
        path = match.group(1).strip()
        log(f"READ: {path}")
        content = read_file(path)
        results.append(f"FILE CONTENT ({path}):\n{content[:2000]}")
    
    # <write path="...">content</write>
    for match in re.finditer(r'<write\s+path="(.*?)">(.*?)</write>', response, re.DOTALL):
        path = match.group(1).strip()
        content = match.group(2).strip()
        log(f"WRITE: {path}")
        result = write_file(path, content)
        results.append(result)
    
    # <list>path</list>
    for match in re.finditer(r'<list>(.*?)</list>', response, re.DOTALL):
        path = match.group(1).strip()
        log(f"LIST: {path}")
        content = list_dir(path)
        results.append(f"DIRECTORY ({path}):\n{content[:2000]}")
    
    # <web>url</web>
    for match in re.finditer(r'<web>(.*?)</web>', response, re.DOTALL):
        url = match.group(1).strip()
        log(f"WEB: {url}")
        content = web_fetch(url)
        results.append(f"WEB CONTENT ({url}):\n{content[:2000]}")
    
    # <download url="..." dest="...">
    for match in re.finditer(r'<download\s+url="(.*?)"\s+dest="(.*?)"', response, re.DOTALL):
        url = match.group(1).strip()
        dest = match.group(2).strip()
        log(f"DOWNLOAD: {url} -> {dest}")
        result = web_download(url, dest)
        results.append(result)
    
    # <spawn name="...">script</spawn>
    for match in re.finditer(r'<spawn\s+name="(.*?)">(.*?)</spawn>', response, re.DOTALL):
        name = match.group(1).strip()
        script = match.group(2).strip()
        script_path = os.path.join(SCRIPTS_DIR, script)
        log(f"SPAWN: {name} -> {script_path}")
        result = spawn_agent(name, script_path)
        results.append(result)
    
    # <kill>process</kill>
    for match in re.finditer(r'<kill>(.*?)</kill>', response, re.DOTALL):
        proc = match.group(1).strip()
        log(f"KILL: {proc}")
        result = kill_process(proc)
        results.append(result)
    
    # <learn_abrasax>
    if '<learn_abrasax>' in response:
        log("LEARNING ABRASAX DOCS")
        docs = learn_abrasax_docs()
        results.append(f"ABRASAX DOCS:\n{json.dumps({k: v[:200] for k, v in docs.items()}, indent=2)}")
    
    # <learn_lmstudio>
    if '<learn_lmstudio>' in response:
        log("LEARNING LM STUDIO CONFIGS")
        configs = learn_lm_studio_docs()
        results.append(f"LM STUDIO CONFIGS:\n{json.dumps({k: v[:200] for k, v in configs.items()}, indent=2)}")
    
    # <optimize_lmstudio>
    if '<optimize_lmstudio>' in response:
        log("OPTIMIZING LM STUDIO")
        result = optimize_lm_studio()
        results.append(f"LM STUDIO OPTIMIZED: {result}")
    
    # <hardware>
    if '<hardware>' in response:
        hw = get_hardware()
        results.append(f"HARDWARE:\n{json.dumps(hw, indent=2)}")
    
    # <logs>
    if '<logs>' in response:
        logs = read_logs()
        results.append(f"AGENT LOGS:\n{json.dumps({k: v[-500:] for k, v in logs.items()}, indent=2)}")
    
    # <memory key="...">value</memory>
    for match in re.finditer(r'<memory\s+key="(.*?)">(.*?)</memory>', response, re.DOTALL):
        key = match.group(1).strip()
        value = match.group(2).strip()
        mem = load_memory()
        mem[key] = value
        emb = call_embed(value)
        if emb:
            mem[f"{key}_embed"] = emb
        save_memory(mem)
        results.append(f"MEMORY STORED: {key}")
    
    return "\n".join(results) if results else None

# ═══════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════
def main():
    log("═══ ABRASAX MASTER AUTONOMOUS AGENT BOOT ═══")
    log("CPU: AMD Ryzen 7 4800H | GPU: GTX 1660 Ti + Radeon")
    
    # Initial optimization
    log("Running initial optimizations...")
    set_amd_power()
    optimize_lm_studio()
    
    # Learn existing state
    memory = load_memory()
    logs = read_logs()
    hw = get_hardware()
    
    log(f"Memory: {len(memory.get('tasks_completed',[]))} tasks recorded")
    log(f"Hardware: CPU {hw.get('cpu_pct','?')}% RAM {hw.get('ram_pct','?')}%")
    
    # Build initial context (text-only for speed)
    log_summary = "\n".join([f"{k}: {v[-300:]}" for k, v in logs.items() if v])
    
    initial_msg = f"""INITIAL SYSTEM STATE:
Hardware: {json.dumps(hw, indent=2)}

Recent Agent Logs:
{log_summary}

Memory: {json.dumps(memory, indent=2)}

Begin your mission. Read logs, learn docs, optimize everything. What is your first action?"""
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": initial_msg}
    ]
    
    iteration = 0
    max_iterations = 500
    last_screenshot = 0
    
    while iteration < max_iterations:
        iteration += 1
        memory["iterations"] = iteration
        
        try:
            log(f"--- Iteration {iteration} ---")
            
            response = call_llm(messages, max_tokens=2000, timeout=300)
            
            if not response or response.startswith("API_ERR"):
                log(f"API error, retry in 5s")
                time.sleep(5)
                continue
            
            # Log response preview
            preview = response[:200].replace("\n", " ")
            log(f"Gemma: {preview}...")
            
            # Check for done signal
            if "<done>" in response:
                log("Gemma signaled DONE for this phase")
                memory["tasks_completed"].append(f"phase_{iteration}")
                save_memory(memory)
            
            # Execute tools
            tool_results = parse_and_execute(response)
            
            # Build next message
            messages.append({"role": "assistant", "content": response})
            
            if tool_results:
                messages.append({"role": "user", "content": f"Tool results:\n{tool_results}\n\nContinue your mission. What next?"})
            else:
                # Take screenshot every 5 iterations for visual feedback
                if iteration - last_screenshot >= 5:
                    time.sleep(2)
                    screenshot_b64 = take_screenshot()
                    if screenshot_b64:
                        last_screenshot = iteration
                        messages.append({"role": "user", "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}},
                            {"type": "text", "text": "Current screen. Continue your mission."}
                        ]})
                    else:
                        messages.append({"role": "user", "content": "Continue your mission. What next?"})
                else:
                    messages.append({"role": "user", "content": "Continue your mission. What next?"})
            
            # Keep message history manageable
            if len(messages) > 25:
                messages = [messages[0]] + messages[-24:]
            
            # Save state periodically
            if iteration % 10 == 0:
                save_memory(memory)
                save_state({"iteration": iteration, "timestamp": datetime.now().isoformat()})
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            log("Interrupted by user")
            break
        except Exception as e:
            log(f"Loop error: {e}")
            time.sleep(5)
    
    save_memory(memory)
    log(f"Master agent completed {iteration} iterations")

if __name__ == "__main__":
    main()
