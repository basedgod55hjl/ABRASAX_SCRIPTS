"""Prove the full chain: LLM reply -> field -> rendered pixels.

This is the end-to-end claim, so it is tested end to end and nothing is mocked:

  1. ask the live LLM router two semantically different prompts
  2. build each drive field from the actual reply text
  3. POST each to the renderer's /drive
  4. fetch /frame.png and compare

If different model replies produce identical frames, the "AI drives the visual"
claim is false. If they differ, it is true and reproducible.

Exit 0 = the chain is real.
"""
import base64
import hashlib
import json
import struct
import sys
import urllib.request
import zlib

sys.path.insert(0, r"C:\ABRASAX")
sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")

from string_brain import W, H, build_field, tokenize, ask_llm

RENDER = "http://127.0.0.1:9700"


def post(path, payload, timeout=15):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(RENDER + path, data=body,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode()


def get(path, timeout=20):
    with urllib.request.urlopen(RENDER + path, timeout=timeout) as r:
        return r.read()


def decode(data):
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
    return bytes(px)


def digest(px):
    return hashlib.sha256(px).hexdigest()[:16]


def drive(text, clock=0.0):
    field = build_field(tokenize(text), clock=clock)
    raw = bytes(int(max(0.0, min(1.0, v)) * 255) for v in field)
    st, resp = post("/drive", {"w": W, "h": H,
                               "data": base64.b64encode(raw).decode()})
    return field, st, resp


ok = True

P1 = "Describe a storm in exactly one short sentence."
P2 = "Describe silence in exactly one short sentence."

print(f"prompt A: {P1}")
a_text, a_route, a_model, a_dt = ask_llm(P1, max_tokens=40)
print(f"  reply  : {a_text[:90]}")
print(f"  route  : {a_route}  model: {a_model}  {a_dt:.2f}s")

print(f"prompt B: {P2}")
b_text, b_route, b_model, b_dt = ask_llm(P2, max_tokens=40)
print(f"  reply  : {b_text[:90]}")
print(f"  route  : {b_route}  model: {b_model}  {b_dt:.2f}s")

check = bool(a_text) and bool(b_text) and a_text != b_text
print(f"[{'PASS' if check else 'FAIL'}] the model produced two different replies")
ok &= check

fa, sta, ra = drive(a_text, clock=0.0)
pa = digest(decode(get("/frame.png?clock=0&exposure=24&yaw=0&pitch=0")))
print(f"drive A: HTTP {sta}  frame sha={pa}")

fb, stb, rb = drive(b_text, clock=0.0)
pb = digest(decode(get("/frame.png?clock=0&exposure=24&yaw=0&pitch=0")))
print(f"drive B: HTTP {stb}  frame sha={pb}")

check = sta == 200 and stb == 200
print(f"[{'PASS' if check else 'FAIL'}] both AI fields were accepted by the renderer")
ok &= check

check = pa != pb
print(f"[{'PASS' if check else 'FAIL'}] different AI replies render different pixels")
ok &= check

# determinism: same reply twice -> same pixels
drive(a_text, clock=0.0)
pa2 = digest(decode(get("/frame.png?clock=0&exposure=24&yaw=0&pitch=0")))
check = pa2 == pa
print(f"[{'PASS' if check else 'FAIL'}] same reply renders identically ({pa2})")
ok &= check

# the field really came from the text, not a constant
check = list(fa) != list(fb)
print(f"[{'PASS' if check else 'FAIL'}] the two drive fields differ "
      f"(A mean {sum(fa)/len(fa):.4f}, B mean {sum(fb)/len(fb):.4f})")
ok &= check

print("\nRESULT:", "PASS -- LLM output genuinely drives the rendered image"
      if ok else "FAIL")
sys.exit(0 if ok else 1)
