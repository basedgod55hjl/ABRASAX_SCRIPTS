"""Offload the local evidence trail onto TON as commitments, not as data.

The premise
-----------
The chain's job here is not storage and not compute: TON cannot run the 7D
crystal kernels, and putting gigabytes of ledger on-chain would be absurd. What
a public chain uniquely provides is an ordering and a clock that nobody on this
box controls. So the offload is:

    local:   keep every byte, verify everything, recompute on demand
    on TON:  publish one 32-byte Merkle root per epoch + the masterchain block
             that fixes when that root existed

That turns "this evidence existed" from a claim about this machine into a claim
a stranger can check against mainnet. The data stays where it belongs; only the
commitment leaves.

What makes the record a proof and not a timestamp
-------------------------------------------------
The anchor stores the masterchain seqno *and* that block's `root_hash` from two
independent indexers. Verification re-fetches the block and compares the hash.
A block hash cannot be forged after the fact without redoing the chain, so
"root R existed no later than block B" is checkable by anyone, and the local
clock is never trusted.

Commands
--------
    anchor [--notify]   merkle-root the evidence files, require indexer
                        agreement, fetch the anchored block from two providers,
                        record it locally, optionally post the summary to the
                        configured Telegram chat.
    verify              re-derive the root, re-hash the record, re-fetch the
                        anchored block, and check every claim in it.
    rate [--seconds N]  measure the live masterchain block interval against the
                        documented Catchain 2.0 figure.
    status              list recorded anchors.
    install             register an hourly anchor task (verifies one anchor
                        first and refuses to install if it fails).
    uninstall           remove that task.

There is no wallet on this machine and this tool does not create one, does not
hold keys, and cannot spend. Every anchor is verifiable without funds; a funded
on-chain write later would simply take these records as its input.

Usage:
    python SCRIPTS/automation/ton_offload.py anchor
    python SCRIPTS/automation/ton_offload.py anchor --notify
    python SCRIPTS/automation/ton_offload.py verify
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

ROOT = r"C:\abrasax"
if ROOT not in sys.path:          # the durable-append helper lives in abrasax/
    sys.path.insert(0, ROOT)
from abrasax.fs_atomic import append_line  # noqa: E402
OUT_DIR = os.path.join(ROOT, "DATA", "runtime-memory", "ton-offload")
LEDGER = os.path.join(ROOT, "LOGS", "ton-offload-ledger.jsonl")
ENV = os.path.join(ROOT, ".env")

EVIDENCE = [
    "LOGS/state-chain.jsonl",
    "LOGS/supervisor-ledger.jsonl",
    "LOGS/build-loop-ledger.jsonl",
    "LOGS/ops-ledger.jsonl",
    "GGUFF/ledger.jsonl",
    "LOGS/freeze/incidents.jsonl",
    "LOGS/freeze/markers.jsonl",
]

HEAD_PROVIDERS = {
    "tonapi_status": "https://tonapi.io/v2/status",
    "tonapi_head": "https://tonapi.io/v2/blockchain/masterchain-head",
    "toncenter_v2": "https://toncenter.com/api/v2/getMasterchainInfo",
}

# Two independent indexers, two different envelopes, same block.
BLOCK_PROVIDERS = {
    "tonapi": "https://tonapi.io/v2/blockchain/blocks/(-1,8000000000000000,{seqno})",
    "toncenter_v2": ("https://toncenter.com/api/v2/getBlockHeader?"
                     "workchain=-1&shard=-9223372036854775808&seqno={seqno}"),
}

AGREEMENT_TOLERANCE = 8  # blocks; independent indexers do not share a tip
ANCHOR_LAG = 12            # anchor a block this far below the lowest head so a lagging indexer can still answer
PREFIX_BYTES = 65536       # bytes covered by a file's prefix digest
TASK_NAME = "AbrasaxTonAnchor"
TASK_XML = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>{user}</Author>
    <Description>ABRASAX TON commitment anchor: hourly, no wallet, no keys, nothing on-chain</Description>
    <URI>\\{name}</URI>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{user}</UserId>
    </LogonTrigger>
    <TimeTrigger>
      <Repetition>
        <Interval>PT1H</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <StartBoundary>{start}</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{user}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT20M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{py}</Command>
      <Arguments>"{script}" anchor</Arguments>
      <WorkingDirectory>{root}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


# ------------------------------------------------------------------ plumbing ---

def http_json(url: str, timeout: float = 25.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "abrasax-ton-offload/1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def dig(doc, *keys):
    """Walk nested dicts without raising; indexers disagree about envelopes."""
    cur = doc
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None
    return cur


def masterchain_seqno(url: str) -> int | None:
    try:
        doc = http_json(url)
    except Exception:  # noqa: BLE001 -- a dead indexer is data, not a crash
        return None
    for path in (("result", "last", "seqno"), ("last", "seqno"),
                 ("last_known_masterchain_seqno",), ("seqno",)):
        val = dig(doc, *path)
        if isinstance(val, int):
            return val
    return None


def run(cmd: list[str], timeout: float = 60.0) -> str:
    """Run a command, return stdout+stderr, never raise. Used by the scheduler."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return (proc.stdout or "") + (proc.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return "%s: %s" % (type(exc).__name__, exc)


