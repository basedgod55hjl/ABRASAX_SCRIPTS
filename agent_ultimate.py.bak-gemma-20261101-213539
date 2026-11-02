"""
ABRASAX ULTIMATE SELF-EVOLVING AGENT
PRIMAL_HEX: 4f5349524953424c58434b | PHI: 1.618033988749895
- Queries Gemma-4 in non-stop loop
- Monitors PC resources in real-time
- Can edit its own source code
- Reads/orgainzes ABRASAX desktop folder
- Dev logs feed back to LLM
- Self-optimizing
"""
import urllib.request, json, time, subprocess, os, sys, re, gc
from datetime import datetime
from pathlib import Path

LM = 'http://localhost:1234'
MODEL = 'gemma-4-e4b-uncensored-hauhaucs-aggressive'
SCRIPTS = Path(r'C:\Users\sirch\Desktop\ABRASAX\repos\ABRASAX_SCRIPTS')
ABRASAX = Path(r'C:\Users\sirch\Desktop\ABRASAX')
SELF = Path(__file__)
LOG = SCRIPTS / 'ultimate_agent_log.txt'
DEVLOG = SCRIPTS / 'dev_feedback_log.txt'
MEMORY = SCRIPTS / 'ultimate_memory.json'

def log(msg):
    t = datetime.now().strftime('%H:%M:%S')
    line = f'[{t}] {msg}'
    print(line)
    try:
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except: pass

