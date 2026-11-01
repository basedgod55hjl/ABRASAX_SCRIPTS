"""
ABRASAX RESOURCE MONITOR AGENT — Live PC resource tracking
Queries Gemma for optimization decisions. Offloads RAM when high.
Runs non-stop. GPU-aware. GTX 1660 Ti optimized.
"""
import subprocess
import json
import time
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
import threading

# ═══════════════════════════════════════════════════════
LM_STUDIO = "http://localhost:1234"
MODEL = "gemma-4-e4b-uncensored-hauhaucs-aggressive"
LOG_PATH = r"C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX_SCRIPTS\resource_monitor_log.txt"

def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    line = f"[{t}] RESMON: {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def call_llm(messages, max_tokens=300, temp=0.3):
    body = json.dumps({"model": MODEL, "messages": messages, "temperature": temp, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(f"{LM_STUDIO}/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
            c = d["choices"][0]["message"]
            return c.get("content", "") or c.get("reasoning_content", "")
    except Exception as e:
        return f"API_ERR:{e}"

def get_resources():
    """Get live system resources"""
    try:
        # GPU
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
        gpu_data = gpu.stdout.strip().split(", ")
        
        # RAM
        ram = subprocess.run(["powershell", "-Command", "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1024 / 1024; (Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize / 1024 / 1024"], capture_output=True, text=True, timeout=10)
        ram_lines = ram.stdout.strip().split("\n")
        ram_free = float(ram_lines[0].strip()) if len(ram_lines) > 0 else 0
        ram_total = float(ram_lines[1].strip()) if len(ram_lines) > 1 else 32
        
        # CPU
        cpu = subprocess.run(["powershell", "-Command", "(Get-CimInstance Win32_Processor).LoadPercentage"], capture_output=True, text=True, timeout=10)
        cpu_usage = float(cpu.stdout.strip() or 0)
        
        # Top processes by RAM
        top_procs = subprocess.run(["powershell", "-Command", "Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 5 Name, @{N='MemMB';E={[math]::Round($_.WorkingSet64/1MB,1)}} | ConvertTo-Json"], capture_output=True, text=True, timeout=10)
        
        return {
            "gpu_util": float(gpu_data[0]) if len(gpu_data) > 0 else 0,
            "vram_used_mb": float(gpu_data[1]) if len(gpu_data) > 1 else 0,
            "vram_total_mb": float(gpu_data[2]) if len(gpu_data) > 2 else 6144,
            "gpu_temp": float(gpu_data[3]) if len(gpu_data) > 3 else 0,
            "gpu_power": float(gpu_data[4]) if len(gpu_data) > 4 else 0,
            "ram_free_gb": round(ram_free, 1),
            "ram_total_gb": round(ram_total, 1),
            "ram_used_pct": round((1 - ram_free/ram_total) * 100, 1) if ram_total > 0 else 0,
            "cpu_pct": cpu_usage,
            "top_processes": top_procs.stdout.strip()[:500]
        }
    except Exception as e:
        return {"error": str(e)}

def offload_ram():
    """Aggressively free RAM"""
    try:
        # Clear standby list
        subprocess.run(["powershell", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue; [System.GC]::Collect(); [System.GC]::WaitForPendingFinalizers()"], capture_output=True, timeout=15)
        # Kill non-essential heavy processes
        subprocess.run(["powershell", "-Command", "Get-Process chrome, msedge, firefox -ErrorAction SilentlyContinue | Where-Object {$_.WorkingSet64 -gt 500MB} | Stop-Process -Force -ErrorAction SilentlyContinue"], capture_output=True, timeout=10)
        return "RAM offload executed"
    except Exception as e:
        return f"Offload error: {e}"

def optimize_gpu():
    """Optimize GPU memory"""
    try:
        subprocess.run(["powershell", "-Command", "nvidia-smi --gpu-reset-applications-clocks"], capture_output=True, timeout=10)
        return "GPU clocks reset"
    except:
        return "GPU optimize skipped"

def main():
    log("═══ RESOURCE MONITOR AGENT BOOT ═══")
    log(f"Model: {MODEL}")
    
    # Initial system prompt
    sys_msg = {
        "role": "system",
        "content": "You are the ABRASAX Resource Monitor. You receive live PC resource data (RAM, GPU, CPU, VRAM). If RAM usage > 80% or VRAM > 90%, command OFFLOAD. If CPU > 90%, suggest process kills. Respond with ACTION: <offload_ram>, <offload_vram>, <kill_chrome>, <optimize_gpu>, or <ok>. Be concise. One word actions."
    }
    
    messages = [sys_msg]
    iteration = 0
    
    while True:
        iteration += 1
        try:
            resources = get_resources()
            
            if "error" in resources:
                log(f"Resource read error: {resources['error']}")
                time.sleep(5)
                continue
            
            # Log status
            status = f"GPU:{resources['gpu_util']}% VRAM:{resources['vram_used_mb']:.0f}/{resources['vram_total_mb']:.0f}MB RAM:{resources['ram_used_pct']:.1f}% CPU:{resources['cpu_pct']:.0f}%"
            
            # Check thresholds
            action_taken = ""
            
            if resources['ram_used_pct'] > 80:
                log(f"HIGH RAM ({resources['ram_used_pct']:.1f}%) - OFFLOADING")
                offload_ram()
                action_taken = "RAM_OFFLOAD"
            
            if resources['vram_used_mb'] / resources['vram_total_mb'] > 0.90:
                log(f"HIGH VRAM ({resources['vram_used_mb']:.0f}MB) - OPTIMIZING GPU")
                optimize_gpu()
                action_taken += " VRAM_OPTIMIZE"
            
            if resources['cpu_pct'] > 90:
                log(f"HIGH CPU ({resources['cpu_pct']:.0f}%) - checking processes")
            
            # Every 5 iterations, ask Gemma for advice
            if iteration % 5 == 0:
                msg = f"Resources: GPU {resources['gpu_util']}%, VRAM {resources['vram_used_mb']:.0f}/{resources['vram_total_mb']:.0f}MB ({resources['gpu_temp']}C), RAM {resources['ram_used_pct']:.1f}% ({resources['ram_free_gb']}GB free), CPU {resources['cpu_pct']}%. Top procs: {resources['top_processes'][:200]}. Action?"
                messages.append({"role": "user", "content": msg})
                resp = call_llm(messages, max_tokens=200)
                log(f"Gemma: {resp[:150]}")
                
                if "offload_ram" in resp.lower():
                    offload_ram()
                    action_taken += " GEMMA_RAM_OFFLOAD"
                if "offload_vram" in resp.lower() or "optimize_gpu" in resp.lower():
                    optimize_gpu()
                    action_taken += " GEMMA_GPU_OPTIMIZE"
                
                # Keep messages slim
                if len(messages) > 10:
                    messages = [sys_msg] + messages[-9:]
            
            if action_taken:
                log(f"ACTIONS: {action_taken}")
            elif iteration % 10 == 0:
                log(f"OK - {status}")
            
            time.sleep(3)  # Check every 3 seconds
            
        except Exception as e:
            log(f"Loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