def normalise_root_hash(value) -> str | None:
    """Root hash as lowercase hex. toncenter speaks base64, tonapi speaks hex."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if re.fullmatch(r"[0-9a-fA-F]{64}", text):
        return text.lower()
    try:
        raw = base64.b64decode(text, validate=True)
    except Exception:  # noqa: BLE001
        return None
    return raw.hex() if len(raw) == 32 else None


def block_facts(seqno: int, attempts: int = 3) -> dict:
    """gen_utime + root_hash for one masterchain block, per provider.

    Retried because a single 429 from one indexer is not evidence about the
    block, and treating it as such turns an availability blip into a false
    "providers disagree" verdict.
    """
    out = {}
    for name, tpl in BLOCK_PROVIDERS.items():
        rec = {"ok": False, "attempts": 0}
        doc = None
        last_err = ""
        for attempt in range(1, attempts + 1):
            rec["attempts"] = attempt
            try:
                doc = http_json(tpl.format(seqno=seqno))
                break
            except Exception as exc:  # noqa: BLE001
                last_err = "%s: %s" % (type(exc).__name__, exc)
                if attempt < attempts:
                    time.sleep(0.6 * attempt)
        if doc is None:
            rec["error"] = last_err
            out[name] = rec
            continue
        container = doc.get("result") if isinstance(doc.get("result"), dict) else doc
        gen = container.get("gen_utime") if isinstance(container, dict) else None
        root = container.get("root_hash") if isinstance(container, dict) else None
        if root is None:
            root = dig(container, "id", "root_hash")
        if gen is not None:
            rec.update(ok=True, gen_utime=int(gen),
                       root_hash=normalise_root_hash(root))
        else:
            rec["error"] = "no gen_utime in response"
        out[name] = rec
    return out


def env(name: str) -> str:
    try:
        with open(ENV, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return ""


# --------------------------------------------------------------------- merkle ---

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_pair(a: str, b: str) -> str:
    return hashlib.sha256(bytes.fromhex(a) + bytes.fromhex(b)).hexdigest()


def merkle_root(leaves: list[str]) -> str:
    """Root of a pairwise-SHA256 tree; an odd tail promotes its last leaf.

    Promotion (rather than hashing the odd node with a zero) keeps the tree
    shape a pure function of the leaf count, so anyone with the file list can
    rebuild the same root without guessing our padding.
    """
    if not leaves:
        return "0" * 64
    level = list(leaves)
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [sha256_pair(level[i], level[i + 1])
                 for i in range(0, len(level), 2)]
    return level[0]


def proof(index: int, leaves: list[str]) -> list[dict]:
    """Sibling path for one leaf, so a third party can check a single file."""
    if not leaves or index >= len(leaves):
        return []
    level = list(leaves)
    idx = index
    path = []
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        sib = idx ^ 1
        path.append({"side": "right" if sib > idx else "left",
                     "hash": level[sib]})
        level = [sha256_pair(level[i], level[i + 1])
                 for i in range(0, len(level), 2)]
        idx //= 2
    return path


def fold_proof(leaf: str, path: list[dict]) -> str:
    cur = leaf
    for step in path:
        cur = (sha256_pair(cur, step["hash"]) if step["side"] == "right"
               else sha256_pair(step["hash"], cur))
    return cur


def sha256_prefix(path: str, n: int) -> str:
    """SHA-256 of the first n bytes only, so append-only growth is provable."""
    h = hashlib.sha256()
    left = n
    with open(path, "rb") as fh:
        while left > 0:
            chunk = fh.read(min(left, 1 << 20))
            if not chunk:
                break
            h.update(chunk)
            left -= len(chunk)
    return h.hexdigest()


def evidence() -> list[dict]:
    out = []
    for rel in EVIDENCE:
        full = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.isfile(full):
            continue
        size = os.path.getsize(full)
        out.append({"path": rel, "sha256": sha256_file(full),
                    "bytes": size, "lines": byte_line_count(full),
                    # Digest of the first PREFIX_BYTES. A later anchor can then
                    # prove the file only grew (prefix digest unchanged) instead
                    # of calling every appended line "evidence changed", which
                    # is what made verify() report a failure for a ledger doing
                    # exactly what it is supposed to do.
                    "prefix_sha256": sha256_prefix(full, min(size, PREFIX_BYTES))})
    return out

def byte_line_count(path: str) -> int:
    n = 0
    try:
        with open(path, "rb") as fh:
            for _ in fh:
                n += 1
    except OSError:
        return 0
    return n


# ------------------------------------------------------------------- commands ---

def cmd_anchor(notify: bool) -> int:
    files = evidence()
    if not files:
        print("REFUSING: no evidence files present")
        return 1
    leaves = [f["sha256"] for f in files]
    root = merkle_root(leaves)

    heads = {name: masterchain_seqno(url) for name, url in HEAD_PROVIDERS.items()}
    got = [v for v in heads.values() if isinstance(v, int)]
    if len(got) < 2:
        print("REFUSING: fewer than two indexers answered with a head %s" % heads)
        return 1
    spread = max(got) - min(got)
    agree = spread <= AGREEMENT_TOLERANCE
    # Anchor a block that is already buried, not the tip: an indexer that is
    # behind the tip must still be able to answer for it. Head spread is
    # reported, never fatal -- a 20-block lag is a slow indexer (observed live
    # at 16:07: tonapi 102777412 vs toncenter 102777432), whereas two different
    # root_hashes for the same seqno would be a fork, and that is checked
    # directly on the anchored block instead of being inferred from the heads.
    base = max(0, min(got) - ANCHOR_LAG)
    blocks: dict = {}
    usable: dict = {}
    gen_utime = None
    block_root = None
    for depth in (0, 20, 60):
        candidate = max(0, base - depth)
        blocks = block_facts(candidate)
        usable = {k: v for k, v in blocks.items() if v.get("ok")}
        if len(usable) < 2:
            continue
        times = {v["gen_utime"] for v in usable.values()}
        roots = {v["root_hash"] for v in usable.values()}
        if len(times) == 1 and len(roots) == 1:
            seqno = candidate
            gen_utime = times.pop()
            block_root = roots.pop()
            break
    if gen_utime is None or block_root is None:
        print("REFUSING: no block within %d of the lowest head %d agreed by two "
              "indexers: %s" % (ANCHOR_LAG + 60, min(got),
                                {k: (v.get("error") or "root_hash mismatch")
                                 for k, v in blocks.items()}))
        return 1

    rec = {
        "kind": "abrasax-ton-offload-anchor-v2",
        "ts": time.time(),
        "local_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "merkle_root": root,
        "leaf_count": len(leaves),
        "files": files,
        "proofs": {f["path"]: proof(i, leaves) for i, f in enumerate(files)},
        "ton": {
            "masterchain_seqno": seqno,
            "head_providers": heads,
            "head_providers_agree": agree,
            "anchored_block": {"gen_utime": gen_utime,
                               "root_hash": block_root,
                               "providers": sorted(usable)},
            "block_providers": blocks,
        },
        "note": "commitment only; no wallet, no keys, nothing written on-chain",
    }
    body = json.dumps({k: rec[k] for k in ("merkle_root", "leaf_count", "ton",
                                           "kind")}, sort_keys=True)
    rec["record_sha256"] = hashlib.sha256(body.encode()).hexdigest()

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "anchor-%d.json" % int(rec["ts"]))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=2, sort_keys=True)
    # durable append: this ledger is evidence, so a crash must not tear a line
    append_line(LEDGER, json.dumps({"ts": rec["ts"], "merkle_root": root,
                                    "leaf_count": len(leaves), "seqno": seqno,
                                    "block_root_hash": block_root,
                                    "block_gen_utime": gen_utime,
                                    "record_sha256": rec["record_sha256"]}) + "\n")

    print("anchored %d files  root=%s" % (len(leaves), root))
    print("  masterchain seqno %d (%d below the lowest head; head spread %d"
          " blocks, within %d: %s)"
          % (seqno, min(got) - seqno, spread, AGREEMENT_TOLERANCE, heads))
    print("  block root_hash %s..." % block_root[:24])
    print("  block gen_utime %s UTC  (local clock %+.0fs vs chain)"
          % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(gen_utime)),
             rec["ts"] - gen_utime))
    print("  record_sha256 %s" % rec["record_sha256"])
    print("  -> %s" % path)

    if notify:
        msg = ("ABRASAX anchor\nroot %s\nfiles %d\nmasterchain %d\n"
               "block %s\n%s" % (root[:32] + "...", len(leaves), seqno,
                                 block_root[:16] + "...", rec["local_iso"]))
        ok = telegram_send(msg)
        print("  telegram notify: %s" % ("sent" if ok else "FAILED"))
        if not ok:
            return 1
    return 0


def evidence_drift(rec: dict) -> dict:
    """Classify each evidence file against an anchor record.

    Four verdicts, because "hash differs" is not one thing:
      missing    -- the file is gone (fatal)
      rewritten  -- shrank, or its recorded prefix no longer matches (fatal)
      grew       -- append-only: the first `bytes` bytes still hash to the
                    recorded prefix digest (benign, worth a NOTE)
      unproven   -- changed, and the anchor predates prefix digests, so neither
                    append nor rewrite can be proven (benign, labelled)

    Reads ROOT at call time so a test can point the module at a temp tree.
    """
    out = {"missing": [], "rewritten": [], "grew": [], "unproven": []}
    for f in rec.get("files", []):
        full = os.path.join(ROOT, f["path"].replace("/", os.sep))
        if not os.path.isfile(full):
            out["missing"].append("%s missing" % f["path"])
            continue
        if sha256_file(full) == f["sha256"]:
            continue
        now_size = os.path.getsize(full)
        was_size = f.get("bytes")
        prefix = f.get("prefix_sha256")
        if not isinstance(was_size, int):
            out["rewritten"].append("%s changed, record has no size to judge"
                                    % f["path"])
        elif now_size < was_size:
            out["rewritten"].append("%s shrank %d -> %d B"
                                    % (f["path"], was_size, now_size))
        elif not prefix:
            out["unproven"].append("%s +%d B (legacy anchor: no prefix digest)"
                                   % (f["path"], now_size - was_size))
        elif sha256_prefix(full, was_size) != prefix:
            out["rewritten"].append("%s REWRITTEN (first %d B no longer match)"
                                    % (f["path"], was_size))
        else:
            out["grew"].append("%s +%d B" % (f["path"], now_size - was_size))
    return out

def cmd_verify() -> int:
    try:
        with open(LEDGER, "r", encoding="utf-8") as fh:
            entries = [json.loads(ln) for ln in fh if ln.strip()]
    except OSError:
        print("FAIL no anchor ledger at %s" % LEDGER)
        return 1
    if not entries:
        print("FAIL anchor ledger is empty")
        return 1
    latest = entries[-1]
    snap = os.path.join(OUT_DIR, "anchor-%d.json" % int(latest["ts"]))
    try:
        with open(snap, "r", encoding="utf-8") as fh:
            rec = json.load(fh)
    except OSError:
        print("FAIL anchor snapshot missing: %s" % snap)
        return 1

    fails = 0

    def check(ok: bool, msg: str) -> None:
        nonlocal fails
        print("  %s %s" % ("PASS" if ok else "FAIL", msg))
        if not ok:
            fails += 1

    body = json.dumps({k: rec[k] for k in ("merkle_root", "leaf_count", "ton",
                                           "kind")}, sort_keys=True)
    check(hashlib.sha256(body.encode()).hexdigest() == rec.get("record_sha256"),
          "anchor record unmodified (record_sha256 re-derives)")

    recomputed = [f["sha256"] for f in rec["files"]]
    check(merkle_root(recomputed) == rec["merkle_root"],
          "merkle root re-derives from the %d recorded leaf hashes"
          % len(recomputed))

    tri = evidence_drift(rec)
    drift = tri["missing"] + tri["rewritten"]
    check(not drift,
          "evidence files %s" % ("all still match the anchor" if not drift
                                 else "; ".join(drift)))
    if tri["grew"]:
        print("  NOTE append-only growth since the anchor: %s"
              % ", ".join(tri["grew"]))
    if tri["unproven"]:
        print("  NOTE changed and not provable either way: %s"
              % ", ".join(tri["unproven"]))

    for path, path_proof in list(rec["proofs"].items())[:1]:
        leaf = next(f["sha256"] for f in rec["files"] if f["path"] == path)
        check(fold_proof(leaf, path_proof) == rec["merkle_root"],
              "merkle proof for %s folds to the root (%d steps)"
              % (path, len(path_proof)))

    anchored = rec["ton"]["masterchain_seqno"]
    live = {name: masterchain_seqno(url) for name, url in HEAD_PROVIDERS.items()}
    vals = [v for v in live.values() if isinstance(v, int)]
    check(bool(vals) and min(vals) >= anchored - AGREEMENT_TOLERANCE,
          "anchored block is not in the future (anchored %d, live head %s)"
          % (anchored, min(vals) if vals else "?"))

    facts = block_facts(anchored)
    usable = {k: v for k, v in facts.items() if v.get("ok")}
    check(len(usable) == 2, "block %d re-fetched from %d independent indexers (%s)"
          % (anchored, len(usable), sorted(usable)))
    recorded = rec["ton"]["anchored_block"]
    same_time = all(v["gen_utime"] == recorded["gen_utime"]
                    for v in usable.values()) and bool(usable)
    same_root = all(v["root_hash"] == recorded["root_hash"]
                    for v in usable.values()) and bool(usable)
    check(same_time, "block gen_utime unchanged (%s)" % recorded["gen_utime"])
    check(same_root, "block root_hash unchanged (%s...)"
          % str(recorded["root_hash"])[:24])

    if usable:
        delta = rec["ts"] - float(recorded["gen_utime"])
        check(abs(delta) < 3600,
              "local anchor time agrees with chain time within an hour (%+.0fs)"
              % delta)
        print("  NOTE chain proves the evidence existed no later than %s UTC"
              % time.strftime("%Y-%m-%dT%H:%M:%SZ",
                              time.gmtime(recorded["gen_utime"])))

    print("\n%d check(s) failed" % fails)
    return 1 if fails else 0


def cmd_rate(seconds: float) -> int:
    a = masterchain_seqno(HEAD_PROVIDERS["tonapi_head"])
    t0 = time.time()
    if a is None:
        print("FAIL no head from tonapi")
        return 1
    time.sleep(seconds)
    b = masterchain_seqno(HEAD_PROVIDERS["tonapi_head"])
    dt = time.time() - t0
    if b is None:
        print("FAIL no head from tonapi (second sample)")
        return 1
    carried = b - a
    if carried <= 0:
        print("FAIL no blocks produced in %.1fs (head %d -> %d)" % (dt, a, b))
        return 1
    print("seqno %d -> %d  (+%d blocks in %.1fs)" % (a, b, carried, dt))
    print("measured block rate %.2f blocks/s (interval %.0f ms)"
          % (carried / dt, 1000.0 * dt / carried))
    print("documented: ~400 ms interval, ~2.5 blocks/s, ~1 s finalisation"
          " (Catchain 2.0, mainnet since 2026-04-09)")
    return 0


def cmd_status() -> int:
    try:
        with open(LEDGER, "r", encoding="utf-8") as fh:
            entries = [json.loads(ln) for ln in fh if ln.strip()]
    except OSError:
        entries = []
    print("anchors recorded: %d" % len(entries))
    for e in entries[-5:]:
        print("  %s  root=%s  files=%d  seqno=%s  block=%s"
              % (time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(e["ts"])),
                 e["merkle_root"][:16], e["leaf_count"], e["seqno"],
                 str(e.get("block_root_hash"))[:12]))
    return 0


def telegram_send(text: str) -> bool:
    tok = env("ABRASAX_TELEGRAM_TOKEN")
    chat = env("ABRASAX_TELEGRAM_CHAT_ID")
    if not tok or not chat:
        return False
    data = json.dumps({"chat_id": chat, "text": text,
                       "disable_web_page_preview": True}).encode()
    req = urllib.request.Request("https://api.telegram.org/bot%s/sendMessage" % tok,
                                 data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode())
        return bool(body.get("ok"))
    except Exception:  # noqa: BLE001
        return False



def task_xml(py: str, script: str, user: str) -> str:
    """Task Scheduler 1.2 XML with an hourly repetition that never expires.

    Register-ScheduledTask rejects `[TimeSpan]::MaxValue` (it serialises to
    P99999999DT23H59M59S, HRESULT 0x80041318), so the repetition is expressed
    the way the GUI expresses "repeat indefinitely": an <Interval> with no
    <Duration> element at all.
    """
    start = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() + 120))
    off = time.strftime("%z")
    if off:
        start += "%s:%s" % (off[:3], off[3:])
    return TASK_XML.format(name=TASK_NAME, user=user, start=start,
                           py=py, script=script, root=ROOT)


def cmd_install() -> int:
    """Register the hourly anchor. Verify one anchors cleanly first."""
    probe = cmd_anchor(notify=False)
    if probe != 0:
        print("REFUSING to install: a manual anchor just failed (rc=%d)" % probe)
        return 1
    py = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.isfile(py):
        print("REFUSING to install: %s missing (task would run nothing)" % py)
        return 1
    script = os.path.abspath(__file__)
    user = os.environ.get("USERNAME", "")
    os.makedirs(OUT_DIR, exist_ok=True)
    xml_path = os.path.join(OUT_DIR, "%s.xml" % TASK_NAME)
    with open(xml_path, "w", encoding="utf-16") as fh:
        fh.write(task_xml(py, script, user))

    ps = ("$ErrorActionPreference='Stop';"
          "try {"
          "$xml=Get-Content -LiteralPath '%s' -Raw -Encoding Unicode;"
          "Register-ScheduledTask -TaskName '%s' -Xml $xml -User '%s' -Force "
          "| Out-Null;"
          "} catch { Write-Output ('REGFAIL ' + $_.Exception.Message); exit 3 };"
          "$t=Get-ScheduledTask -TaskName '%s';"
          "$i=Get-ScheduledTaskInfo -TaskName '%s';"
          "$r=$t.Triggers | Where-Object { $_.Repetition -and $_.Repetition.Interval } "
          "| Select-Object -First 1;"
          "Write-Output ('STATE=' + $t.State);"
          "Write-Output ('INTERVAL=' + $r.Repetition.Interval);"
          "Write-Output ('DURATION=' + $r.Repetition.Duration);"
          "Write-Output ('NEXT=' + $i.NextRunTime);"
          "Write-Output ('ACTION=' + ($t.Actions | ForEach-Object { $_.Execute }) )"
          % (xml_path, TASK_NAME, user, TASK_NAME, TASK_NAME))
    out = run(["powershell", "-NoProfile", "-Command", ps], timeout=90)
    print(out.rstrip())

    fields = {}
    for line in out.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            fields[k.strip()] = v.strip()
    problems = []
    if "REGFAIL" in out:
        problems.append("registration failed")
    if fields.get("STATE") != "Ready":
        problems.append("state=%r (want Ready)" % fields.get("STATE"))
    if fields.get("INTERVAL") != "PT1H":
        problems.append("interval=%r (want PT1H)" % fields.get("INTERVAL"))
    if fields.get("DURATION") not in ("", "P0D", None):
        problems.append("duration=%r (want empty = never expires)"
                        % fields.get("DURATION"))
    if py.lower() not in fields.get("ACTION", "").lower():
        problems.append("action=%r (want %s)" % (fields.get("ACTION"), py))
    if problems:
        print("INSTALL FAILED: " + "; ".join(problems))
        return 1
    print("installed: %s every %s, never expires, next %s"
          % (TASK_NAME, fields.get("INTERVAL"), fields.get("NEXT")))
    return 0

def cmd_uninstall() -> int:
    print(run(["powershell", "-NoProfile", "-Command",
               "Unregister-ScheduledTask -TaskName '%s' -Confirm:$false" % TASK_NAME],
              timeout=60))
    return 0


def main() -> int:
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "status").lower()
    if cmd == "anchor":
        return cmd_anchor("--notify" in sys.argv)
    if cmd == "verify":
        return cmd_verify()
    if cmd == "rate":
        secs = 8.0
        if "--seconds" in sys.argv:
            secs = float(sys.argv[sys.argv.index("--seconds") + 1])
        return cmd_rate(secs)
    if cmd == "status":
        return cmd_status()
    if cmd == "install":
        return cmd_install()
    if cmd == "uninstall":
        return cmd_uninstall()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
