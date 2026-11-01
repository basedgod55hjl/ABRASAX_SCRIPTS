"""
ABRASAX REAL-TIME OPTIMIZER — Minimal, RAM-safe, instant
Connects to LM Studio API, monitors system, applies optimizations.
No file scanning. Non-stop loop.
"""
import urllib.request, json, time, subprocess, os, re
from datetime import datetime

LM = 'http://localhost:1234'
MODEL = 'gemma-4-e4b-uncensored-hauhaucs-aggressive'

def log(msg):
    print(f'[{datetime.now():%H:%M:%S}] {msg}')

def llm(msg):
    body = json.dumps({'model':MODEL,'messages':[{'role':'user','content':msg}],'temperature':0.7,'max_tokens':500}).encode()
    try:
        req = urllib.request.Request(f'{LM}/v1/chat/completions', data=body, headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read())
            return d['choices'][0]['message'].get('content','') or d['choices'][0]['message'].get('reasoning_content','')
    except Exception as e:
        return f'ERR:{e}'

def sys_info():
    gpu = subprocess.run(['nvidia-smi','--query-gpu=utilization.gpu,memory.used,temperature.gpu','--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=5)
    ram = subprocess.run(['powershell','-Command','(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB'], capture_output=True, text=True, timeout=5)
    vlc = subprocess.run(['tasklist','/fi','imagename eq vlc.exe'], capture_output=True, text=True, timeout=3)
    vlc_on = "ON" if "vlc.exe" in vlc.stdout else "OFF"
    try: ram_mb = float(ram.stdout.strip())
    except: ram_mb = 0
    return f'GPU:{gpu.stdout.strip()} RAMfree:{ram_mb:.0f}MB VLC:{vlc_on}'

log('═══ ABRASAX REAL-TIME AGENT ═══')
log(f'System: {sys_info()}')

log('Testing API...')
r = llm('Say READY')
log(f'Gemma: {r[:120]}')

sys_msg = 'You are ABRASAX real-time optimizer. System: AMD Ryzen 7 4800H + GTX 1660 Ti + Radeon. RAM limited (16GB). Keep responses under 100 words. Monitor system, suggest optimizations. Use <cmd> for PowerShell commands.'
msgs = [{'role':'system','content':sys_msg}]

for i in range(100):
    try:
        info = sys_info()
        msg = f'System: {info}. Iter {i+1}. What optimization?'
        resp = llm(msg)
        log(f'[{i+1}] Gemma: {resp[:200]}')
        
        if '<cmd>' in resp:
            for m in re.finditer(r'<cmd>(.*?)</cmd>', resp, re.DOTALL):
                cmd = m.group(1).strip()
                log(f'EXEC: {cmd[:100]}')
                try:
                    out = subprocess.run(['powershell','-Command',cmd], capture_output=True, text=True, timeout=30)
                    log(f'OUT: {(out.stdout or out.stderr)[:150]}')
                except Exception as e:
                    log(f'ERR: {e}')
        
        msgs.append({'role':'assistant','content':resp[:500]})
        if len(msgs) > 10:
            msgs = [msgs[0]] + msgs[-9:]
        time.sleep(3)
    except KeyboardInterrupt:
        break
    except Exception as e:
        log(f'Loop: {e}')
        time.sleep(5)

log('Done')
