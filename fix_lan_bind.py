#!/usr/bin/env python3
"""fix_lan_bind.py -- bind the stack to the LAN so the phone can reach it, safely.

The operator's requirement: "bind all, github, telegram and pc ... so abrasax is always
online". Measured state on 2026-11-01: LM Studio already listened on 0.0.0.0:1234, but the
gateway was 127.0.0.1:9001, the UI was 127.0.0.1:8090 and no firewall rule existed, so a
phone on the same Wi-Fi could reach the models and nothing else.

This does the binding with the invariant the gateway itself enforces: a non-loopback bind
requires bearer auth (`_assert_bind_is_safe`), so a token is generated once and written to
.env, and the launcher/supervisor inherit it. A phone that cannot present the token gets a
401 -- the bind is open, the spend is not.

What it changes (all idempotent):
  * .env gains ABRASAX_GATEWAY_TOKEN (random, 32 hex) if absent;
  * supervisor AUTOSTART: gateway gets --host 0.0.0.0, the static UI gets --bind 0.0.0.0;
  * UI/abrasax-ui/web/phone.html -- one page with the exact endpoints for the phone;
  * Windows firewall: allow TCP 9001/8090/1234 from the local subnet only.

Run: python SCRIPTS/fix_lan_bind.py [--check]
"""
from __future__ import annotations

import re
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
SUPERVISOR = ROOT / "SCRIPTS" / "automation" / "supervisor.py"
PHONE = ROOT / "UI" / "abrasax-ui" / "web" / "phone.html"

SUBNET = "192.168.1.0/24"
PORTS = {"ABRASAX-gateway": 9001, "ABRASAX-ui": 8090, "ABRASAX-gguf(api)": 1234}

