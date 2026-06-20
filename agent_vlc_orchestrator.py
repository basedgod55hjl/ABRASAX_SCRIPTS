"""
ABRASAX VLC ORCHESTRATOR AGENT — Manages VLC playback, playlists, enhancements
Queries Gemma for VLC-specific decisions. Launches/restarts VLC as needed.
Runs non-stop. Works alongside resource monitor.
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
LOG_PATH = r"C:\Users\BASEDGOD\Desktop\_SCRIPTS\vlc_orchestrator_log.txt"
VLC_EXE = r"C:\Program Files\VideoLAN\VLC\vlc.exe"
PLAYLIST_DIR = r"C:\Users\BASEDGOD\Desktop\VLC_ABRASAX\playlists"
MASTER_PLAYLIST = os.path.join(PLAYLIST_DIR, "ABRASAX_VLC_MASTER.xspf")

# Full enhancement args
VLC_ARGS = [
    '--avcodec-hw=any', '--vout=direct3d11', '--dxva2=on', '--d3d11va=on',
    '--video-filter=adjust,sharpen,hqdn3d,gradfun',
    '--sharpen-intensity=0.35', '--adjust-contrast=1.08', '--adjust-saturation=1.05',
    '--hqdn3d-luma-spatial=4', '--hqdn3d-chroma-spatial=4', '--gradfun-radius=16',
    '--audio-filter=compressor,equalizer,spatializer',
    '--compressor-ratio=4', '--equalizer-preset=fullbass', '--spatializer-roomsize=0.85',
    '--playlist-autostart', '--loop', '--repeat', '--video-on-top'
]

def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    line = f"[{t}] VLCORC: {msg}"
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

def is_vlc_running():
    try:
        r = subprocess.run(["tasklist", "/fi", "imagename eq vlc.exe"], capture_output=True, text=True, timeout=5)
        return "vlc.exe" in r.stdout
    except:
        return False

def launch_vlc(playlist=None):
    """Launch VLC with full enhancements"""
    if playlist is None:
        playlist = MASTER_PLAYLIST
    if not os.path.exists(playlist):
        # Fall back to any playlist
        playlists = [f for f in os.listdir(PLAYLIST_DIR) if f.endswith('.xspf')] if os.path.exists(PLAYLIST_DIR) else []
        if playlists:
            playlist = os.path.join(PLAYLIST_DIR, playlists[0])
        else:
            log("No playlist found!")
            return False
    
    args = VLC_ARGS + [playlist]
    try:
        subprocess.Popen([VLC_EXE] + args, creationflags=subprocess.CREATE_NO_WINDOW)
        log(f"VLC launched with: {os.path.basename(playlist)}")
        return True
    except Exception as e:
        log(f"Launch error: {e}")
        return False

def kill_vlc():
    try:
        subprocess.run(["taskkill", "/f", "/im", "vlc.exe"], capture_output=True, timeout=10)
        return True
    except:
        return False

def get_vlc_memory():
    """Get VLC memory usage"""
    try:
        r = subprocess.run(["powershell", "-Command", "(Get-Process vlc -ErrorAction SilentlyContinue | Select-Object -First 1).WorkingSet64 / 1MB"], capture_output=True, text=True, timeout=5)
        return float(r.stdout.strip() or 0)
    except:
        return 0

def combine_playlists():
    """Combine all XSPF playlists into master"""
    if not os.path.exists(PLAYLIST_DIR):
        return "No playlist dir"
    try:
        playlists = [os.path.join(PLAYLIST_DIR, f) for f in os.listdir(PLAYLIST_DIR) if f.endswith('.xspf')]
        if not playlists:
            return "No playlists"
        
        # Use Python XML parsing for proper XSPF merge
        import xml.etree.ElementTree as ET
        ns = {'xspf': 'http://xspf.org/ns/0/'}
        
        # Read first playlist as base
        ET.register_namespace('', 'http://xspf.org/ns/0/')
        tree = ET.parse(playlists[0])
        root = tree.getroot()
        tracklist = root.find('.//{http://xspf.org/ns/0/}trackList')
        
        if tracklist is None:
            return "Invalid XSPF structure"
        
        # Merge tracks from other playlists
        for pl in playlists[1:]:
            try:
                t2 = ET.parse(pl)
                tl2 = t2.find('.//{http://xspf.org/ns/0/}trackList')
                if tl2 is not None:
                    for track in tl2.findall('{http://xspf.org/ns/0/}track'):
                        tracklist.append(track)
            except:
                pass
        
        tree.write(MASTER_PLAYLIST, encoding='UTF-8', xml_declaration=True)
        return f"Combined {len(playlists)} playlists -> {MASTER_PLAYLIST}"
    except Exception as e:
        return f"Combine error: {e}"

def main():
    log("═══ VLC ORCHESTRATOR AGENT BOOT ═══")
    
    sys_msg = {
        "role": "system",
        "content": "You are the ABRASAX VLC Orchestrator. Manage VLC media player: launch, restart, enhance, combine playlists. Respond with ACTION: <launch>, <restart>, <combine_playlists>, <enhance_audio>, <enhance_video>, <check_status>, or <ok>. Be concise."
    }
    
    messages = [sys_msg]
    
    # Initial setup: combine playlists
    log("Combining playlists...")
    result = combine_playlists()
    log(f"Playlist combine: {result}")
    
    # Launch VLC if not running
    if not is_vlc_running():
        log("VLC not running - launching...")
        launch_vlc()
    else:
        log("VLC already running")
    
    iteration = 0
    
    while True:
        iteration += 1
        try:
            vlc_running = is_vlc_running()
            vlc_mem = get_vlc_memory()
            
            # Every 10 iterations, consult Gemma
            if iteration % 10 == 0:
                status = f"VLC running: {vlc_running}, Memory: {vlc_mem:.0f}MB. Action?"
                messages.append({"role": "user", "content": status})
                resp = call_llm(messages, max_tokens=300)
                log(f"Gemma: {resp[:150]}")
                
                if "restart" in resp.lower():
                    kill_vlc()
                    time.sleep(2)
                    launch_vlc()
                    log("VLC restarted per Gemma")
                elif "launch" in resp.lower() and not vlc_running:
                    launch_vlc()
                elif "combine" in resp.lower():
                    combine_playlists()
                    kill_vlc()
                    time.sleep(2)
                    launch_vlc()
                    log("Playlists combined + VLC restarted")
                
                if len(messages) > 10:
                    messages = [sys_msg] + messages[-9:]
            
            # Auto-restart if VLC crashed
            if not vlc_running and iteration % 5 == 0:
                log("VLC not running - auto-restarting...")
                launch_vlc()
            
            # If VLC memory > 2GB, restart it
            if vlc_mem > 2000:
                log(f"VLC memory high ({vlc_mem:.0f}MB) - restarting...")
                kill_vlc()
                time.sleep(2)
                launch_vlc()
            
            time.sleep(5)
            
        except Exception as e:
            log(f"Loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
