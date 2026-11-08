"""seal_env_to_tpm v3 — TPM-bound sealed containers for ABRASAX secrets.

WHY THIS EXISTS
  abrasax/tpm.py claimed TPM sealing but only computed a hash. v1 chunked RSA
  blocks: ECB-identical blocks, no integrity, no truncation guard. v2 was the
  design; v3 is the working implementation on top of the verified
  abrasax.cng primitives.

DESIGN
  wrap key : RSA-2048 persisted in "Microsoft Platform Crypto Provider".
             Private half never leaves the AMD fTPM. Created once, reused.
  CEK      : 32 bytes from BCryptGenRandom (system preferred RNG) per seal.
  IV       : 16 bytes from the same RNG per seal.
  cipher   : AES-256-CBC, PKCS#7 (userland, see abrasax.cng).
  integrity: HMAC-SHA256 over (header || wrapped || ciphertext), keyed by
             SHA-256(plaintext). A forged or truncated container cannot produce a
             matching tag without knowing the original bytes.
  layout   : MAGIC(8) | len(body)(4) | len(ct)(4) | body | ct | tag(32)
             body = header_json || 0x00 || rsa_wrap(CEK||IV)

CRYPTO BOUNDARY — do not overclaim
  The AES key and IV are wrapped by the TPM, so a container is useless on any
  other machine. AES/HMAC execute in software (CNG) while sealing/unsealing, so
  the plaintext and CEK live in this process's memory during the operation.
  At-rest protection is TPM-bound; in-flight protection is not claimed.

USAGE
  python seal_env_to_tpm_v3.py                # seal C:\\abrasax\\.env
  python seal_env_to_tpm_v3.py --verify       # unseal, compare, print verdict
  python seal_env_to_tpm_v3.py --admit        # exit 0 only if intact (wire gate)
  python seal_env_to_tpm_v3.py --tamper-test  # prove bitflip/truncation rejected
  python seal_env_to_tpm_v3.py --tree DIR     # seal a directory's manifest
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import hmac
import json
import os
import sys
import time

sys.path.insert(0, r"C:\abrasax")
from abrasax import cng  # noqa: E402

ROOT = r"C:\abrasax"
SEAL_DIR = os.path.join(ROOT, "CONFIG", "tpm-sealed")
ENV = os.path.join(ROOT, ".env")
NAME = "abrasax-env-v3"
PROVIDER = "Microsoft Platform Crypto Provider"
MAGIC = b"ABXSEAL3"
NCRYPT_SILENT_FLAG = 0x40
NCRYPT_OVERWRITE_KEY_FLAG = 0x80

ncrypt = ctypes.WinDLL("ncrypt")
ncrypt.NCryptOpenStorageProvider.restype = ctypes.c_long
ncrypt.NCryptOpenStorageProvider.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_wchar_p, ctypes.c_ulong]
ncrypt.NCryptCreatePersistedKey.restype = ctypes.c_long
ncrypt.NCryptCreatePersistedKey.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong]
ncrypt.NCryptOpenKey.restype = ctypes.c_long
ncrypt.NCryptOpenKey.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong]
ncrypt.NCryptFinalizeKey.restype = ctypes.c_long
ncrypt.NCryptFinalizeKey.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
ncrypt.NCryptEncrypt.restype = ctypes.c_long
ncrypt.NCryptEncrypt.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_ulong), ctypes.c_ulong]
ncrypt.NCryptDecrypt.restype = ctypes.c_long
ncrypt.NCryptDecrypt.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_ulong), ctypes.c_ulong]
ncrypt.NCryptFreeObject.restype = ctypes.c_long
ncrypt.NCryptFreeObject.argtypes = [ctypes.c_void_p]


# ---------------- TPM wrap key ----------------
def open_provider():
    p = ctypes.c_void_p()
    st = ncrypt.NCryptOpenStorageProvider(ctypes.byref(p), PROVIDER, NCRYPT_SILENT_FLAG)
    if st != 0:
        raise OSError(f"open provider {cng.hx(st)}")
    return p


def get_or_create_key(prov, name):
    k = ctypes.c_void_p()
    if ncrypt.NCryptOpenKey(prov, ctypes.byref(k), name, 0, 0) == 0:
        return k, "existing"
    k = ctypes.c_void_p()
    st = ncrypt.NCryptCreatePersistedKey(prov, ctypes.byref(k), "RSA", name, 0,
                                         NCRYPT_OVERWRITE_KEY_FLAG)
    if st != 0:
        raise OSError(f"create key {cng.hx(st)}")
    st = ncrypt.NCryptFinalizeKey(k, NCRYPT_SILENT_FLAG)
    if st != 0:
        raise OSError(f"finalize key {cng.hx(st)}")
    return k, "created"


def tpm_wrap(key, data):
    n = ctypes.c_ulong(0)
    st = ncrypt.NCryptEncrypt(key, data, len(data), None, None, ctypes.byref(n), 0)
    if st != 0:
        raise OSError(f"NCryptEncrypt size {cng.hx(st)}")
    buf = ctypes.create_string_buffer(n.value)
    st = ncrypt.NCryptEncrypt(key, data, len(data), None, buf, ctypes.byref(n), 0)
    if st != 0:
        raise OSError(f"NCryptEncrypt {cng.hx(st)}")
    return buf.raw[: n.value]


def tpm_unwrap(key, blob):
    n = ctypes.c_ulong(0)
    st = ncrypt.NCryptDecrypt(key, blob, len(blob), None, None, ctypes.byref(n), 0)
    if st != 0:
        raise OSError(f"NCryptDecrypt size {cng.hx(st)}")
    buf = ctypes.create_string_buffer(n.value)
    st = ncrypt.NCryptDecrypt(key, blob, len(blob), None, buf, ctypes.byref(n), 0)
    if st != 0:
        raise OSError(f"NCryptDecrypt {cng.hx(st)}")
    return buf.raw[: n.value]


# ---------------- container ----------------
def _mac(plaintext, payload):
    mk = hashlib.sha256(b"abx-seal3-mac\x00" + hashlib.sha256(plaintext).digest()).digest()
    return hmac.new(mk, hashlib.sha256(payload).digest(), hashlib.sha256).digest()


def seal_bytes(plaintext: bytes, name: str, prov) -> tuple[bytes, str]:
    cek = cng.rand(32)
    iv = cng.rand(16)
    with cng.AesCbc() as aes:
        ct = aes.encrypt(cek, iv, plaintext)
    key, how = get_or_create_key(prov, name)
    try:
        wrapped = tpm_wrap(key, cek + iv)
    finally:
        ncrypt.NCryptFreeObject(key)
    header = json.dumps({
        "v": 3, "name": name,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "alg": "AES-256-CBC/PKCS7 + HMAC-SHA256",
        "wrap": "RSA-2048 TPM-persisted (NCryptEncrypt)",
        "provider": PROVIDER,
        "plaintext_bytes": len(plaintext),
        "ciphertext_bytes": len(ct),
    }, sort_keys=True).encode()
    body = header + b"\x00" + wrapped
    tag = _mac(plaintext, body + ct)
    blob = MAGIC + len(body).to_bytes(4, "big") + len(ct).to_bytes(4, "big") + body + ct + tag
    return blob, how


def unseal_bytes(blob: bytes, name: str, prov) -> tuple[bytes, dict]:
    if not blob.startswith(MAGIC):
        raise ValueError("bad magic — not an ABXSEAL3 container")
    p = len(MAGIC)
    hlen = int.from_bytes(blob[p:p + 4], "big"); p += 4
    clen = int.from_bytes(blob[p:p + 4], "big"); p += 4
    if p + hlen + clen + 32 != len(blob):
        raise ValueError(f"length mismatch — truncated or padded container "
                         f"(header {hlen}, ct {clen}, total {len(blob)})")
    body = blob[p:p + hlen]; p += hlen
    ct = blob[p:p + clen]; p += clen
    tag = blob[p:p + 32]
    if b"\x00" not in body:
        raise ValueError("malformed body")
    header_b, wrapped = body.split(b"\x00", 1)
    header = json.loads(header_b)
    key, _ = get_or_create_key(prov, name)
    try:
        mat = tpm_unwrap(key, wrapped)
    finally:
        ncrypt.NCryptFreeObject(key)
    if len(mat) != 48:
        raise ValueError("wrapped key material has wrong length")
    cek, iv = mat[:32], mat[32:]
    with cng.AesCbc() as aes:
        pt = aes.decrypt(cek, iv, ct)
    if not hmac.compare_digest(_mac(pt, body + ct), tag):
        raise ValueError("MAC mismatch — container tampered or from another origin")
    if len(pt) != header["plaintext_bytes"]:
        raise ValueError("plaintext length disagrees with header")
    return pt, header


def tree_manifest(root: str) -> tuple[str, list]:
    acc = hashlib.sha256(b"")
    rows = []
    for dp, dns, fns in os.walk(root):
        dns.sort()
        for fn in sorted(fns):
            fp = os.path.join(dp, fn)
            h = hashlib.sha256(open(fp, "rb").read()).hexdigest()
            acc = hashlib.sha256(acc.digest() + h.encode())
            rows.append({"rel": os.path.relpath(fp, root).replace("\\", "/"),
                         "sha256": h, "bytes": os.path.getsize(fp)})
    return acc.hexdigest(), rows


# ---------------- CLI ----------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--admit", action="store_true")
    ap.add_argument("--tamper-test", action="store_true")
    a = ap.parse_args(argv)

    os.makedirs(SEAL_DIR, exist_ok=True)
    name = NAME if not a.tree else "abrasax-tree-" + hashlib.sha256(a.tree.encode()).hexdigest()[:12]
    sealed_path = os.path.join(SEAL_DIR, f"{name}.sealed")
    rec_path = os.path.join(SEAL_DIR, f"{name}.json")
    rec = json.load(open(rec_path)) if os.path.isfile(rec_path) else {}

    if a.verify or a.admit:
        if not os.path.isfile(sealed_path):
            print(f"ADMIT: FAIL — no container at {sealed_path}")
            return 2
        prov = open_provider()
        try:
            pt, header = unseal_bytes(open(sealed_path, "rb").read(), name, prov)
        except Exception as e:
            print(f"ADMIT: FAIL — {type(e).__name__}: {e}")
            return 2
        finally:
            ncrypt.NCryptFreeObject(prov)
        checks = []
        checks.append(("TPM unseal + MAC verified", True))
        checks.append(("size matches header", len(pt) == header["plaintext_bytes"]))
        if a.tree:
            term, rows = tree_manifest(a.tree)
            checks.append((f"tree digest matches ({len(rows)} files)", term == rec.get("tree_digest")))
        elif rec.get("env_sha256"):
            checks.append(("env content unchanged since seal",
                           hashlib.sha256(pt).hexdigest() == rec["env_sha256"]))
        for label, ok in checks:
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        verdict = all(ok for _, ok in checks)
        print(f"\nADMIT: {'PASS' if verdict else 'FAIL'}")
        return 0 if verdict else 3

    if a.tamper_test:
        prov = open_provider()
        try:
            blob = open(sealed_path, "rb").read()
            cases = {}
            flipped = bytearray(blob); flipped[len(blob) // 2] ^= 0x01
            cases["bitflip-mid"] = bytes(flipped)
            flipped_iv = bytearray(blob)
            flipped_iv[len(MAGIC) + 12] ^= 0x01
            cases["bitflip-header"] = bytes(flipped_iv)
            cases["truncate-tail"] = blob[:-8]
            cases["truncate-head"] = blob[4:]
            cases["append-junk"] = blob + b"\x00" * 16
            bad = 0
            for label, b in cases.items():
                try:
                    unseal_bytes(b, name, prov)
                    print(f"  tamper {label:16s} -> ACCEPTED (FAIL)")
                    bad += 1
                except Exception as e:
                    print(f"  tamper {label:16s} -> rejected ({type(e).__name__})")
            print(f"\nRESULT: {bad} accepted / {len(cases)} tamper cases")
            return 0 if bad == 0 else 4
        finally:
            ncrypt.NCryptFreeObject(prov)

    t0 = time.time()
    if a.tree:
        term, rows = tree_manifest(a.tree)
        payload = json.dumps({"root": a.tree, "digest": term, "files": rows},
                             sort_keys=True).encode()
        record = {"tree": a.tree, "tree_digest": term, "file_count": len(rows)}
        print(f"=== sealing tree {a.tree} ({len(rows)} files) ===")
    else:
        payload = open(ENV, "rb").read()
        record = {"source": ENV, "env_sha256": hashlib.sha256(payload).hexdigest()}
        print(f"=== sealing {ENV} ({len(payload):,} bytes) ===")

    prov = open_provider()
    try:
        blob, how = seal_bytes(payload, name, prov)
        print(f"  TPM key '{name}': {how}")
        open(sealed_path, "wb").write(blob)
        print(f"  container: {len(blob):,} bytes -> {sealed_path}")
        restored, header = unseal_bytes(blob, name, prov)
        ident = restored == payload
        leaked = payload[:32] in blob
        print(f"  round-trip identical : {ident}")
        print(f"  plaintext in container: {leaked}")
        record.update({
            "name": name, "sealed": sealed_path, "created": header["created"],
            "alg": header["alg"], "wrap": header["wrap"], "provider": PROVIDER,
            "plaintext_bytes": len(payload), "ciphertext_bytes": len(blob),
            "roundtrip_identical": ident, "elapsed_s": round(time.time() - t0, 3),
            "crypto_boundary": "AES/HMAC keys TPM-wrapped at rest; AES/HMAC execute "
                               "in CNG software during seal/unseal.",
        })
        json.dump(record, open(rec_path, "w", encoding="utf-8"), indent=2)
        print(f"  record -> {rec_path}")
        return 0 if ident and not leaked else 5
    finally:
        ncrypt.NCryptFreeObject(prov)


if __name__ == "__main__":
    sys.exit(main())
