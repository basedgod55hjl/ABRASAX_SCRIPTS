"""
ABRASAX SYSTEM OPTIMIZER AGENT — Keeps PC running fast & smooth
Queries Gemma for optimization strategies. Manages processes, services, GPU.
Non-stop loop. Works with resource monitor for data.
"""
import subprocess
import json
import time
import os
import urllib.request
import urllib.error
from datetime import datetime

LM_STUDIO = "http://localhost:1234"
MODEL = "gemma-4-e4b-uncensored-hauhaucs-aggressive"
LOG_PATH = r"C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX_SCRIPTS\system_optimizer_log.txt"

def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    line = f"[{t}] SYSOPT: {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def call_llm(messages, max_tokens=400, temp=0.5):
    body = json.dumps({"model": MODEL, "messages": messages, "temperature": temp, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(f"{LM_STUDIO}/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
            c = d["choices"][0]["message"]
            return c.get("content", "") or c.get("reasoning_content", "")
    except Exception as e:
        return f"API_ERR:{e}"

def get_system_stats():
    """Get comprehensive system stats"""
    try:
        stats = {}
        
        # CPU
        cpu = subprocess.run(["powershell", "-Command", "(Get-CimInstance Win32_Processor).LoadPercentage"], capture_output=True, text=True, timeout=5)
        stats['cpu'] = float(cpu.stdout.strip() or 0)
        
        # RAM
        ram = subprocess.run(["powershell", "-Command", "$os=Get-CimInstance Win32_OperatingSystem; $free=$os.FreePhysicalMemory/1MB; $total=$os.TotalVisibleMemorySize/1MB; Write-Host \"$([math]::Round($free,1))|$([math]::Round($total,1))|$([math]::Round(($total-$free)/$total*100,1))\""], capture_output=True, text=True, timeout=5)
        parts = ram.stdout.strip().split("|")
        stats['ram_free'] = float(parts[0]) if len(parts) > 0 else 0
        stats['ram_total'] = float(parts[1]) if len(parts) > 1 else 32
        stats['ram_pct'] = float(parts[2]) if len(parts) > 2 else 0
        
        # GPU
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5)
        gpu_parts = gpu.stdout.strip().split(", ")
        stats['gpu_util'] = float(gpu_parts[0]) if len(gpu_parts) > 0 else 0
        stats['vram_used'] = float(gpu_parts[1]) if len(gpu_parts) > 1 else 0
        stats['vram_total'] = float(gpu_parts[2]) if len(gpu_parts) > 2 else 6144
        stats['gpu_temp'] = float(gpu_parts[3]) if len(gpu_parts) > 3 else 0
        
        # Disk
        disk = subprocess.run(["powershell", "-Command", "(Get-PSDrive C).Free/1GB"], capture_output=True, text=True, timeout=5)
        stats['disk_free'] = float(disk.stdout.strip() or 100)
        
        # Process count
        procs = subprocess.run(["powershell", "-Command", "(Get-Process).Count"], capture_output=True, text=True, timeout=5)
        stats['proc_count'] = int(procs.stdout.strip() or 0)
        
        return stats
    except Exception as e:
        return {"error": str(e)}

def optimize_system():
    """Run system optimizations"""
    actions = []
    try:
        # Clear memory standby list
        r = subprocess.run(["powershell", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue; [System.GC]::Collect(2, [System.GCCollectionMode]::Aggressive); [System.GC]::WaitForPendingFinalizers()"], capture_output=True, timeout=15)
        actions.append("GC_collected")
        
        # Set power plan to high performance
        r = subprocess.run(["powercfg", "/setactive", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"], capture_output=True, timeout=5)
        actions.append("high_perf_power")
        
        # Kill unnecessary background processes
        bloat = ["OneDrive", "Skype", "Teams", "Cortana", "Widgets", "GameBar"]
        for b in bloat:
            subprocess.run(["taskkill", "/f", "/im", f"{b}.exe"], capture_output=True, timeout=3)
        
        # Set NVIDIA to prefer maximum performance
        subprocess.run(["nvidia-smi", "-ac", "5001,1800"], capture_output=True, timeout=5)
        actions.append("nvidia_max_perf")
        
        return "; ".join(actions)
    except Exception as e:
        return f"Opt error: {e}"

def main():
    log("═══ SYSTEM OPTIMIZER AGENT BOOT ═══")
    
    sys_msg = {
        "role": "system",
        "content": "You are the ABRASAX System Optimizer. Keep the PC running fast and smooth. You receive system stats and decide optimizations. Respond with ACTION: <optimize>, <clear_ram>, <boost_gpu>, <kill_bloat>, <defrag_memory>, or <ok>. Be concise."
    }
    
    messages = [sys_msg]
    
    # Initial optimization
    log("Running initial optimization...")
    result = optimize_system()
    log(f"Initial: {result}")
    
    iteration = 0
    last_optimize = time.time()
    
    while True:
        iteration += 1
        try:
            stats = get_system_stats()
            
            if "error" in stats:
                time.sleep(5)
                continue
            
            # Log status periodically
            if iteration % 20 == 0:
                log(f"CPU:{stats['cpu']:.0f}% RAM:{stats['ram_pct']:.1f}% GPU:{stats['gpu_util']:.0f}% VRAM:{stats['vram_used']:.0f}MB Disk:{stats['disk_free']:.0f}GB Procs:{stats['proc_count']}")
            
            # Auto-optimize if resources are strained
            needs_opt = False
            if stats['ram_pct'] > 75:
                log(f"RAM high ({stats['ram_pct']:.1f}%) - optimizing...")
                needs_opt = True
            if stats['cpu'] > 85:
                log(f"CPU high ({stats['cpu']:.0f}%) - optimizing...")
                needs_opt = True
            if stats['gpu_temp'] > 80:
                log(f"GPU hot ({stats['gpu_temp']:.0f}C) - throttling...")
                needs_opt = True
            
            # Optimize at most every 30 seconds
            if needs_opt and time.time() - last_optimize > 30:
                result = optimize_system()
                log(f"Optimization: {result}")
                last_optimize = time.time()
            
            # Every 15 iterations, ask Gemma
            if iteration % 15 == 0:
                status = f"CPU:{stats['cpu']:.0f}% RAM:{stats['ram_pct']:.1f}% ({stats['ram_free']:.0f}GB free) GPU:{stats['gpu_util']:.0f}% {stats['gpu_temp']:.0f}C VRAM:{stats['vram_used']:.0f}/{stats['vram_total']:.0f}MB Disk:{stats['disk_free']:.0f}GB Procs:{stats['proc_count']}. Action?"
                messages.append({"role": "user", "content": status})
                resp = call_llm(messages, max_tokens=300)
                log(f"Gemma: {resp[:150]}")
                
                if "optimize" in resp.lower() or "clear_ram" in resp.lower() or "boost" in resp.lower():
                    result = optimize_system()
                    log(f"Gemma optimization: {result}")
                    last_optimize = time.time()
                
                if len(messages) > 10:
                    messages = [sys_msg] + messages[-9:]
            
            time.sleep(2)
            
        except Exception as e:
            log(f"Loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
