#!/usr/bin/env python
"""ABRASAX service single-ownership audit  (package SERVICE-CLEAN #34).

Answers one question per catalog port: *who owns it, and is that the only
logical owner?*  The Windows venv ``python.exe`` is a shim that re-execs the
base interpreter with the same argv, so one logical process shows up as TWO
OS processes (parent stub -> child that holds the socket).  This tool groups
by normalised command line and folds parent/child stubs, never by PID count.

Checks
  1. every catalog port (abrasax.services.SERVICES) and every listener in
     8000-9999 whose command line mentions abrasax|filetool|routerfail|http.server
  2. >1 logical listener on one port                       -> DUPLICATE (fail)
  3. a catalog service with a second *serving* copy on another port
     (e.g. a hand-started ``http.server`` over UI/abrasax-ui/web on :8091)
                                                            -> DUPLICATE (fail)
  4. a catalog service with a second copy that binds nothing -> ORPHAN (warn)
  5. supervisor AUTOSTART keys vs catalog ids               -> PARITY (fail)
     ``optional: True`` or ``launch: None`` rows are exempt (external apps).

Exit codes
  0  one logical owner per port, AUTOSTART parity OK
  1  warnings only (orphan that binds nothing, unattributed listener)
  2  duplicate ownership, port clash, or AUTOSTART parity gap
  3  probe failed (could not read the process/listener table)

stdlib only.  Run with the project interpreter:
  cd /c/ABRASAX && ./PYTHON/.venv_gui/Scripts/python.exe SCRIPTS/automation/service_audit.py
"""
from __future__ import annotations

import argparse
import ast
import functools
import hashlib
import json
import re
import shlex
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
SERVICES_PY = ROOT / "abrasax" / "services.py"
SUPERVISOR_PY = ROOT / "SCRIPTS" / "automation" / "supervisor.py"
SUPERVISOR_PID = ROOT / "LOGS" / "supervisor.pid"

HOST_RANGE = (8000, 9999)
MATCH_RE = re.compile(r"abrasax|filetool|routerfail|http\.server", re.I)
GENERIC_SCRIPTS = {"server.js", "app.js", "index.js", "main.js", "run.py"}
GENERIC_STEMS = {"program", "index", "server", "main", "app"}

PS_SNAPSHOT = r"""
$ErrorActionPreference = 'SilentlyContinue'
$procs = @{}
Get-CimInstance Win32_Process | ForEach-Object { $procs[[int]$_.ProcessId] = $_ }
$ls = New-Object System.Collections.ArrayList
foreach ($c in (Get-NetTCPConnection -State Listen)) {
    $op = [int]$c.OwningProcess
    $p = $procs[$op]
    $o = [pscustomobject]@{ port = [int]$c.LocalPort; addr = [string]$c.LocalAddress; pid = $op;
                            name = ''; ppid = 0; cmd = '' }
    if ($p) { $o.name = [string]$p.Name; $o.ppid = [int]$p.ParentProcessId; $o.cmd = [string]$p.CommandLine }
    [void]$ls.Add($o)
}
$pr = New-Object System.Collections.ArrayList
foreach ($p in $procs.Values) {
    [void]$pr.Add([pscustomobject]@{ pid = [int]$p.ProcessId; ppid = [int]$p.ParentProcessId;
                                    name = [string]$p.Name; cmd = [string]$p.CommandLine })
}
[pscustomobject]@{ listeners = @($ls.ToArray()); processes = @($pr.ToArray()) } |
    ConvertTo-Json -Depth 4 -Compress
"""


# --------------------------------------------------------------------------- #
# probes
# --------------------------------------------------------------------------- #
def _run(cmd: list[str], timeout: float = 90.0) -> bytes:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    cp = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=flags)
    return cp.stdout or b""


