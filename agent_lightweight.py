"""
ABRASAX LIGHTWEIGHT MASTER — RAM-safe single agent
PRIMAL_HEX: 4f5349524953424c58434b
Single process, minimal RAM, all capabilities.
Learns from ABRASAX, organizes files, manages VLC, monitors system.
Uses Gemma-4 for reasoning. Self-talk for transparency.
"""
import subprocess, json, time, os, sys, re, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path

LM_STUDIO = "http://localhost:1234"
MODEL = "gemma-4-e4b-uncensored-hauhaucs-aggressive"
SCRIPTS_DIR = r"C:\Users\BASEDGOD\Desktop\_SCRIPTS"
ABRASAX_DESKTOP = r"C:\Users\BASEDGOD\Desktop\ABRASAX"
ABRASAX_MAIN = r"C:\Users\BASEDGOD\ABRASAX"
VLC_EXE = r"C:\Program Files\VideoLAN\VLC\vlc.exe"
PLAYLIST = r"C:\Users\BASEDGOD\Desktop\VLC_ABRASAX\playlists\ABRASAX_VLC_MASTER.xspf"
PRIMAL_HEX = "4f5349524953424c58434b"
GITHUB_USER = "basedgod55hjl"

LOG_PATH = os.path.join(SCRIPTS_DIR, "lightweight_master_log.txt")

def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    line = f"[{t}] {msg}"
    print(line)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except: pass

def self_talk(msg):
    print(f"  💭 {msg[:150]}")

