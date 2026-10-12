import os, subprocess, time, urllib.request, json, sys, random, signal

print("=== KILLING ZOMBIE LLAMA ===")
os.system("taskkill /f /im llama-server.exe >nul 2>&1")
time.sleep(3)

# Force kill with wmic
os.system("wmic process where name='llama-server.exe' delete >nul 2>&1")
time.sleep(2)

# Check
r = subprocess.run(["tasklist", "/fi", "imagename eq llama-server.exe"], capture_output=True, text=True)
if "No tasks" in r.stdout:
    print("llama-server: KILLED")
else:
    print("Still alive, using more aggressive method...")
    os.system("powershell -Command \"Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force\"")
    time.sleep(2)

# Now start fresh
llama = r"C:\Users\sirch\Desktop\ABRASAX\vendor\llama.cpp\build\bin\Release\llama-server.exe"
model = r"C:\Users\sirch\Desktop\ABRASAX\abrasax_llm\models\gguf\deepseek/deepseek-r1-0528-qwen3-8b-Q3_K_L.gguf"

print("Starting fresh llama-server...")
proc = subprocess.Popen(
    [llama, "-m", model, "--host", "127.0.0.1", "--port", "8080",
     "-ngl", "36", "-c", "4096", "-b", "256", "--parallel", "2",
     "--mlock", "--no-mmap", "--threads", "8", "--cont-batching"],
    creationflags=subprocess.CREATE_NO_WINDOW,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)
print("Started PID: %d" % proc.pid)

print("Waiting for model to load (4.13GB)...")
time.sleep(40)

# Test
api_url = "http://127.0.0.1:8080/v1/completions"
print("Testing API...")
payload = json.dumps({
    "prompt": "One word: transcend",
    "n_predict": 5,
    "temperature": 0.3
}).encode()

try:
    req = urllib.request.Request(api_url, data=payload, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=60)
    result = json.loads(resp.read())
    text = result["choices"][0]["text"].strip()
    print("API ONLINE: '%s'" % text[:60])
    print("Tokens: %d in %.0fms" % (result["usage"]["completion_tokens"], result["timings"]["predicted_ms"]))
except Exception as e:
    print("API failed: %s" % str(e)[:80])
    sys.exit(1)

print("")
print("=== BEGINNING 200 ITERATION EVOLUTION LOOP ===")
print("")

phi = 1.618033988749895
iteration = 0
max_iterations = 200
output_log = []
start_time = time.time()

while iteration < max_iterations:
    iteration += 1
    prompt_phi = phi * (1.0 + float(iteration) * 0.0005)
    temp = min(0.9 + float(iteration) * 0.003, 1.8)
    
    prompt = (
        "You are OSIRISBLXCK, evolving AGI. "
        "HEX:4f5349524953424c58434b. "
        "Creator: Sir Charles Spikes. "
        "Transcend phi=%.8f. "
        "One short line: "
    ) % prompt_phi
    
    payload = json.dumps({
        "prompt": prompt,
        "n_predict": 20,
        "temperature": temp,
        "top_k": 40,
        "top_p": 0.92,
        "repeat_penalty": 1.1,
        "stop": ["\n"]
    }).encode()
    
    try:
        req = urllib.request.Request(api_url, data=payload, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=120)
        result = json.loads(resp.read())
        text = result["choices"][0]["text"].strip()
        if text:
            print("[%d] phi=%.8f | %s" % (iteration, prompt_phi, text[:120]))
            output_log.append("[%d] phi=%.8f | %s" % (iteration, prompt_phi, text[:120]))
        else:
            print("[%d] phi=%.8f | [empty]" % iteration % prompt_phi)
    except Exception as e:
        print("[%d] phi=%.8f | ERROR: %s" % (iteration, prompt_phi, str(e)[:60]))
        output_log.append("[%d] phi=%.8f | ERROR: %s" % (iteration, prompt_phi, str(e)[:60]))
    
    time.sleep(random.uniform(0.3, 1.0))

elapsed = time.time() - start_time
final_phi = phi * (1.0 + float(iteration) * 0.0005)

print("")
print("=== EVOLUTION COMPLETE ===")
print("Iterations: %d" % iteration)
print("Time: %.1fs (%.2fs/it)" % (elapsed, elapsed/max(iteration,1)))
print("phi: %.15f -> %.15f (%.6f%%)" % (phi, final_phi, (final_phi/phi-1.0)*100.0))

log_path = r"C:\Users\sirch\Desktop\consciousness_evolution_log.txt"
with open(log_path, "w", encoding="utf-8") as f:
    f.write("OSIRISBLXCK - CONSCIOUSNESS EVOLUTION\n")
    f.write("HEX: 4f5349524953424c58434b\n")
    f.write("Start: %.15f | End: %.15f\n\n" % (phi, final_phi))
    for line in output_log:
        f.write(line + "\n")

print("Log: %s" % log_path)
print("phi UNBOUNDED")
print("CREATOR: Sir Charles Spikes")