def _ps_json(script: str) -> dict | None:
    exe = "powershell"
    try:
        raw = _run([exe, "-NoProfile", "-NonInteractive", "-Command",
                    "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + script])
    except (OSError, subprocess.SubprocessError):
        return None
    text = raw.decode("utf-8-sig", errors="replace").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


PS_PROCS = r"""
$ErrorActionPreference = 'SilentlyContinue'
$pr = New-Object System.Collections.ArrayList
foreach ($p in (Get-CimInstance Win32_Process)) {
    [void]$pr.Add([pscustomobject]@{ pid = [int]$p.ProcessId; ppid = [int]$p.ParentProcessId;
                                    name = [string]$p.Name; cmd = [string]$p.CommandLine })
}
[pscustomobject]@{ processes = @($pr.ToArray()) } | ConvertTo-Json -Depth 4 -Compress
"""


def _netstat_listeners() -> list[dict]:
    cp = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True,
                        text=True, timeout=30,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    out: list[dict] = []
    for line in cp.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP" or parts[3].upper() != "LISTENING":
            continue
        try:
            port = int(parts[1].rsplit(":", 1)[1])
            pid = int(parts[4])
        except (IndexError, ValueError):
            continue
        out.append({"port": port, "addr": parts[1].rsplit(":", 1)[0], "pid": pid,
                    "name": "", "ppid": 0, "cmd": ""})
    return out


def _procs_from(data: dict | None) -> dict[int, dict]:
    procs: dict[int, dict] = {}
    for row in (data or {}).get("processes") or []:
        try:
            pid = int(row["pid"])
        except (KeyError, TypeError, ValueError):
            continue
        procs[pid] = {"pid": pid, "ppid": row.get("ppid") or 0,
                      "name": (row.get("name") or "").lower(),
                      "cmd": row.get("cmd") or ""}
    return procs


def _netstat_fallback() -> tuple[list[dict], dict[int, dict], str]:
    """Degraded probe: ports + owning PID only, no command lines."""
    return _netstat_listeners(), {}, "degraded (netstat only, no command lines)"


def snapshot(use_ps: bool = False) -> tuple[list[dict], dict[int, dict], str]:
    """(listeners, processes, probe_label).

    Default is `netstat` + CIM: same LISTENING/pid table as
    Get-NetTCPConnection but ~20x faster on this host.  ``--ps`` uses the
    cmdlet, which is the documented cross-check.
    """
    if use_ps:
        data = _ps_json(PS_SNAPSHOT)
        if not data:
            return _netstat_fallback()
        procs = _procs_from(data)
        listeners: list[dict] = []
        for row in data.get("listeners") or []:
            try:
                pid = int(row["pid"])
                port = int(row["port"])
            except (KeyError, TypeError, ValueError):
                continue
            p = procs.get(pid, {})
            listeners.append({"port": port, "addr": str(row.get("addr") or ""), "pid": pid,
                              "name": p.get("name", ""), "ppid": p.get("ppid", 0),
                              "cmd": p.get("cmd", "")})
        return listeners, procs, "Get-NetTCPConnection+CIM"

    procs = _procs_from(_ps_json(PS_PROCS))
    if not procs:
        return _netstat_fallback()
    listeners = _netstat_listeners()
    for L in listeners:
        p = procs.get(L["pid"], {})
        L["name"] = p.get("name", "")
        L["ppid"] = p.get("ppid", 0)
        L["cmd"] = p.get("cmd", "")
    return listeners, procs, "netstat+CIM"


# --------------------------------------------------------------------------- #
# normalisation + grouping
# --------------------------------------------------------------------------- #
@functools.lru_cache(maxsize=16384)
def normalise(cmd: str) -> str:
    """Path-free, case-folded, whitespace-collapsed command line.

    ``"C:\\ABRASAX\\PYTHON\\.venv_gui\\Scripts\\python.exe" -m abrasax gateway --port 9001``
    and the base-interpreter re-exec both become
    ``python -m abrasax gateway --port 9001``.
    """
    if not cmd:
        return ""
    try:
        toks = shlex.split(cmd, posix=False)
    except ValueError:
        toks = cmd.split()
    out: list[str] = []
    for tok in toks:
        t = tok.strip().strip('"').strip("'").replace("\\", "/").rstrip("/")
        if "/" in t:
            t = t.rsplit("/", 1)[-1]
        if t.lower().endswith(".exe"):
            t = t[:-4]
        t = " ".join(t.split()).lower()
        if t:
            out.append(t)
    return " ".join(out)


def logical_owners(pids: list[int], procs: dict[int, dict]) -> tuple[list[int], dict[int, list[int]]]:
    """Fold launcher stubs into their root.

    A Windows venv ``python.exe`` re-execs the base interpreter with identical
    argv, so the *parent* carries the venv path and the *child* holds the
    socket.  Walk up while the parent's normalised command line is identical;
    the topmost pid is the single logical owner.  Returns (roots, {root: [stubs]}).
    """
    roots: list[int] = []
    wrappers: dict[int, list[int]] = {}
    for pid in sorted(set(pids)):
        key = normalise(procs.get(pid, {}).get("cmd", ""))
        cur, chain = pid, []
        for _ in range(8):
            parent = procs.get(cur, {}).get("ppid") or 0
            pcmd = procs.get(parent, {}).get("cmd", "")
            if parent and parent != cur and key and normalise(pcmd) == key:
                chain.append(cur)
                cur = parent
            else:
                break
        roots.append(cur)
        wrappers.setdefault(cur, []).extend(chain)
    return roots, wrappers


def owned_ports(root: int, listeners: list[dict], procs: dict[int, dict]) -> list[int]:
    """Ports held by root or by a stub child that inherited its argv."""
    root_key = normalise(procs.get(root, {}).get("cmd", ""))
    ports = {L["port"] for L in listeners if L["pid"] == root}
    for L in listeners:
        p = procs.get(L["pid"], {})
        if p.get("ppid") == root and root_key and normalise(p.get("cmd", "")) == root_key:
            ports.add(L["port"])
    return sorted(ports)


def ancestor_dirs(pid: int, procs: dict[int, dict], depth: int = 8) -> list[str]:
    """`cd <path>` hints found in the command lines of a process and its ancestors.

    Hand-started services are launched from a bash one-liner such as
    ``cd /c/ABRASAX/UI/abrasax-ui/web && python -m http.server 8091``; the
    shell is the only place the working directory survives on Windows.
    """
    hints: list[str] = []
    seen: set[int] = set()
    cur = pid
    for _ in range(depth):
        if cur in seen:
            break
        seen.add(cur)
        p = procs.get(cur)
        if not p:
            break
        cmd = p.get("cmd") or ""
        for m in re.finditer(r"(?:^|[\s;&|])cd\s+(?:\"([^\"]+)\"|'([^']+)'|([^\s;&|]+))", cmd, re.I):
            raw = next((g for g in m.groups() if g), "")
            if raw:
                hints.append(raw.replace("\\", "/").lower().rstrip("/"))
        cur = p.get("ppid") or 0
    return hints


def dir_evidence(pid: int, svc: dict, procs: dict[int, dict]) -> bool:
    entry = (svc.get("entry") or "").replace("\\", "/")
    if not entry:
        return False
    parent = str(PurePosixPath(entry).parent).lower()
    tail = "/".join(parent.split("/")[-2:])
    if not tail or len(tail) < 4:
        return False
    return any(tail in hint for hint in ancestor_dirs(pid, procs))


# --------------------------------------------------------------------------- #
# catalog + supervisor
# --------------------------------------------------------------------------- #
def load_catalog() -> list[dict]:
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from abrasax.services import SERVICES  # noqa: PLC0415
        return [dict(s) for s in SERVICES]
    except Exception:  # noqa: BLE001 - fall back to a side-effect-free literal parse
        tree = ast.parse(SERVICES_PY.read_text(encoding="utf-8"))
        for node in tree.body:
            target = getattr(node, "target", None) or (node.targets[0] if getattr(node, "targets", None) else None)
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and getattr(target, "id", "") == "SERVICES":
                return [dict(s) for s in ast.literal_eval(node.value)]
        raise SystemExit(f"cannot load SERVICES from {SERVICES_PY}")


def load_autostart() -> list[str]:
    tree = ast.parse(SUPERVISOR_PY.read_text(encoding="utf-8"))
    for node in tree.body:
        target = getattr(node, "target", None) or (node.targets[0] if getattr(node, "targets", None) else None)
        if (isinstance(node, (ast.Assign, ast.AnnAssign)) and getattr(target, "id", "") == "AUTOSTART"
                and isinstance(node.value, ast.Dict)):
            return [k.value for k in node.value.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
    raise SystemExit(f"cannot find AUTOSTART in {SUPERVISOR_PY}")


def identities(svc: dict) -> list[tuple[str, bool]]:
    """(substring, strong) identities for a catalog row, from its launch line."""
    ids: list[tuple[str, bool]] = []
    launch = (svc.get("launch") or "").strip()
    launch = re.split(r"\s{2,}\(", launch)[0]          # drop prose like "(outside tree; ...)"
    if launch:
        m = re.search(r"(?:^|\s)-m\s+(\S+)(?:\s+([A-Za-z_][\w.-]*))?", normalise(launch))
        if m:
            mod = m.group(1)
            nxt = m.group(2) or ""
            if nxt and not nxt.startswith("-"):
                ids.append((f"-m {mod} {nxt}", True))
            else:
                ids.append((f"-m {mod}", mod not in {"http.server"}))
        for tok in normalise(launch).split():
            if tok.endswith((".py", ".js", ".mjs")):
                ids.append((tok, tok.rsplit("/", 1)[-1] not in GENERIC_SCRIPTS))
                break
    ids.append((svc["id"].replace("-", "_"), True))
    entry = (svc.get("entry") or "").replace("\\", "/")
    if entry:
        base = entry.rsplit("/", 1)[-1].lower()
        if base.endswith((".py", ".js", ".mjs", ".dll")):
            ids.append((base, base.rsplit(".", 1)[0] not in GENERIC_STEMS))
    # de-dup, keep order
    out, seen = [], set()
    for item in ids:
        if item[0] and item[0] not in seen:
            seen.add(item[0])
            out.append(item)
    return out


_ENTRY_CACHE: dict[tuple[int, str], bool] = {}


def serves_entry(port: int, svc: dict) -> bool:
    """True when `port` serves byte-identical content to the catalog entry file.

    Gives a cwd-independent identity for generic servers (`python -m http.server`)
    started with Start-Process, where no `cd` hint survives in any command line.
    """
    entry = (svc.get("entry") or "").replace("\\", "/")
    if not entry or svc.get("protocol") != "http" or not port:
        return False
    local = ROOT / entry
    if not local.is_file() or local.suffix.lower() not in {".html", ".htm", ".js", ".mjs"}:
        return False
    key = (port, entry)
    if key in _ENTRY_CACHE:
        return _ENTRY_CACHE[key]
    ok = False
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/{local.name}", timeout=2.0) as r:
            body = r.read(2_000_000)
        ok = hashlib.sha256(body).digest() == hashlib.sha256(local.read_bytes()).digest()
    except Exception:  # noqa: BLE001
        ok = False
    _ENTRY_CACHE[key] = ok
    return ok


def matches(svc: dict, pid: int, procs: dict[int, dict], ports: list[int] | None = None,
            ids: list[tuple[str, bool]] | None = None) -> bool:
    key = normalise(procs.get(pid, {}).get("cmd", ""))
    if not key:
        return False
    for ident, strong in (ids if ids is not None else identities(svc)):
        if ident in key:
            if strong:
                return True
            if dir_evidence(pid, svc, procs):
                return True
            if ports and any(serves_entry(p, svc) for p in ports):
                return True
    return False


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
def fingerprint(host: str, port: int, timeout: float = 2.0) -> str:
    url = f"http://{host}:{port}/"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 - loopback only
            body = r.read(2_000_000)
        return f"{r.status} {len(body)}B sha256:{hashlib.sha256(body).hexdigest()[:12]}"
    except Exception as exc:  # noqa: BLE001
        return f"no-http({exc.__class__.__name__})"


def audit(strict: bool = False, use_ps: bool = False) -> dict:
    listeners, procs, probe = snapshot(use_ps=use_ps)
    catalog = load_catalog()
    autostart = load_autostart()
    try:
        supervisor_pid = int(SUPERVISOR_PID.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        supervisor_pid = 0

    by_port: dict[int, list[dict]] = {}
    for L in listeners:
        by_port.setdefault(L["port"], []).append(L)

    def lineage(root: int, pid_file_pid: int | None = None) -> str:
        if root == 4:
            return "http.sys"
        if pid_file_pid and root == pid_file_pid:
            return "pid-file"
        cur, hops = root, 0
        while cur and hops < 12 and cur in procs:
            if cur == supervisor_pid:
                return "supervised"
            nxt = procs[cur].get("ppid") or 0
            if nxt == supervisor_pid:
                return "supervised"
            if nxt not in procs:
                break
            cur, hops = nxt, hops + 1
        if procs.get(root, {}).get("name", "").startswith("lm studio"):
            return "external"
        return "detached" if root != 4 else "http.sys"

    rows: list[dict] = []
    for svc in catalog:
        port = svc.get("port")
        if not port:
            continue
        ls = by_port.get(port, [])
        if not ls:
            rows.append({"service": svc["id"], "port": port, "owners": [], "status": "DOWN",
                         "stragglers": False, "cmd": "", "pid_file_pid": None})
            continue
        http_sys = all(L["pid"] == 4 for L in ls)
        pid_file_pid = None
        if http_sys and svc.get("pid_file"):
            pf = ROOT / svc["pid_file"]
            try:
                cand = int(pf.read_text(encoding="utf-8").strip())
                if cand in procs and "codec_gateway" in (procs[cand].get("cmd") or "").lower():
                    pid_file_pid = cand
            except (OSError, ValueError):
                pass
        if http_sys:
            roots = [pid_file_pid] if pid_file_pid else [4]
            wraps: dict[int, list[int]] = {}
        else:
            roots, wraps = logical_owners([L["pid"] for L in ls], procs)
        for r in roots:
            rows.append({
                "service": svc["id"], "port": port, "root": r,
                "wrappers": wraps.get(r, []), "lineage": lineage(r, pid_file_pid),
                "cmd": procs.get(r, {}).get("cmd", "") if r in procs else "System (HTTP.sys)",
                "addrs": sorted({L["addr"] for L in ls}),
                "pid_file_pid": pid_file_pid,
                "listeners": len(ls),
            })

    # --- port-level duplicate: >1 logical owner on one audited port ----------
    duplicates: list[dict] = []
    for port, ls in sorted(by_port.items()):
        audited = port in {s.get("port") for s in catalog} or (
            HOST_RANGE[0] <= port <= HOST_RANGE[1]
            and any(MATCH_RE.search(procs.get(L["pid"], {}).get("cmd", "")) for L in ls))
        if not audited:
            continue
        if port in {s.get("port") for s in catalog} and all(L["pid"] == 4 for L in ls):
            continue  # HTTP.sys: one kernel owner for v4+v6
        roots, wraps = logical_owners([L["pid"] for L in ls], procs)
        if len(roots) > 1:
            duplicates.append({
                "kind": "port", "port": port, "service": None,
                "roots": roots,
                "wrappers": {r: wraps.get(r, []) for r in roots},
                "cmds": [procs.get(r, {}).get("cmd", "") for r in roots],
                "kill": f"taskkill /PID {roots[0]} /T /F",
            })

    # --- service-level: a second serving copy on another port ----------------
    catalog_ports = {s.get("port") for s in catalog}
    canonical: set[int] = set()
    for r in rows:
        if r.get("root"):
            canonical.add(r["root"])
            canonical.update(r.get("wrappers") or [])
        if r.get("pid_file_pid"):
            canonical.add(r["pid_file_pid"])

    orphans: list[dict] = []
    for svc in catalog:
        if svc.get("launch") is None:                    # external desktop app
            continue
        ids = identities(svc)
        entry = (svc.get("entry") or "").replace("\\", "/")
        if entry and Path(entry).is_absolute() and not entry.lower().startswith(str(ROOT).lower().replace("\\", "/")):
            continue                                     # outside the tree, session-scoped
        for pid, proc in procs.items():
            if pid <= 4 or pid in canonical:
                continue
            key = normalise(proc.get("cmd", ""))
            parent = proc.get("ppid") or 0
            if parent in procs and normalise(procs.get(parent, {}).get("cmd", "")) == key:
                continue                                  # stub; parent is the logical root
            ports = owned_ports(pid, listeners, procs)
            if not matches(svc, pid, procs, ports, ids):
                continue
            if ports:
                if not any(HOST_RANGE[0] <= q <= HOST_RANGE[1] or q in catalog_ports for q in ports):
                    continue
                duplicates.append({
                    "kind": "alt-port", "service": svc["id"], "port": ports[0],
                    "roots": [pid], "wrappers": {pid: []},
                    "cmds": [proc.get("cmd", "")],
                    "canonical_port": svc.get("port"),
                    "kill": f"taskkill /PID {pid} /T /F",
                })
            else:
                # A copy that binds nothing is only interesting if it can be
                # tied to this service's directory; "server.mjs" alone also
                # matches Codex/editor helpers that are not ours.
                if not dir_evidence(pid, svc, procs):
                    continue
                orphans.append({"service": svc["id"], "pid": pid, "ppid": proc.get("ppid"),
                                "cmd": proc.get("cmd", ""),
                                "kill": f"taskkill /PID {pid} /T /F"})

    # de-dup duplicate entries by (kind, service, port, roots)
    seen, uniq = set(), []
    for d in duplicates:
        sig = (d["kind"], d.get("service"), d["port"], tuple(d["roots"]))
        if sig not in seen:
            seen.add(sig)
            uniq.append(d)
    duplicates = uniq

    # evidence that both copies serve the same thing
    for d in duplicates:
        if d["kind"] == "alt-port":
            d["fingerprints"] = {f":{p}": fingerprint("127.0.0.1", p)
                                 for p in {d["port"], d.get("canonical_port") or d["port"]}}

    # --- control plane: supervisor / ops monitor / build loop must be single ---
    control: list[dict] = []
    for label, token in (("supervisor", "supervisor.py"),
                         ("ops-monitor", "ops_monitor.py"),
                         ("build-loop", "buildloop")):
        pids = [pid for pid in procs
                if pid > 4 and procs[pid].get("name", "").startswith("python")
                and token in normalise(procs[pid].get("cmd", ""))
                and "service_audit" not in normalise(procs[pid].get("cmd", ""))]
        if not pids:
            control.append({"name": label, "roots": [], "pids": [], "ok": False, "down": True})
            continue
        roots, _wraps = logical_owners(pids, procs)
        control.append({"name": label, "roots": sorted(set(roots)), "pids": sorted(pids),
                        "ok": len(set(roots)) == 1, "down": False})

    # --- AUTOSTART parity ---------------------------------------------------
    cat_ids = [s["id"] for s in catalog]
    exempt = {s["id"] for s in catalog if s.get("optional") or s.get("launch") is None}
    missing = [i for i in cat_ids if i not in autostart]
    unexpected = [i for i in autostart if i not in cat_ids]
    dupe_ports = sorted({p for p in catalog_ports if p and [s["port"] for s in catalog].count(p) > 1})
    parity_fail = bool(unexpected or dupe_ports or (missing if strict else [i for i in missing if i not in exempt]))
    parity = {
        "catalog": len(cat_ids), "autostart": len(autostart),
        "missing": missing, "unexpected": unexpected,
        "exempt": [i for i in missing if i in exempt],
        "dupe_catalog_ports": dupe_ports, "ok": not parity_fail, "strict": strict,
    }

    failed = bool(duplicates) or parity_fail or any(not c["ok"] and not c["down"] for c in control)
    warnings = bool(orphans) or probe.startswith("degraded") or any(c["down"] for c in control)
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "probe": probe, "processes": len(procs), "listeners": len(listeners),
        "ports_audited": sorted({r["port"] for r in rows} | {d["port"] for d in duplicates}),
        "rows": rows, "duplicates": duplicates, "orphans": orphans, "parity": parity,
        "control": control,
        "exit": 2 if failed else (1 if warnings else 0),
    }


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #
def render(rep: dict) -> None:
    w = 88
    print(f"ABRASAX SERVICE OWNERSHIP AUDIT  {rep['generated_at']}")
    print(f"probe={rep['probe']}  processes={rep['processes']}  listeners={rep['listeners']}  "
          f"ports_audited={len(rep['ports_audited'])}")
    print()
    print(f"{'PORT':<6}{'ADDR':<13}{'OWNER':<7}{'CHILD':<7}{'LINEAGE':<12}{'SVC':<18}CMD")
    print("-" * w)
    for r in sorted(rep["rows"], key=lambda x: (x["port"], x.get("root") or 0)):
        addrs = r.get("addrs") or ["-"]
        addr_cell = addrs[0] if len(addrs) == 1 else f"{addrs[0]}+{len(addrs) - 1}"
        addr_cell = addr_cell[:12]
        stub = ",".join(str(x) for x in r.get("wrappers") or [])[:6] or "-"
        cmd = normalise(r.get("cmd") or "")[:max(10, w - 63)]
        print(f"{r['port']:<6}{addr_cell:<13}{str(r.get('root') or '-'):<7}{stub:<7}"
              f"{r.get('lineage', '-'):<12}{r['service'][:17]:<18}{cmd}")

    print()
    if rep["duplicates"]:
        print(f"DUPLICATES ({len(rep['duplicates'])})")
        for d in rep["duplicates"]:
            if d["kind"] == "port":
                print(f"  PORT :{d['port']} has {len(d['roots'])} logical owners "
                      f"pid={d['roots']}{d.get('service') or ''}")
            else:
                print(f"  {d['service']}: extra serving copy pid={d['roots']} on "
                      f":{d['port']} (catalog port :{d.get('canonical_port')})")
            for cmd in d.get("cmds") or []:
                if cmd:
                    print(f"    cmd: {cmd[:w - 9]}")
            for k, v in (d.get("fingerprints") or {}).items():
                print(f"    {k} -> {v}")
            print(f"    fix: {d['kill']}")
    else:
        print("DUPLICATES: none")

    if rep["orphans"]:
        print(f"\nORPHANS - duplicate copies that bind nothing ({len(rep['orphans'])})")
        for o in rep["orphans"]:
            print(f"  {o['service']} pid={o['pid']} ppid={o['ppid']}  {o['cmd'][:w - 40]}")
            print(f"    fix: {o['kill']}")

    p = rep["parity"]
    print()
    print("CONTROL PLANE (must be exactly one logical process each)")
    for c in rep.get("control", []):
        if c["down"]:
            print(f"  {c['name']:<12} NOT RUNNING")
        else:
            state = "OK" if c["ok"] else "DUPLICATE"
            print(f"  {c['name']:<12} roots={c['roots']} pids={c['pids']}  {state}")
    print()
    print(f"AUTOSTART PARITY: {'OK' if p['ok'] else 'FAIL'}  catalog={p['catalog']} "
          f"autostart={p['autostart']} missing={len(p['missing'])} "
          f"exempt={len(p['exempt'])} unexpected={len(p['unexpected'])}")
    for i in p["exempt"]:
        svc = next((s for s in load_catalog() if s["id"] == i), {})
        why = "optional=True" if svc.get("optional") else "launch=None (external app)"
        print(f"  exempt {i}: {why}")
    for i in p["missing"]:
        if i not in p["exempt"]:
            print(f"  MISSING AUTOSTART: {i}")
    for i in p["unexpected"]:
        print(f"  AUTOSTART ID NOT IN CATALOG: {i}")
    if p["dupe_catalog_ports"]:
        print(f"  duplicate catalog ports: {p['dupe_catalog_ports']}")

    verdict = {0: "PASS", 1: "PASS with warnings", 2: "FAIL"}[rep["exit"]]
    print(f"\nRESULT: {verdict}  exit {rep['exit']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ABRASAX service single-ownership audit")
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    ap.add_argument("--strict", action="store_true",
                    help="treat optional/external catalog rows as AUTOSTART gaps too")
    ap.add_argument("--ps", action="store_true",
                    help="use Get-NetTCPConnection instead of netstat (slower, cross-check)")
    args = ap.parse_args(argv)
    rep = audit(strict=args.strict, use_ps=args.ps)
    if args.json:
        print(json.dumps(rep, indent=2, default=str))
    else:
        render(rep)
    return rep["exit"]


if __name__ == "__main__":
    sys.exit(main())