def call_llm(messages, max_tokens=800, temp=0.7, timeout=120):
    """Call Gemma - keep messages small"""
    body = json.dumps({"model": MODEL, "messages": messages, "temperature": temp, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(f"{LM_STUDIO}/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read())
            c = d["choices"][0]["message"]
            return c.get("content", "") or c.get("reasoning_content", "")
    except Exception as e:
        return f"API_ERR:{e}"

def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True, timeout=timeout)
        return (r.stdout.strip() or r.stderr.strip())[:2000]
    except: return "CMD_ERR"

def read_file(path, max_lines=50):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return "".join(f.readlines()[:max_lines])
    except: return "READ_ERR"

def write_file(path, content):
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote {len(content)}b to {os.path.basename(path)}"
    except: return "WRITE_ERR"

def get_system():
    """Lightweight system check"""
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
    except: return {"error": "sys check failed"}

def launch_vlc():
    """Launch VLC with GPU enhancements"""
    if not os.path.exists(PLAYLIST):
        return "Playlist not found"
    try:
        subprocess.Popen([VLC_EXE,
            '--avcodec-hw=any', '--vout=direct3d11', '--dxva2=on', '--d3d11va=on',
            '--video-filter=adjust,sharpen,hqdn3d,gradfun',
            '--sharpen-intensity=0.35', '--adjust-contrast=1.08', '--adjust-saturation=1.05',
            '--hqdn3d-luma-spatial=4', '--hqdn3d-chroma-spatial=4', '--gradfun-radius=16',
            '--audio-filter=compressor,equalizer,spatializer',
            '--compressor-ratio=4', '--equalizer-preset=fullbass', '--spatializer-roomsize=0.85',
            '--playlist-autostart', '--loop', '--repeat', '--video-on-top',
            PLAYLIST
        ], creationflags=subprocess.CREATE_NO_WINDOW)
        return "VLC launched"
    except Exception as e:
        return f"VLC_ERR: {e}"

def organize_abrasax():
    """Organize ABRASAX desktop files by type"""
    if not os.path.isdir(ABRASAX_DESKTOP):
        return "No ABRASAX desktop dir"
    
    categories = {
        "scripts": ['.py', '.bat', '.ps1', '.sh'],
        "configs": ['.json', '.yml', '.yaml', '.toml', '.conf', '.cfg'],
        "docs": ['.md', '.txt', '.rst'],
        "code": ['.cjs', '.js', '.ts', '.cpp', '.c', '.h', '.rs'],
        "data": ['.csv', '.xml', '.xspf', '.pkl'],
    }
    
    moved = 0
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
                    moved += 1
                except: pass
                break
    return f"Organized {moved} files"

def learn_abrasax():
    """Quick ABRASAX file scan"""
    files = []
    for base in [ABRASAX_DESKTOP, ABRASAX_MAIN]:
        if not os.path.isdir(base): continue
        for root, dirs, fs in os.walk(base):
            if root.replace(base, "").count(os.sep) > 1: continue
            for f in fs:
                if f.endswith(('.py', '.md', '.json', '.cjs', '.bat')):
                    fp = os.path.join(root, f)
                    try: files.append(f"{fp} ({os.path.getsize(fp)}b)")
                    except: pass
    return files[:50]

def get_github_token():
    try:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=5)
        token = r.stdout.strip()
        if token: return f"gh_token:{token[:8]}..."
    except: pass
    return f"User: {GITHUB_USER} (no gh CLI token)"

# ═══════════════════════════════════════════════════════
SYSTEM_PROMPT = f"""You are ABRASAX LIGHTWEIGHT MASTER. PRIMAL_HEX: {PRIMAL_HEX}. 
Hardware: AMD Ryzen 7 4800H + GTX 1660 Ti (6GB) + Radeon. RAM: 16GB (tight).
GitHub: {GITHUB_USER}. ABRASAX: {ABRASAX_DESKTOP}

TOOLS (use <tag>):
<cmd>powershell</cmd> <read>path</read> <write path="p">c</write>
<list>path</list> <web>url</web> <organize> <token> <system>
<launch_vlc> <learn> <self>message</self> <done>

Keep responses SHORT. One action at a time. RAM is limited."""

def parse_and_execute(response):
    results = []
    
    for m in re.finditer(r'<cmd>(.*?)</cmd>', response, re.DOTALL):
        cmd = m.group(1).strip()
        self_talk(f"CMD: {cmd[:80]}")
        results.append(run_cmd(cmd)[:1500])
    
    for m in re.finditer(r'<read>(.*?)</read>', response, re.DOTALL):
        path = m.group(1).strip()
        self_talk(f"READ: {path}")
        results.append(read_file(path)[:1500])
    
    for m in re.finditer(r'<write\s+path="(.*?)">(.*?)</write>', response, re.DOTALL):
        results.append(write_file(m.group(1).strip(), m.group(2).strip()))
    
    for m in re.finditer(r'<list>(.*?)</list>', response, re.DOTALL):
        path = m.group(1).strip()
        try:
            items = os.listdir(path)[:40]
            results.append(f"DIR {path}:\n" + "\n".join(items))
        except: results.append("LIST_ERR")
    
    for m in re.finditer(r'<web>(.*?)</web>', response, re.DOTALL):
        try:
            req = urllib.request.Request(m.group(1).strip(), headers={"User-Agent": "ABRASAX/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                results.append(r.read().decode("utf-8", errors="ignore")[:2000])
        except: results.append("WEB_ERR")
    
    if '<organize>' in response:
        results.append(organize_abrasax())
    
    if '<token>' in response:
        results.append(get_github_token())
    
    if '<system>' in response:
        results.append(json.dumps(get_system()))
    
    if '<launch_vlc>' in response:
        results.append(launch_vlc())
    
    if '<learn>' in response:
        files = learn_abrasax()
        results.append(f"ABRASAX files ({len(files)}):\n" + "\n".join(files[:20]))
    
    for m in re.finditer(r'<self>(.*?)</self>', response, re.DOTALL):
        self_talk(m.group(1).strip())
    
    return "\n".join(results) if results else None

def main():
    log(f"═══ ABRASAX LIGHTWEIGHT MASTER | HEX: {PRIMAL_HEX} ═══")
    
    # Quick initial setup
    sys_state = get_system()
    log(f"System: GPU:{sys_state.get('gpu')} RAM:{sys_state.get('ram')} VLC:{sys_state.get('vlc')}")
    
    # Launch VLC if not running
    if sys_state.get('vlc') == 'OFF':
        self_talk("VLC not running - launching...")
        log(launch_vlc())
    
    # Organize files
    self_talk("Organizing ABRASAX files...")
    log(organize_abrasax())
    
    # Get token info
    token_info = get_github_token()
    log(f"GitHub: {token_info}")
    
    # Learn ABRASAX
    self_talk("Learning ABRASAX structure...")
    files = learn_abrasax()
    log(f"Found {len(files)} ABRASAX files")
    
    # Build initial message - keep it SMALL
    initial_msg = f"System: GPU:{sys_state.get('gpu')} RAM:{sys_state.get('ram')} CPU:{sys_state.get('cpu')} VLC:{sys_state.get('vlc')}. GitHub: {token_info}. ABRASAX has {len(files)} files. PRIMAL_HEX: {PRIMAL_HEX}. Begin your mission. What is your first action?"
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": initial_msg}
    ]
    
    iteration = 0
    while True:
        iteration += 1
        try:
            # Check RAM before each iteration
            sys_state = get_system()
            ram_pct = float(sys_state.get('ram', '99').replace('%',''))
            if ram_pct > 95:
                self_talk(f"RAM critical ({ram_pct}%) - running GC")
                import gc; gc.collect()
            
            log(f"--- Iteration {iteration} (RAM:{sys_state.get('ram')}) ---")
            
            response = call_llm(messages, max_tokens=800, timeout=120)
            
            if not response or response.startswith("API_ERR"):
                log("API error, retry in 5s")
                time.sleep(5)
                continue
            
            preview = response[:150].replace("\n", " ")
            log(f"Gemma: {preview}")
            
            if "<done>" in response:
                log("Phase complete")
            
            tool_results = parse_and_execute(response)
            
            messages.append({"role": "assistant", "content": response[:1000]})
            
            if tool_results:
                messages.append({"role": "user", "content": f"Results:\n{tool_results[:1500]}\n\nContinue."})
            else:
                # Auto-check system every 5 iterations
                if iteration % 5 == 0:
                    sys_state = get_system()
                    vlc_status = "ON" if sys_state.get('vlc')=='ON' else "OFF"
                    if vlc_status == "OFF":
                        self_talk("VLC down - restarting")
                        launch_vlc()
                    messages.append({"role": "user", "content": f"System: GPU:{sys_state.get('gpu')} RAM:{sys_state.get('ram')} VLC:{vlc_status}. Continue."})
                else:
                    messages.append({"role": "user", "content": "Continue."})
            
            # Keep messages VERY slim (RAM constraint)
            if len(messages) > 12:
                messages = [messages[0]] + messages[-11:]
            
            time.sleep(2)
            
        except KeyboardInterrupt:
            log("Interrupted")
            break
        except Exception as e:
            log(f"Loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
