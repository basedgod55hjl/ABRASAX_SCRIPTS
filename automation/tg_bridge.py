"""Telegram bridge: live ABRASAX state out, commands in.

Why Telegram and not a LAN socket
---------------------------------
"no matter where pc and phone is" rules out a local port: the phone and PC are
not guaranteed to be on the same network. Telegram's Bot API is a relay that
works from anywhere, needs no port forwarding, and is already authenticated by
the bot token that was present in .env and verified against getMe
(@botABRASAXbot, id 8619208012).

PRIVACY DEFAULT
---------------
ABRASAX_TELEGRAM_CHAT_ID held "@botABRASAXbot" -- the bot's own USERNAME, not a
conversation id. Sending to that fails. The real destination discovered from
getUpdates is a SUPERGROUP (-1002414432745, "MY INFORMATION-Orders-INFO
NEEDED", 2 members). A group is not a private chat, so this bridge sends a
minimal status line and deliberately EXCLUDES location by default. Pass
--with-location to include it; nothing else about the phone is ever sent.

Commands understood (only from the configured chat):
  status   -> current state
  chain    -> hash-chain head and length
  help
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(r"C:\ABRASAX")
ENV = ROOT / ".env"


def _env() -> dict:
    out = {}
    try:
        for line in ENV.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*([A-Z0-9_]+)\s*=\s*(.*)", line)
            if m:
                out[m.group(1)] = m.group(2).strip()
    except OSError:
        pass
    return out


def _api(tok: str, method: str, **params):
    url = f"https://api.telegram.org/bot{tok}/{method}"
    data = urllib.parse.urlencode(params).encode() if params else None
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode())
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": repr(exc)[:200]}


def _read(path: pathlib.Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def resolve_chat(tok: str, configured: str) -> str | None:
    """A numeric chat id is used as-is; anything else is a username typo and we
    fall back to the newest real conversation from getUpdates."""
    if re.fullmatch(r"-?\d+", configured or ""):
        return configured
    d = _api(tok, "getUpdates", limit=100)
    for u in reversed(d.get("result") or []):
        msg = (u.get("message") or u.get("edited_message")
               or u.get("channel_post") or {})
        chat = msg.get("chat") or {}
        if chat.get("id"):
            return str(chat["id"])
    return None


def status_text(with_location: bool = False) -> str:
    h = _read(ROOT / "DATA" / "runtime-memory" / "s25_senses.json")
    m = _read(ROOT / "DATA" / "runtime-memory" / "s25_motion.json")
    c = _read(ROOT / "DATA" / "runtime-memory" / "cost.json")

    overl = {}
    try:
        with urllib.request.urlopen("http://127.0.0.1:9627/health", timeout=3) as r:
            overl = json.loads(r.read().decode())
    except Exception:  # noqa: BLE001
        overl = {}

    b = h.get("battery") or {}
    s = h.get("storage") or {}
    fg = (h.get("foreground") or {}).get("package") or "-"

    lines = [
        "ABRASAX live",
        f"overlay {overl.get('fps', '?')} fps  frames {overl.get('frames', '?')}",
        f"phone motion {m.get('hz', '?')} Hz  pitch {m.get('pitch_deg', '?')} "
        f"yaw {m.get('yaw_deg', '?')}  shaking {m.get('moving')}",
        f"S25 {b.get('level_pct', '?')}%  {b.get('temp_c', '?')}C  {s.get('free_gb', '?')}GB free",
        f"fg {fg}",
        f"llm calls today {c.get('calls_today', '?')} "
        f"(paid {c.get('paid_calls_today', '?')}/{c.get('paid_budget', '?')})",
    ]
    if with_location:
        loc = h.get("location") or {}
        if loc.get("available"):
            lines.append(f"loc {loc.get('lat')},{loc.get('lon')}")
    return "\n".join(lines)


def chain_head() -> str:
    p = ROOT / "LOGS" / "state-chain.jsonl"
    try:
        lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        if not lines:
            return "chain empty"
        head = json.loads(lines[-1])
        return (f"chain {len(lines)} entries\n"
                f"head {head['hash'][:32]}...\n"
                f"at {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(head['ts']))}")
    except OSError:
        return "chain absent"


def send(tok: str, chat: str, text: str) -> dict:
    return _api(tok, "sendMessage", chat_id=chat, text=text,
                disable_web_page_preview="true")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    e = _env()
    tok = e.get("ABRASAX_TELEGRAM_TOKEN") or ""
    if not tok:
        print("no ABRASAX_TELEGRAM_TOKEN in .env")
        return 2
    chat = resolve_chat(tok, e.get("ABRASAX_TELEGRAM_CHAT_ID", ""))
    if not chat:
        print("no chat id: message the bot once, then retry")
        return 2
    with_loc = "--with-location" in argv

    if "--once" in argv:
        r = send(tok, chat, status_text(with_loc))
        print("send ok:", r.get("ok"), "chat:", chat)
        if not r.get("ok"):
            print("  ", r)
        return 0 if r.get("ok") else 1

    if "--watch" in argv:
        i = argv.index("--watch")
        period = float(argv[i + 1]) if i + 1 < len(argv) else 300.0
        last = None
        print(f"watching, posting every {period}s to {chat}", flush=True)
        while True:
            txt = status_text(with_loc)
            # only post when something moved, so a group of 2 is not spammed
            if txt != last:
                # Commit the state that is about to be published, so the posted
                # message and the hash chain attest each other: a reader can
                # verify the chain and see the same numbers we sent.
                # Full backend attestation: append to the hash chain, seal an
                # ML-KEM envelope around the new head, ML-DSA-sign it, have the
                # TPM sign the ML-DSA identity, then re-open and verify every
                # link. The digest goes into the message, so the post and the
                # chain reference each other.
                try:
                    sys.path.insert(0, str(ROOT / "SCRIPTS" / "automation"))
                    import backend_attest
                    at = backend_attest.attest()
                    txt = txt + f"\n{at['line']}"
                    try:
                        import pqc_tpm_wire
                        pqc_tpm_wire.push()   # keep the S25 copy in step
                    except Exception:  # noqa: BLE001
                        pass
                except Exception as exc:  # noqa: BLE001
                    txt = txt + f"\n(attest unavailable: {type(exc).__name__})"
                r = send(tok, chat, txt)
                print(f"{time.strftime('%H:%M:%S')} posted ok={r.get('ok')} "
                      f"chain={txt.rsplit(chr(10), 1)[-1]}", flush=True)
                last = txt
            time.sleep(period)

    if "--poll" in argv:
        print(f"polling commands for chat {chat}", flush=True)
        offset = 0
        while True:
            d = _api(tok, "getUpdates", offset=offset, timeout=30)
            for u in d.get("result") or []:
                offset = max(offset, int(u.get("update_id", 0)) + 1)
                msg = u.get("message") or {}
                cid = str((msg.get("chat") or {}).get("id") or "")
                text = (msg.get("text") or "").strip().lower()
                if cid != str(chat) or not text:
                    continue
                if text.startswith("status"):
                    send(tok, chat, status_text(with_loc))
                elif text.startswith("chain"):
                    send(tok, chat, chain_head())
                elif text.startswith("verify") or text.startswith("attest"):
                    try:
                        sys.path.insert(0, str(ROOT / "SCRIPTS" / "automation"))
                        import backend_attest
                        v = (backend_attest.attest() if text.startswith("attest")
                             else backend_attest.verify_all())
                        vd = v.get("verdict", v)
                        send(tok, chat, backend_attest.format_verdict(vd))
                    except Exception as exc:  # noqa: BLE001
                        send(tok, chat, "verify failed: " + type(exc).__name__)
                elif text.startswith("help"):
                    send(tok, chat, "commands: status, chain, verify, attest, help")
            time.sleep(1.0)

    print("nothing to do: pass --once | --watch SECONDS | --poll")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