PHONE_HTML = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>ABRASAX - phone</title>
<style>
 :root{--bg:#14141e;--violet:#7c6cf0;--mint:#2ee6a0;--dim:#9a9ab0}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:#e8e8f2;font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;padding:18px}
 h1{font-size:20px;margin:0 0 4px;letter-spacing:.04em}
 h1 span{color:var(--mint)}
 .sub{color:var(--dim);font-size:12px;margin-bottom:18px}
 .card{background:#1c1c28;border:1px solid #2a2a3a;border-radius:14px;padding:14px;margin:0 0 12px}
 .card h2{font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:var(--violet);margin:0 0 8px}
 code,label{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}
 .row{display:flex;gap:8px;align-items:center;margin:6px 0}
 .row code{flex:1;background:#101018;border:1px solid #2a2a3a;border-radius:8px;padding:8px;overflow:auto;white-space:nowrap}
 button{background:var(--violet);color:#fff;border:0;border-radius:8px;padding:8px 10px;font-size:12px}
 button.ghost{background:#2a2a3a}
 .ok{color:var(--mint)} .bad{color:#ff6b6b}
 input{width:100%;background:#101018;border:1px solid #2a2a3a;border-radius:8px;color:#e8e8f2;padding:8px}
 .hint{color:var(--dim);font-size:11.5px;margin-top:6px}
</style></head><body>
<h1>ABRASAX <span>online</span></h1>
<div class="sub">PRIMAL_HEX 4f5349524953424c58434b &middot; phi 1.618</div>

<div class="card">
  <h2>Gateway (chat / sensors / brain)</h2>
  <div class="row"><code id="gw"></code><button onclick="cp('gw')">copy</button></div>
  <label>bearer token</label>
  <input id="tok" placeholder="ABRASAX_GATEWAY_TOKEN" autocomplete="off">
  <div class="row" style="margin-top:10px">
    <button onclick="ping('/health','gwst')">/health</button>
    <button class="ghost" onclick="ping('/v1/sensors/state','gwst')">/sensors</button>
    <button class="ghost" onclick="ping('/v1/models','gwst')">/models</button>
    <span id="gwst" class="hint">idle</span>
  </div>
</div>

<div class="card">
  <h2>GGUF models (LM Studio, OpenAI-compatible)</h2>
  <div class="row"><code id="lm"></code><button onclick="cp('lm')">copy</button></div>
  <div class="hint">Any GGUF resident on the PC is served here. Use this URL + key in any
  OpenAI-compatible phone app (Jan, ChatterUI, LM Studio mobile, Open WebUI):</div>
  <label style="display:block;margin-top:8px">base URL</label>
  <input id="lmurl" readonly>
  <label style="display:block;margin-top:8px">API key</label>
  <input id="lmkey" placeholder="LM Studio key" autocomplete="off">
</div>

<div class="card">
  <h2>Telegram</h2>
  <div class="row"><code>@botABRASAXbot</code><button onclick="navigator.clipboard.writeText('@botABRASAXbot')">copy</button></div>
  <div class="hint">/status /sensors /model /ping &mdash; the backend polls continuously on the PC.</div>
</div>

<div class="card">
  <h2>Hermes agent bus (live)</h2>
  <div class="row"><code id="core"></code><button onclick="cp('core')">copy</button></div>
  <div class="hint">REST + WebSocket. POST /api/task {"type":"route",...} reaches a real agent.</div>
</div>

<script>
 const host = location.hostname || 'localhost';
 const GW  = 'http://' + host + ':9001';
 const LM  = 'http://' + host + ':1234/v1';
 const CORE= 'http://' + host + ':4200';
 document.getElementById('gw').textContent = GW;
 document.getElementById('lm').textContent = LM;
 document.getElementById('lmurl').value = LM;
 document.getElementById('core').textContent = CORE;
 const saved = localStorage.getItem('abr_tok') || '';
 document.getElementById('tok').value = saved;
 document.getElementById('tok').oninput = e => localStorage.setItem('abr_tok', e.target.value);
 function cp(id){ navigator.clipboard.writeText(document.getElementById(id).textContent); }
 async function ping(path, out){
   const el = document.getElementById(out);
   el.textContent = '...'; el.className = 'hint';
   try {
     const r = await fetch(GW + path, {headers: {'Authorization': 'Bearer ' + (localStorage.getItem('abr_tok')||'')}});
     const t = await r.text();
     el.textContent = r.status + ' ' + t.slice(0, 90);
     el.className = r.ok ? 'ok' : 'bad';
   } catch (e) { el.textContent = 'unreachable: ' + e.message; el.className = 'bad'; }
 }
</script>
</body></html>
"""


def ensure_token() -> str:
    text = ENV.read_text(encoding="utf-8") if ENV.exists() else ""
    m = re.search(r"^ABRASAX_GATEWAY_TOKEN=(\S+)$", text, re.M)
    if m and m.group(1).strip():
        return m.group(1).strip()
    token = secrets.token_hex(16)
    if text and not text.endswith("\n"):
        text += "\n"
    ENV.write_text(text + f"ABRASAX_GATEWAY_TOKEN={token}\n", encoding="utf-8")
    return token


def patch_supervisor() -> list[str]:
    notes = []
    src = SUPERVISOR.read_text(encoding="utf-8-sig")

    gw_old = '"cmd": [sys.executable, "-m", "abrasax", "gateway", "--port", "9001"],'
    gw_new = ('"cmd": [sys.executable, "-m", "abrasax", "gateway", "--host", "0.0.0.0",\n'
              '                "--port", "9001"],')
    if "--host\", \"0.0.0.0\"" not in src and gw_old in src:
        src = src.replace(gw_old, gw_new, 1)
        notes.append("gateway -> 0.0.0.0:9001 (bearer token required)")

    ui_old = '"cmd": [sys.executable, "-m", "http.server", "8090", "--bind", "127.0.0.1"],'
    ui_new = '"cmd": [sys.executable, "-m", "http.server", "8090", "--bind", "0.0.0.0"],'
    if ui_old in src:
        src = src.replace(ui_old, ui_new, 1)
        notes.append("ui -> 0.0.0.0:8090")
    if notes:
        SUPERVISOR.write_text(src, encoding="utf-8")
    return notes


def firewall() -> list[str]:
    """Allow the three ports from the local subnet only (never from anywhere)."""
    notes = []
    for name, port in PORTS.items():
        check = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", f"name={name}"],
            capture_output=True, text=True,
        )
        if check.returncode == 0 and "No rules match" not in check.stdout:
            notes.append(f"{name}: rule already present")
            continue
        add = subprocess.run(
            ["netsh", "advfirewall", "firewall", "add", "rule", f"name={name}",
             "dir=in", "action=allow", "protocol=TCP", f"localport={port}",
             f"remoteip={SUBNET}"],
            capture_output=True, text=True,
        )
        notes.append(f"{name}: " + ("added" if add.returncode == 0 else f"FAILED {add.stdout}{add.stderr}"))
    return notes


def main() -> int:
    token = ensure_token()
    phone_exists = PHONE.exists() and "ABRASAX <span>online</span>" in PHONE.read_text(encoding="utf-8", errors="replace")
    src = SUPERVISOR.read_text(encoding="utf-8-sig")
    bound = '"--host", "0.0.0.0"' in src and '"--bind", "0.0.0.0"' in src

    if "--check" in sys.argv:
        print(("PASS " if (bound and phone_exists and token) else "FAIL ")
              + f"lan bind: gateway_public={bound} phone_page={phone_exists} token={'set' if token else 'missing'}")
        return 0 if (bound and phone_exists and token) else 1

    if not phone_exists:
        PHONE.parent.mkdir(parents=True, exist_ok=True)
        PHONE.write_text(PHONE_HTML, encoding="utf-8")
        print(f"  + {PHONE.relative_to(ROOT)}")
    for n in patch_supervisor():
        print("  + " + n)
    for n in firewall():
        print("  + fw " + n)
    print("lan bind configured (token in .env, subnet-limited firewall rules)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
