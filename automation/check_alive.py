"""Prove the live binding is moving the picture, not just logging.

A daemon that prints 'drive-ok' every 8 s proves nothing on its own: it could be
pushing the same field forever and the image would look frozen while every log
line said success.

This samples the rendered frame several times over a real interval and asserts:
  * the frame hash actually changes between samples,
  * each change is attributable to a fresh reply (heartbeat log grows),
  * the image is never a flat fill (the field stays structured).

Exit 0 = the picture is genuinely alive.
"""
import hashlib
import json
import struct
import sys
import time
import urllib.request
import zlib

RENDER = "http://127.0.0.1:9700"
HEARTBEAT = r"C:\ABRASAX\LOGS\alive-bind.jsonl"
SAMPLES = 5
GAP = 4.0


def frame_hash():
    url = f"{RENDER}/frame.png?clock={time.time():.3f}&exposure=24&yaw=0&pitch=0"
    with urllib.request.urlopen(url, timeout=20) as r:
        data = r.read()

    i, idat, ihdr = 8, b"", None
    while i < len(data):
        ln = struct.unpack(">I", data[i:i + 4])[0]
        typ = data[i + 4:i + 8]
        if typ == b"IHDR":
            ihdr = data[i + 8:i + 8 + ln]
        elif typ == b"IDAT":
            idat += data[i + 8:i + 8 + ln]
        i += 12 + ln
    w, h = struct.unpack(">II", ihdr[:8])
    raw = zlib.decompress(idat)
    st = 1 + w * 4
    px = bytearray()
    for y in range(h):
        px += raw[y * st + 1:(y + 1) * st]
    uniq = len(set(bytes(px[k:k + 4]) for k in range(0, len(px), 4)))
    return hashlib.sha256(bytes(px)).hexdigest()[:16], uniq


def hb_lines():
    try:
        with open(HEARTBEAT, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except OSError:
        return []


h0 = len(hb_lines())
print(f"heartbeat lines before: {h0}")

hashes = []
uniqs = []
for n in range(SAMPLES):
    dg, u = frame_hash()
    hashes.append(dg)
    uniqs.append(u)
    print(f"  sample {n}: sha={dg} unique_px={u}")
    if n < SAMPLES - 1:
        time.sleep(GAP)

h1 = len(hb_lines())
new = hb_lines()[h0:]

ok = True

distinct = len(set(hashes))
check = distinct >= 2
print(f"[{'PASS' if check else 'FAIL'}] frame changed across {SAMPLES} samples "
      f"({distinct} distinct hashes)")
ok &= check

check = h1 > h0
print(f"[{'PASS' if check else 'FAIL'}] heartbeat grew {h0} -> {h1} "
      f"({len(new)} new bind cycles)")
ok &= check

if new:
    oks = sum(1 for r in new if r.get("ok"))
    check = oks == len(new)
    print(f"[{'PASS' if check else 'FAIL'}] every new cycle reported drive-ok "
          f"({oks}/{len(new)})")
    ok &= check

    pushes = {r.get("push") for r in new}
    check = pushes == {"drive-ok"}
    print(f"[{'PASS' if check else 'FAIL'}] push outcomes: {sorted(str(p) for p in pushes)}")
    ok &= check

check = min(uniqs) >= 64
print(f"[{'PASS' if check else 'FAIL'}] image never went flat "
      f"(min unique_px {min(uniqs)})")
ok &= check

print("\nRESULT:", "PASS -- the rendered image is genuinely alive under the binding"
      if ok else "FAIL")
sys.exit(0 if ok else 1)
