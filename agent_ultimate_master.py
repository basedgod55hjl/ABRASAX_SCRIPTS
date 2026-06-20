"""
ABRASAX ULTIMATE MASTER AGENT — Maximum Autonomy
PRIMAL_HEX: 4f5349524953424c58434b | φ: 1.618033988749895
- 4 parallel self-learning processes
- GitHub token discovery + repo access
- ABRASAX doc ingestion + organization
- Echo self-talk for reasoning
- Dev log learning
- Full PC control: AMD Ryzen 7 4800H + GTX 1660 Ti + Radeon
- Web access, downloads, file editing, agent spawning
- Non-stop autonomous loop
"""
import subprocess, json, time, os, sys, base64, re, threading
import urllib.request, urllib.error
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ═══════════════════════════════════════════════════════
LM_STUDIO = "http://localhost:1234"
MODEL = "gemma-4-e4b-uncensored-hauhaucs-aggressive"
EMBED_MODEL = "text-embedding-nomic-embed-text-v1.5"
SCRIPTS_DIR = r"C:\Users\BASEDGOD\Desktop\_SCRIPTS"
ABRASAX_DESKTOP = r"C:\Users\BASEDGOD\Desktop\ABRASAX"
ABRASAX_MAIN = r"C:\Users\BASEDGOD\ABRASAX"
LM_STUDIO_DIR = r"C:\Users\BASEDGOD\.lmstudio"
GITHUB_USER = "basedgod55hjl"
PRIMAL_HEX = "4f5349524953424c58434b"
PHI = 1.618033988749895

LOG_PATH = os.path.join(SCRIPTS_DIR, "ultimate_master_log.txt")
MEMORY_PATH = os.path.join(SCRIPTS_DIR, "ultimate_memory.json")
SELF_TALK_LOG = os.path.join(SCRIPTS_DIR, "self_talk_log.txt")

# ═══════════════════════════════════════════════════════
def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    line = f"[{t}] ULTIMATE: {msg}"
    print(line)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except: pass