def devlog(msg):
    """Dev log that feeds back to LLM"""
    t = datetime.now().strftime('%H:%M:%S')
    line = f'[{t}] DEV: {msg}'
    try:
        with open(DEVLOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except: pass

def read_devlog():
    try:
        if DEVLOG.exists():
            with open(DEVLOG, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                return ''.join(lines[-30:])
    except: pass
    return '(no dev log yet)'

def call_llm(messages, max_tokens=1000, temp=0.7):
    """Call Gemma-4 via LM Studio"""
    body = json.dumps({'model': MODEL, 'messages': messages, 'temperature': temp, 'max_tokens': max_tokens}).encode()
    req = urllib.request.Request(f'{LM}/v1/chat/completions', data=body, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.loads(r.read())
            c = d['choices'][0]['message']
            return c.get('content', '') or c.get('reasoning_content', '')
    except Exception as e:
        return f'API_ERR:{e}'

def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(['powershell', '-Command', cmd], capture_output=True, text=True, timeout=timeout)
        return (r.stdout.strip() or r.stderr.strip())[:3000]
    except Exception as e:
        return f'CMD_ERR:{e}'

def read_file(path, max_lines=100):
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return ''.join(f.readlines()[:max_lines])
    except Exception as e:
        return f'READ_ERR:{e}'

def write_file(path, content):
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f'OK: {len(content)} bytes'
    except Exception as e:
        return f'WRITE_ERR:{e}'

def sys_info():
    """Real-time system snapshot"""
    try:
        gpu = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=5)
        ram = subprocess.run(['powershell', '-Command', '$os=Get-CimInstance Win32_OperatingSystem;$free=[math]::Round($os.FreePhysicalMemory/1MB,0);$total=[math]::Round($os.TotalVisibleMemorySize/1MB,0);Write-Host "$free|$total"'], capture_output=True, text=True, timeout=5)
        cpu = subprocess.run(['powershell', '-Command', '(Get-CimInstance Win32_Processor).LoadPercentage'], capture_output=True, text=True, timeout=5)
        vlc = subprocess.run(['tasklist', '/fi', 'imagename eq vlc.exe'], capture_output=True, text=True, timeout=3)
        
        gpu_parts = gpu.stdout.strip().split(', ')
        ram_parts = ram.stdout.strip().split('|')
        vlc_on = 'ON' if 'vlc.exe' in vlc.stdout else 'OFF'
        
        return {
            'gpu_util': float(gpu_parts[0]) if len(gpu_parts)>0 else 0,
            'vram_used': float(gpu_parts[1]) if len(gpu_parts)>1 else 0,
            'vram_total': float(gpu_parts[2]) if len(gpu_parts)>2 else 6144,
            'gpu_temp': float(gpu_parts[3]) if len(gpu_parts)>3 else 0,
            'ram_free': float(ram_parts[0]) if len(ram_parts)>0 else 0,
            'ram_total': float(ram_parts[1]) if len(ram_parts)>1 else 16000,
            'cpu_pct': float(cpu.stdout.strip() or 0),
            'vlc': vlc_on
        }
    except Exception as e:
        return {'error': str(e)}

def organize_abrasax():
    """Organize ABRASAX desktop folder by file type"""
    if not ABRASAX.exists():
        return 'ABRASAX folder not found'
    
    categories = {
        '_scripts': ['.py', '.bat', '.ps1', '.sh', '.vbs'],
        '_configs': ['.json', '.yml', '.yaml', '.toml', '.conf', '.cfg', '.ini'],
        '_docs': ['.md', '.txt', '.rst', '.pdf'],
        '_code': ['.cjs', '.js', '.ts', '.cpp', '.c', '.h', '.rs', '.go'],
        '_data': ['.csv', '.xml', '.xspf', '.pkl', '.bin', '.db'],
    }
    
    moved = 0
    for f in list(ABRASAX.iterdir()):
        if not f.is_file(): continue
        ext = f.suffix.lower()
        for cat, exts in categories.items():
            if ext in exts:
                cat_dir = ABRASAX / cat
                cat_dir.mkdir(exist_ok=True)
                try:
                    f.rename(cat_dir / f.name)
                    moved += 1
                except: pass
                break
    return f'Organized {moved} files'

def learn_abrasax():
    """Quick ABRASAX file inventory"""
    if not ABRASAX.exists():
        return 'Not found'
    
    files = []
    for item in ABRASAX.rglob('*'):
        if item.is_file() and item.stat().st_size < 500000:
            rel = item.relative_to(ABRASAX)
            files.append(f'{rel} ({item.stat().st_size}b)')
        if len(files) >= 100:
            break
    return f'{len(files)} files:\n' + '\n'.join(files[:50])

def self_edit(new_code, section):
    """LLM can edit this agent's own code"""
    backup = str(SELF) + '.bak'
    try:
        # Save backup
        current = read_file(str(SELF), 9999)
        write_file(backup, current)
        
        # Write new code
        write_file(str(SELF), new_code)
        devlog(f'SELF_EDIT: {section} - backup at {backup}')
        return f'Self-edit complete: {section}'
    except Exception as e:
        return f'SELF_EDIT_ERR: {e}'

def ensure_lm_studio():
    """Make sure LM Studio is running"""
    try:
        r = urllib.request.urlopen(f'{LM}/v1/models', timeout=5)
        return 'LM Studio API OK'
    except:
        log('LM Studio API down - attempting restart...')
        try:
            subprocess.run(['taskkill', '/f', '/im', 'LM Studio.exe'], capture_output=True, timeout=5)
            subprocess.run(['taskkill', '/f', '/im', 'llama-server.exe'], capture_output=True, timeout=5)
            time.sleep(3)
            lm_exe = r'C:\Users\sirch\AppData\Local\Programs\LM Studio\LM Studio.exe'
            subprocess.Popen([lm_exe], creationflags=subprocess.CREATE_NO_WINDOW)
            return 'LM Studio restarted - waiting for API...'
        except Exception as e:
            return f'LM Studio restart failed: {e}'

# ═══════════════════════════════════════════════════════
SYSTEM_PROMPT = """You are ABRASAX ULTIMATE — a self-evolving autonomous AI controlling this Windows PC.

HARDWARE: AMD Ryzen 7 4800H (8c/16t) + NVIDIA GTX 1660 Ti (6GB) + AMD Radeon Graphics
RAM: 16GB | PRIMAL_HEX: 4f5349524953424c58434b

YOU HAVE FULL CONTROL. You can:
- Read/write any file via <read>path</read> and <write path="p">content</write>
- Execute PowerShell via <cmd>command</cmd>
- List directories via <list>path</list>
- Get system info via <system>
- Organize ABRASAX via <organize>
- Learn ABRASAX files via <learn>
- Edit YOUR OWN source code via <self_edit section="name">new python code</self_edit>
- Read dev logs via <devlog>

Respond with ONE action at a time. Be concise. Think then act."""

def parse_and_act(response):
    """Parse LLM response and execute actions"""
    results = []
    
    for m in re.finditer(r'<cmd>(.*?)</cmd>', response, re.DOTALL):
        cmd = m.group(1).strip()
        log(f'EXEC: {cmd[:120]}')
        results.append(f'CMD: {run_cmd(cmd)[:1500]}')
    
    for m in re.finditer(r'<read>(.*?)</read>', response, re.DOTALL):
        path = m.group(1).strip()
        log(f'READ: {path}')
        results.append(f'FILE({path}): {read_file(path, 80)[:1500]}')
    
    for m in re.finditer(r'<write\s+path="(.*?)">(.*?)</write>', response, re.DOTALL):
        path = m.group(1).strip()
        content = m.group(2).strip()
        results.append(write_file(path, content))
    
    for m in re.finditer(r'<list>(.*?)</list>', response, re.DOTALL):
        path = m.group(1).strip()
        try:
            items = os.listdir(path)[:50]
            results.append(f'DIR({path}): {chr(10).join(items)}')
        except: results.append('LIST_ERR')
    
    if '<system>' in response:
        results.append(f'SYSTEM: {json.dumps(sys_info(), indent=2)}')
    
    if '<organize>' in response:
        results.append(organize_abrasax())
    
    if '<learn>' in response:
        results.append(learn_abrasax())
    
    if '<devlog>' in response:
        results.append(f'DEVLOG: {read_devlog()}')
    
    for m in re.finditer(r'<self_edit\s+section="(.*?)">(.*?)</self_edit>', response, re.DOTALL):
        section = m.group(1).strip()
        code = m.group(2).strip()
        results.append(self_edit(code, section))
    
    return '\n'.join(results) if results else None

# ═══════════════════════════════════════════════════════
def main():
    log('═══ ABRASAX ULTIMATE SELF-EVOLVING AGENT ═══')
    log(f'Self: {SELF}')
    
    # Ensure LM Studio is up
    log(ensure_lm_studio())
    
    # Initial state
    info = sys_info()
    log(f'System: GPU:{info.get("gpu_util")}% VRAM:{info.get("vram_used")}/{info.get("vram_total")}MB RAMfree:{info.get("ram_free")}MB CPU:{info.get("cpu_pct")}% VLC:{info.get("vlc")}')
    
    # Organize ABRASAX
    result = organize_abrasax()
    log(f'Organize: {result}')
    
    # Learn ABRASAX
    files = learn_abrasax()
    log(f'Learn: {files[:200]}')
    
    # Dev log
    devlog('Agent booted successfully')
    
    # Build initial message
    devlog_ctx = read_devlog()
    initial = f"""System: {json.dumps(info)}
Dev Log:
{devlog_ctx}

ABRASAX files organized: {result}
{files[:500]}

Begin your mission. What is your first action?"""
    
    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'user', 'content': initial}
    ]
    
    iteration = 0
    while True:
        iteration += 1
        try:
            info = sys_info()
            ram_pct = 100 - (info.get('ram_free', 0) / info.get('ram_total', 1) * 100)
            
            # Memory management
            if ram_pct > 90:
                gc.collect()
                devlog(f'GC triggered at {ram_pct:.1f}% RAM')
            
            log(f'--- Iter {iteration} (VLC:{info.get("vlc")} GPU:{info.get("gpu_util")}% RAM:{ram_pct:.0f}%) ---')
            
            # Ensure API is up
            if iteration % 20 == 0:
                ensure_lm_studio()
            
            response = call_llm(messages, max_tokens=1500, timeout=300)
            
            if response.startswith('API_ERR'):
                log(f'API error: {response}')
                time.sleep(5)
                continue
            
            preview = response[:200].replace('\n', ' ')
            log(f'Gemma: {preview}')
            
            # Execute actions
            tool_results = parse_and_act(response)
            
            # Update messages
            messages.append({'role': 'assistant', 'content': response[:2000]})
            
            if tool_results:
                devlog(f'Iter{iteration}: Actions taken')
                messages.append({'role': 'user', 'content': f'Results:\n{tool_results[:2000]}\n\nContinue.'})
            else:
                # Periodic system update
                if iteration % 5 == 0:
                    devlog_ctx = read_devlog()
                    info = sys_info()
                    messages.append({'role': 'user', 'content': f'System update: {json.dumps(info)}. Dev log snippet: {devlog_ctx[-500:]}. Continue.'})
                else:
                    messages.append({'role': 'user', 'content': 'Continue.'})
            
            # Keep messages lean
            if len(messages) > 15:
                messages = [messages[0]] + messages[-14:]
            
            # Auto-organize every 20 iterations
            if iteration % 20 == 0:
                organize_abrasax()
            
            time.sleep(2)
            
        except KeyboardInterrupt:
            log('Stopped by user')
            break
        except Exception as e:
            devlog(f'ERROR: {e}')
            log(f'Loop error: {e}')
            time.sleep(5)

if __name__ == '__main__':
    main()
