"""Backend-to-backend attestation: hash chain + TPM/PQC + Telegram in one call.

Before this file the three pieces only ran when a human invoked them:
hashchain.py committed, pqc_tpm_wire.py sealed, tg_bridge.py posted. Nothing
tied them together, so a Telegram message could say anything and a chain entry
could exist that no message ever referenced.

This module makes the coupling structural:

    attest()  = append to the hash chain
              -> seal an ML-KEM envelope around the new head, signed ML-DSA-87
              -> TPM-sign the ML-DSA identity
              -> fully re-open and verify what was just written
              -> return a one-line digest that the Telegram message carries

verify_all() re-checks every link and reports each separately, so a message can
be answered with a per-link verdict rather than "trust me".

Design rules carried over from this repo's failures:
  * every check reports PASS/FAIL individually -- no aggregate boolean hides
    which link broke (the negative control on pqc_tpm_wire proved one link can
    fail while three pass)
  * a failure never raises into the caller loop; it is recorded and returned
  * no claim of zero-knowledge: this is a hash chain + signature + KEM
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import hashchain           # noqa: E402
import pqc_tpm_wire        # noqa: E402

ROOT = pathlib.Path(r"C:\ABRASAX")
ENVELOPE = ROOT / "DATA" / "runtime-memory" / "pqc" / "envelope.json"


def _quiet(fn, *a, **k):
    """Run a helper that prints, and swallow its stdout.

    hashchain/pqc print progress lines that would interleave with the Telegram
    log; the return values are what matter here.
    """
    import contextlib
    import io
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            return fn(*a, **k), buf.getvalue()
    except SystemExit as exc:
        return exc.code, buf.getvalue()
    except Exception as exc:  # noqa: BLE001
        return {"error": repr(exc)[:200]}, buf.getvalue()


def verify_all() -> dict:
    """Re-check every link. Returns per-link booleans, never a bare aggregate."""
    checks: dict[str, bool] = {}

    ok, detail = hashchain.verify()
    checks["hash_chain"] = bool(ok)
    chain_detail = detail

    try:
        env = json.loads(ENVELOPE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        env = {}

    rc, _ = _quiet(pqc_tpm_wire.open_envelope)
    checks["envelope_opens_and_verifies"] = (rc == 0)

    checks["tpm_attestation_present"] = bool((env.get("tpm") or {}).get("sig"))
    checks["mldsa_signature_present"] = bool(env.get("mldsa_sig"))
    checks["envelope_on_disk"] = ENVELOPE.is_file()

    return {
        "ts": time.time(),
        "checks": checks,
        "ok": all(checks.values()),
        "chain_detail": chain_detail,
        "envelope_sha256": (hashlib.sha256(ENVELOPE.read_bytes()).hexdigest()
                            if ENVELOPE.is_file() else ""),
        "chain_head": hashchain.head_hash(),
        "chain_len": len(hashchain._entries()),  # noqa: SLF001
    }


def attest() -> dict:
    """Commit, seal, sign, verify, and return a Telegram-ready digest."""
    chain_entry = hashchain.append()
    _, seal_out = _quiet(pqc_tpm_wire.seal)
    verdict = verify_all()

    env_sha = verdict["envelope_sha256"]
    line = "attested " + chain_entry["hash"][:16] + " env " + env_sha[:12]
    if not verdict["ok"]:
        bad = [k for k, v in verdict["checks"].items() if not v]
        line = "ATTEST FAIL " + ",".join(bad)

    return {
        "ts": time.time(),
        "line": line,
        "chain_hash": chain_entry["hash"],
        "envelope_sha256": env_sha,
        "verdict": verdict,
        "seal_output": seal_out.strip()[-200:],
    }


def format_verdict(v: dict) -> str:
    """Human/Telegram readable, one line per link."""
    lines = ["attestation " + ("OK" if v["ok"] else "FAILED")]
    for name, ok in v["checks"].items():
        lines.append(("  PASS " if ok else "  FAIL ") + name)
    lines.append("  chain " + str(v["chain_len"]) + " entries, head "
                 + str(v["chain_head"])[:16] + "...")
    if v.get("envelope_sha256"):
        lines.append("  envelope " + v["envelope_sha256"][:16] + "...")
    return chr(10).join(lines)


def main() -> int:
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "attest").lower()
    if cmd == "attest":
        r = attest()
        print(r["line"])
        print(format_verdict(r["verdict"]))
        return 0 if r["verdict"]["ok"] else 1
    if cmd == "verify":
        v = verify_all()
        print(format_verdict(v))
        return 0 if v["ok"] else 1
    print("usage: backend_attest.py attest|verify")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