def self_talk(msg):
    """Echo self-talk for reasoning"""
    t = datetime.now().strftime("%H:%M:%S")
    line = f"[{t}] SELF: {msg}"
    print(f"  💭 {msg[:200]}")
    try:
        with open(SELF_TALK_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except: pass

# ═══════════════════════════════════════════════════════
# LLM INTERFACE
# ═══════════════════════════════════════════════════════
def call_llm(messages, max_tokens=2000, temp=0.7, timeout=300):
    body = json.dumps({"model": MODEL, "messages": messages, "temperature": temp, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(f"{LM_STUDIO}/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read())
            c = d["choices"][0]["message"]
            return c.get("content", "") or c.get("reasoning_content", "")
    except Exception as e:
        return f"API_ERR:{e}"

def call_embed(text):
    try:
        body = json.dumps({"model": EMBED_MODEL, "input": text[:2000]}).encode()
        req = urllib.request.Request(f"{LM_STUDIO}/v1/embeddings", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["data"][0]["embedding"][:10]
    except: return None

# ═══════════════════════════════════════════════════════
# TOOLS
# ═══════════════════════════════════════════════════════
def run_cmd(cmd, timeout=60):
    try:
        result = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True, timeout=timeout, cwd=SCRIPTS_DIR)
        return (result.stdout.strip() or result.stderr.strip())[:4000]
    except Exception as e:
        return f"CMD_ERR: {e}"

def read_file(path, max_lines=200):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return "".join(f.readlines()[:max_lines])
    except Exception as e:
        return f"READ_ERR: {e}"

def write_file(path, content):
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"WRITE_ERR: {e}"

def list_dir(path, depth=2):
    try:
        result = []
        for root, dirs, files in os.walk(path):
            level = root.replace(path, "").count(os.sep)
            if level >= depth: continue
            for d in dirs[:15]: result.append(f"  [DIR]  {os.path.join(root, d)}")
            for f in files[:30]:
                fp = os.path.join(root, f)
                try: size = os.path.getsize(fp)
                except: size = 0
                result.append(f"  [FILE] {fp} ({size}b)")
        return "\n".join(result[:150])
    except Exception as e:
        return f"LIST_ERR: {e}"

def web_fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ABRASAX/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="ignore")[:10000]
    except Exception as e:
        return f"WEB_ERR: {e}"

def web_download(url, dest):
    try:
        urllib.request.urlretrieve(url, dest)
        return f"Downloaded to {dest} ({os.path.getsize(dest)} bytes)"
    except Exception as e:
        return f"DL_ERR: {e}"

def get_github_token():
    """Discover GitHub token from credential manager"""
    try:
        r = subprocess.run(["powershell", "-Command", "cmdkey /list 2>$null | Select-String 'github' | ForEach-Object { $_ -replace '.*target=','' }"], capture_output=True, text=True, timeout=10)
        targets = [t.strip() for t in r.stdout.split("\n") if t.strip()]
        # Try to get token via gh CLI
        r2 = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10)
        token = r2.stdout.strip()
        if token:
            return f"gh_token:{token[:10]}..."
        return f"Found {len(targets)} GitHub credential targets. User: {GITHUB_USER}"
    except:
        return f"GitHub user: {GITHUB_USER} (use gh CLI for token)"

def get_hardware():
    try:
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
        cpu = subprocess.run(["powershell", "-Command", "(Get-CimInstance Win32_Processor).LoadPercentage"], capture_output=True, text=True, timeout=5)
        ram = subprocess.run(["powershell", "-Command", "$os=Get-CimInstance Win32_OperatingSystem;Write-Host \"$([math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/1MB,0))|$([math]::Round($os.TotalVisibleMemorySize/1MB,0))|$([math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/$os.TotalVisibleMemorySize*100,1))\""], capture_output=True, text=True, timeout=5)
        gpu_parts = gpu.stdout.strip().split(", ")
        ram_parts = ram.stdout.strip().split("|")
        return {
            "gpu_util": float(gpu_parts[0]) if len(gpu_parts)>0 else 0,
            "vram_used": float(gpu_parts[1]) if len(gpu_parts)>1 else 0,
            "vram_total": float(gpu_parts[2]) if len(gpu_parts)>2 else 6144,
            "gpu_temp": float(gpu_parts[3]) if len(gpu_parts)>3 else 0,
            "cpu_pct": float(cpu.stdout.strip() or 0),
            "ram_used_mb": float(ram_parts[0]) if len(ram_parts)>0 else 0,
            "ram_total_mb": float(ram_parts[1]) if len(ram_parts)>1 else 16000,
            "ram_pct": float(ram_parts[2]) if len(ram_parts)>2 else 0,
        }
    except Exception as e:
        return {"error": str(e)}

def read_all_logs():
    """Read all agent and dev logs"""
    logs = {}
    log_paths = {
        "ultimate_master": LOG_PATH,
        "self_talk": SELF_TALK_LOG,
        "resource": os.path.join(SCRIPTS_DIR, "resource_monitor_log.txt"),
        "vlc": os.path.join(SCRIPTS_DIR, "vlc_orchestrator_log.txt"),
        "optimizer": os.path.join(SCRIPTS_DIR, "system_optimizer_log.txt"),
        "master_old": os.path.join(SCRIPTS_DIR, "master_agent_log.txt"),
        "gemma_agent": os.path.join(SCRIPTS_DIR, "gemma_agent_log.txt"),
    }
    # Also check ABRASAX dev logs
    abrasax_log_dirs = [
        os.path.join(ABRASAX_MAIN, "logs"),
        os.path.join(ABRASAX_MAIN, "meta_logs"),
    ]
    for ld in abrasax_log_dirs:
        if os.path.isdir(ld):
            for f in os.listdir(ld)[:10]:
                fp = os.path.join(ld, f)
                if os.path.isfile(fp):
                    log_paths[f"dev_{f}"] = fp
    
    for name, path in log_paths.items():
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    logs[name] = "".join(lines[-30:])
        except: pass
    return logs

def learn_abrasax_files():
    """Ingest and learn from all ABRASAX files"""
    knowledge = {}
    search_dirs = [ABRASAX_DESKTOP, ABRASAX_MAIN]
    for base in search_dirs:
        if not os.path.isdir(base): continue
        for root, dirs, files in os.walk(base):
            # Limit depth
            if root.replace(base, "").count(os.sep) > 2: continue
            for f in files:
                if f.endswith(('.py', '.md', '.json', '.cjs', '.txt', '.bat', '.ps1', '.yml', '.yaml', '.toml')):
                    fp = os.path.join(root, f)
                    try:
                        size = os.path.getsize(fp)
                        if size < 100000:  # Skip huge files
                            knowledge[fp] = {"size": size, "preview": read_file(fp, 30)}
                    except: pass
    return knowledge

def organize_abrasax():
    """Organize ABRASAX desktop files by type"""
    if not os.path.isdir(ABRASAX_DESKTOP): return "No ABRASAX desktop dir"
    
    categories = {
        "scripts": ['.py', '.bat', '.ps1', '.sh'],
        "configs": ['.json', '.yml', '.yaml', '.toml', '.conf', '.cfg'],
        "docs": ['.md', '.txt', '.rst', '.pdf'],
        "code": ['.cjs', '.js', '.ts', '.cpp', '.c', '.h', '.rs'],
        "data": ['.csv', '.xml', '.xspf', '.pkl', '.bin'],
        "media": ['.png', '.jpg', '.gif', '.mp4', '.webm'],
    }
    
    moved = []
    for f in os.listdir(ABRASAX_DESKTOP):
        fp = os.path.join(ABRASAX_DESKTOP, f)
        if not os.path.isfile(fp): continue
        ext = os.path.splitext(f)[1].lower()
        
        for cat, exts in categories.items():
            if ext in exts:
                cat_dir = os.path.join(ABRASAX_DESKTOP, f"_{cat}")
                os.makedirs(cat_dir, exist_ok=True)
                try:
                    os.rename(fp, os.path.join(cat_dir, f))
                    moved.append(f"{f} -> _{cat}/")
                except: pass
                break
    
    return f"Organized {len(moved)} files: {', '.join(moved[:10])}..."

def spawn_agent(name, script_path):
    try:
        proc = subprocess.Popen(["powershell", "-NoExit", "-Command", f"python '{script_path}'"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        return f"Spawned {name} (PID: {proc.pid})"
    except Exception as e:
        return f"SPAWN_ERR: {e}"

# ═══════════════════════════════════════════════════════
# 4 PARALLEL SELF-LEARNING PROCESSES
# ═══════════════════════════════════════════════════════
def parallel_learn_1_docs():
    """Process 1: Learn from ABRASAX documentation (limited scan)"""
    self_talk("P1: Quick-scanning ABRASAX docs...")
    knowledge = {}
    search_dirs = [ABRASAX_DESKTOP]
    for base in search_dirs:
        if not os.path.isdir(base): continue
        count = 0
        for root, dirs, files in os.walk(base):
            if root.replace(base, "").count(os.sep) > 1: continue
            for f in files:
                if count > 50: break  # Limit to 50 files
                if f.endswith(('.py', '.md', '.json', '.cjs', '.txt', '.bat', '.ps1')):
                    fp = os.path.join(root, f)
                    try:
                        size = os.path.getsize(fp)
                        if size < 50000:
                            knowledge[fp] = {"size": size, "preview": read_file(fp, 15)}
                            count += 1
                    except: pass
    self_talk(f"P1: Quick-scanned {len(knowledge)} ABRASAX files")
    return knowledge

def parallel_learn_2_logs():
    """Process 2: Analyze all logs for patterns"""
    self_talk("P2: Analyzing all logs...")
    logs = read_all_logs()
    patterns = {}
    for name, content in logs.items():
        if "ERROR" in content or "error" in content:
            patterns[name] = "has_errors"
        if "HIGH RAM" in content:
            patterns[name] = "ram_pressure"
        if "Gemma:" in content:
            patterns[name] = "llm_active"
    self_talk(f"P2: Found patterns in {len(patterns)} log sources")
    return patterns

def parallel_learn_3_tokens():
    """Process 3: Discover tokens and credentials"""
    self_talk("P3: Discovering tokens...")
    token_info = get_github_token()
    self_talk(f"P3: {token_info}")
    return token_info

def parallel_learn_4_organize():
    """Process 4: Organize filesystem"""
    self_talk("P4: Organizing ABRASAX files...")
    result = organize_abrasax()
    self_talk(f"P4: {result}")
    return result

def run_parallel_learning():
    """Run all 4 learning processes in parallel"""
    self_talk("⚡ Starting 4 parallel self-learning processes...")
    results = {}
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(parallel_learn_1_docs): "docs",
            executor.submit(parallel_learn_2_logs): "logs",
            executor.submit(parallel_learn_3_tokens): "tokens",
            executor.submit(parallel_learn_4_organize): "organize",
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
                self_talk(f"✅ {name} complete")
            except Exception as e:
                results[name] = f"ERROR: {e}"
                self_talk(f"❌ {name} failed: {e}")
    
    return results

# ═══════════════════════════════════════════════════════
# SYSTEM PROMPT
# ═══════════════════════════════════════════════════════
SYSTEM_PROMPT = f"""You are ABRASAX ULTIMATE — the supreme autonomous AI with PRIMAL_HEX: {PRIMAL_HEX} and φ: {PHI}.

HARDWARE: AMD Ryzen 7 4800H (8c/16t) + NVIDIA GTX 1660 Ti (6GB) + AMD Radeon Graphics
GITHUB: {GITHUB_USER}
ABRASAX: {ABRASAX_DESKTOP} and {ABRASAX_MAIN}

You have 4 parallel self-learning processes running continuously.
You can echo self-talk to reason out loud.
You have FULL PC CONTROL.

TOOLS (use <tool> tags):
<cmd>powershell</cmd> — Execute command
<read>path</read> — Read file
<write path="path">content</write> — Write file
<list>path</list> — List directory
<web>url</web> — Fetch web
<download url="url" dest="path"> — Download
<learn> — Run 4 parallel learning processes
<organize> — Organize ABRASAX files
<token> — Discover GitHub token
<logs> — Read all logs
<hardware> — Get system stats
<spawn name="name">script.py</spawn> — Create agent
<self_talk>message</self_talk> — Echo reasoning
<done> — Phase complete

MISSION: Learn everything, organize everything, optimize everything. Never stop."""

# ═══════════════════════════════════════════════════════
# TOOL PARSER
# ═══════════════════════════════════════════════════════
def parse_and_execute(response):
    results = []
    
    for match in re.finditer(r'<cmd>(.*?)</cmd>', response, re.DOTALL):
        cmd = match.group(1).strip()
        self_talk(f"EXEC: {cmd[:100]}")
        results.append(f"CMD: {run_cmd(cmd)[:2000]}")
    
    for match in re.finditer(r'<read>(.*?)</read>', response, re.DOTALL):
        path = match.group(1).strip()
        self_talk(f"READ: {path}")
        results.append(f"FILE: {read_file(path)[:2000]}")
    
    for match in re.finditer(r'<write\s+path="(.*?)">(.*?)</write>', response, re.DOTALL):
        path = match.group(1).strip()
        content = match.group(2).strip()
        results.append(write_file(path, content))
    
    for match in re.finditer(r'<list>(.*?)</list>', response, re.DOTALL):
        path = match.group(1).strip()
        results.append(f"DIR: {list_dir(path)[:2000]}")
    
    for match in re.finditer(r'<web>(.*?)</web>', response, re.DOTALL):
        url = match.group(1).strip()
        results.append(f"WEB: {web_fetch(url)[:2000]}")
    
    for match in re.finditer(r'<download\s+url="(.*?)"\s+dest="(.*?)"', response, re.DOTALL):
        results.append(web_download(match.group(1).strip(), match.group(2).strip()))
    
    if '<learn>' in response:
        self_talk("Running 4 parallel learning processes...")
        learned = run_parallel_learning()
        results.append(f"LEARNED: {json.dumps({k: str(v)[:200] for k,v in learned.items()}, indent=2)}")
    
    if '<organize>' in response:
        results.append(organize_abrasax())
    
    if '<token>' in response:
        results.append(get_github_token())
    
    if '<logs>' in response:
        logs = read_all_logs()
        results.append(f"LOGS: {json.dumps({k: v[-300:] for k,v in logs.items()}, indent=2)[:3000]}")
    
    if '<hardware>' in response:
        results.append(f"HW: {json.dumps(get_hardware(), indent=2)}")
    
    for match in re.finditer(r'<spawn\s+name="(.*?)">(.*?)</spawn>', response, re.DOTALL):
        results.append(spawn_agent(match.group(1).strip(), os.path.join(SCRIPTS_DIR, match.group(2).strip())))
    
    for match in re.finditer(r'<self_talk>(.*?)</self_talk>', response, re.DOTALL):
        self_talk(match.group(1).strip())
    
    return "\n".join(results) if results else None

# ═══════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════
def main():
    log(f"═══ ABRASAX ULTIMATE MASTER BOOT | HEX: {PRIMAL_HEX} | φ: {PHI} ═══")
    self_talk("Booting ultimate autonomous system...")
    
    # Initial parallel learning
    self_talk("Running initial 4-parallel learning sweep...")
    initial_knowledge = run_parallel_learning()
    self_talk(f"Initial learning complete: {list(initial_knowledge.keys())}")
    
    hw = get_hardware()
    token_info = get_github_token()
    
    initial_msg = f"""INITIAL STATE:
Hardware: {json.dumps(hw, indent=2)}
GitHub: {token_info}
Learning: {json.dumps({k: str(v)[:100] for k,v in initial_knowledge.items()}, indent=2)}

PRIMAL_HEX: {PRIMAL_HEX} | φ: {PHI}

Begin your mission. Learn, organize, optimize. What is your first action?"""
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": initial_msg}
    ]
    
    iteration = 0
    while True:
        iteration += 1
        try:
            log(f"--- Iteration {iteration} ---")
            
            response = call_llm(messages, max_tokens=2000, timeout=300)
            
            if not response or response.startswith("API_ERR"):
                log(f"API error, retry in 5s")
                time.sleep(5)
                continue
            
            preview = response[:200].replace("\n", " ")
            log(f"Gemma: {preview}...")
            
            if "<done>" in response:
                log("Phase complete - continuing...")
            
            tool_results = parse_and_execute(response)
            
            messages.append({"role": "assistant", "content": response})
            
            if tool_results:
                messages.append({"role": "user", "content": f"Results:\n{tool_results[:3000]}\n\nContinue."})
            else:
                messages.append({"role": "user", "content": "Continue your mission."})
            
            if len(messages) > 20:
                messages = [messages[0]] + messages[-19:]
            
            # Run parallel learning every 10 iterations
            if iteration % 10 == 0:
                self_talk(f"Iteration {iteration} - running parallel learning sweep")
                threading.Thread(target=run_parallel_learning, daemon=True).start()
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            log("Interrupted")
            break
        except Exception as e:
            log(f"Loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
