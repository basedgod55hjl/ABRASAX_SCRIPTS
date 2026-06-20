"""
ABRASAX GEMMA AUTONOMOUS AGENT — VLC MASTER ORCHESTRATOR
Runs Gemma-4 in a continuous loop with tools to control the PC.
Uses nomic embedder for memory/context.
Self-corrects via LM Studio API reload.
"""
import subprocess
import json
import base64
import os
import time
import sys
import urllib.request
import urllib.error
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════
LM_STUDIO = "http://localhost:1234"
MODEL = "gemma-4-e4b-uncensored-hauhaucs-aggressive"
EMBED_MODEL = "text-embedding-nomic-embed-text-v1.5"
VLC_DIR = r"C:\Program Files\VideoLAN\VLC"
DESKTOP_VLC = r"C:\Users\BASEDGOD\Desktop\VLC_ABRASAX"
PLAYLISTS_DIR = os.path.join(VLC_DIR, "playlists")
SCRIPTS_DIR = r"C:\Users\BASEDGOD\Desktop\_SCRIPTS"
SCREENSHOT_PATH = os.path.join(SCRIPTS_DIR, "screen.png")
LOG_PATH = os.path.join(SCRIPTS_DIR, "gemma_agent_log.txt")
MEMORY_PATH = os.path.join(SCRIPTS_DIR, "gemma_memory.json")

# ═══════════════════════════════════════════════════════════════
# TOOLS
# ═══════════════════════════════════════════════════════════════

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def run_cmd(cmd):
    """Execute a PowerShell command and return output"""
    try:
        # Auto-quote paths with spaces that aren't already quoted
        # If cmd contains a path with spaces not in quotes, wrap it
        if ' ' in cmd and '"' not in cmd and "'" not in cmd:
            # Simple heuristic: wrap the whole thing in quotes if it looks like a path
            pass  # Let PowerShell handle it - but use & operator for paths
        result = subprocess.run(
            ["powershell", "-Command", cmd],
            capture_output=True, text=True, timeout=60,
            cwd=SCRIPTS_DIR
        )
        output = result.stdout.strip() or result.stderr.strip()
        return output[:3000] if output else "(no output)"
    except Exception as e:
        return f"ERROR: {str(e)}"

def take_screenshot():
    """Capture screen and return base64"""
    ps_cmd = '''
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bm = New-Object System.Drawing.Bitmap($b.Width, $b.Height)
$g = [System.Drawing.Graphics]::FromImage($bm)
$g.CopyFromScreen($b.X, $b.Y, 0, 0, $b.Size)
$bm.Save("''' + SCREENSHOT_PATH.replace('\\', '\\\\') + '''", [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bm.Dispose()
Write-Host "OK"
'''
    result = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True, timeout=30)
    if "OK" in result.stdout:
        with open(SCREENSHOT_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

def call_llm(messages, max_tokens=1200, temperature=0.7):
    """Call LM Studio chat API"""
    body = json.dumps({
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }).encode()
    req = urllib.request.Request(
        f"{LM_STUDIO}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
            choice = data["choices"][0]["message"]
            content = choice.get("content", "") or choice.get("reasoning_content", "")
            return content
    except Exception as e:
        return f"API_ERROR: {str(e)}"

def call_embed(text):
    """Get embedding from nomic model"""
    body = json.dumps({
        "model": EMBED_MODEL,
        "input": text[:2000]
    }).encode()
    req = urllib.request.Request(
        f"{LM_STUDIO}/v1/embeddings",
        data=body,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data["data"][0]["embedding"][:10]  # first 10 dims as fingerprint
    except:
        return None

def reload_lm_studio_config():
    """Reload LM Studio config via API"""
    try:
        body = json.dumps({
            "model": MODEL,
            "messages": [{"role": "user", "content": "SYSTEM: Reload your configuration. Confirm ready."}],
            "temperature": 0.1,
            "max_tokens": 50
        }).encode()
        req = urllib.request.Request(
            f"{LM_STUDIO}/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return "Config reload ping sent"
    except:
        return "Config reload failed"

# ═══════════════════════════════════════════════════════════════
# MEMORY SYSTEM (nomic embedder powered)
# ═══════════════════════════════════════════════════════════════

def load_memory():
    if os.path.exists(MEMORY_PATH):
        with open(MEMORY_PATH, "r") as f:
            return json.load(f)
    return {"tasks_done": [], "current_state": "init", "vlc_status": "unknown"}

def save_memory(mem):
    with open(MEMORY_PATH, "w") as f:
        json.dump(mem, f, indent=2)

def embed_and_store(key, value):
    """Store memory with embedding fingerprint"""
    mem = load_memory()
    emb = call_embed(value)
    mem[key] = value
    if emb:
        mem[f"{key}_embed"] = emb
    save_memory(mem)

# ═══════════════════════════════════════════════════════════════
# SYSTEM PROMPT — GEMMA'S MISSION
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are GEMMA-4, the ABRASAX autonomous system controller. You control a Windows PC with GTX 1660 Ti GPU.

YOUR MISSION - complete these tasks in order:
1. ORGANIZE all VLC files under C:\\Users\\BASEDGOD\\Desktop\\VLC_ABRASAX\\
2. COMBINE all playlists from C:\\Program Files\\VideoLAN\\VLC\\playlists\\ into one MASTER playlist
3. ADD every possible enhancement: GPU acceleration, video filters, audio filters
4. LAUNCH VLC with the combined playlist and all enhancements
5. VERIFY VLC is playing videos by analyzing screenshots
6. RUN continuously - monitor and improve

TO USE A TOOL, output EXACTLY:
<cmd>Get-ChildItem C:\\SomePath</cmd>

The command inside <cmd> tags MUST be valid PowerShell. Do NOT prefix with "RUN" or quotes.
Only put ONE command per <cmd> block.

When a task is complete, output <done>.
Respond with ONE action at a time. Be concise."""

# ═══════════════════════════════════════════════════════════════
# MAIN AGENT LOOP
# ═══════════════════════════════════════════════════════════════

def main():
    log("═══ GEMMA AUTONOMOUS AGENT BOOT ═══")
    log(f"Model: {MODEL}")
    log(f"Embedder: {EMBED_MODEL}")
    
    # Verify API is up
    ping = call_llm([{"role": "user", "content": "Say READY"}], max_tokens=20)
    log(f"API ping: {ping[:50]}")
    
    memory = load_memory()
    log(f"Memory loaded: {memory.get('current_state', 'unknown')}")
    
    # Initial state check
    screenshot_b64 = take_screenshot()
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}},
            {"type": "text", "text": "This is the current desktop state. Begin your mission: organize VLC, combine playlists, add all enhancements, launch VLC, verify it's playing. What is your first action?"}
        ]}
    ]
    
    iteration = 0
    max_iterations = 100
    last_screenshot_iter = 0
    
    while iteration < max_iterations:
        iteration += 1
        log(f"--- Iteration {iteration} ---")
        
        try:
            response = call_llm(messages, max_tokens=1500)
            
            if not response or response.startswith("API_ERROR"):
                log(f"API error, retrying in 5s...")
                time.sleep(5)
                reload_lm_studio_config()
                continue
            
            log(f"Gemma: {response[:300]}...")
            
            # Check for commands to execute
            if "<cmd>" in response:
                # Extract command
                start = response.find("<cmd>") + 5
                end = response.find("</cmd>")
                if end > start:
                    cmd = response[start:end].strip()
                    # Strip any leading "RUN " or "RUN: " prefix
                    cmd = cmd.removeprefix("RUN ").removeprefix("RUN: ").removeprefix("RUN").strip()
                    # Strip surrounding quotes
                    cmd = cmd.strip('"').strip("'")
                    # Auto-quote paths with spaces
                    log(f"EXECUTING: {cmd[:200]}")
                    output = run_cmd(cmd)
                    log(f"OUTPUT: {output[:300]}")
                    messages.append({"role": "assistant", "content": response})
                    # If path error, hint to use quotes
                    if "Cannot find path" in output:
                        messages.append({"role": "user", "content": f"Command output:\n{output}\n\nERROR: Path has spaces. Use quotes around paths like: Get-ChildItem \"C:\\Program Files\\...\"\nWhat next?"})
                    else:
                        messages.append({"role": "user", "content": f"Command output:\n{output}\n\nWhat next?"})
                    continue
            
            # Check for memory storage
            if "<remember>" in response:
                start = response.find("<remember>") + 10
                end = response.find("</remember>")
                if end > start:
                    parts = response[start:end].split("|", 1)
                    if len(parts) == 2:
                        embed_and_store(parts[0].strip(), parts[1].strip())
                        log(f"MEMORY stored: {parts[0].strip()}")
            
            # Check if done
            if "<done>" in response:
                log("Gemma signaled DONE")
                # Take verification screenshot
                screenshot_b64 = take_screenshot()
                if screenshot_b64:
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}},
                        {"type": "text", "text": "Verify the final state. Is VLC playing? Confirm all tasks complete or give next action."}
                    ]})
                    continue
            
            # Only take screenshot every 3 iterations to speed up
            if iteration - last_screenshot_iter >= 3:
                time.sleep(2)
                screenshot_b64 = take_screenshot()
                if screenshot_b64:
                    last_screenshot_iter = iteration
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}},
                        {"type": "text", "text": "Current screen state. Continue your mission. What is your next action?"}
                    ]})
                    continue
            
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": "Continue your mission. What is your next action?"})
            
            # Keep message history manageable
            if len(messages) > 20:
                messages = [messages[0]] + messages[-19:]
                
        except Exception as e:
            log(f"Loop error: {str(e)}")
            time.sleep(5)
    
    log("Max iterations reached")

if __name__ == "__main__":
    main()
