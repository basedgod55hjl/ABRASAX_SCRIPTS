#!/usr/bin/env python3
"""
cred_self_audit.py — self-service credential & stealer audit (CURRENT USER ONLY)

Purpose: let you inspect YOUR OWN credential store and check this machine for
credential-stealer activity, entirely in your own logon context.

Modes
  --creds    list Windows Credential Manager entries for the current user
  --reveal   with --creds: also read each credential's secret (own context, CredRead)
  --audit    scan for common credential-stealer indicators
  --all      run both
  --json     machine-readable output

Safety / scope
  * READ-ONLY: nothing is written, moved, or deleted.
  * Only the CALLING user's vault is touched (CredEnumerateW / CredRead resolve to
    the current logon session). Other profiles are never enumerated.
  * Secrets are masked unless --reveal is passed explicitly.
  * Uses only the Python standard library + built-in Windows APIs via ctypes.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Windows credential API bindings ────────────────────────────────────
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

CRED_TYPE_GENERIC = 1
CRED_TYPE_DOMAIN_PASSWORD = 2
CRED_TYPE_DOMAIN_CERTIFICATE = 3
CRED_TYPE_DOMAIN_VISIBLE_PASSWORD = 4
CRED_TYPE_GENERIC_CERTIFICATE = 5
CRED_TYPE_DOMAIN_EXTENDED = 6
CRED_TYPE_NAMES = {
    0: "SESSION",
    1: "GENERIC",
    2: "DOMAIN_PASSWORD",
    3: "DOMAIN_CERTIFICATE",
    4: "DOMAIN_VISIBLE_PASSWORD",
    5: "GENERIC_CERTIFICATE",
    6: "DOMAIN_EXTENDED",
}


class CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wt.DWORD),
        ("Type", wt.DWORD),
        ("TargetName", wt.LPWSTR),
        ("Comment", wt.LPWSTR),
        ("LastWritten", wt.FILETIME),
        ("CredentialBlobSize", wt.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
        ("Persist", wt.DWORD),
        ("AttributeCount", wt.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wt.LPWSTR),
        ("UserName", wt.LPWSTR),
    ]


PCREDENTIALW = ctypes.POINTER(CREDENTIALW)
PPCREDENTIALW = ctypes.POINTER(PCREDENTIALW)

# CredEnumerateW's out-param is an ARRAY OF POINTERS (PCREDENTIALW * / PCREDENTIALW**)
advapi32.CredEnumerateW.argtypes = [
    wt.LPCWSTR, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.POINTER(PPCREDENTIALW),
]
advapi32.CredEnumerateW.restype = wt.BOOL

advapi32.CredReadW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.POINTER(PCREDENTIALW)]
advapi32.CredReadW.restype = wt.BOOL

advapi32.CredFree.argtypes = [ctypes.c_void_p]
advapi32.CredFree.restype = None

# DPAPI self-context test
class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


crypt32.CryptProtectData.argtypes = [
    ctypes.POINTER(DATA_BLOB), wt.LPCWSTR, ctypes.POINTER(DATA_BLOB), ctypes.c_void_p,
    ctypes.c_void_p, wt.DWORD, ctypes.POINTER(DATA_BLOB),
]
crypt32.CryptProtectData.restype = wt.BOOL
crypt32.CryptUnprotectData.argtypes = [
    ctypes.POINTER(DATA_BLOB), ctypes.POINTER(wt.LPWSTR), ctypes.POINTER(DATA_BLOB),
    ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(DATA_BLOB),
]
crypt32.CryptUnprotectData.restype = wt.BOOL


# ── Credential Manager (own context) ───────────────────────────────────
def _filetime_to_iso(ft: wt.FILETIME) -> str | None:
    """FILETIME (100ns ticks since 1601) → ISO-8601 UTC, or None if zero/invalid."""
    ts = (ft.dwHighDateTime << 32) | ft.dwLowDateTime
    if not ts:
        return None
    unix = (ts - 116444736000000000) / 1e7
    if unix < 0 or unix > 4102444800:  # sanity: 1970..2100
        return None
    try:
        return datetime.fromtimestamp(unix, tz=timezone.utc).isoformat()
    except (OSError, OverflowError, ValueError):
        return None


def enumerate_credentials() -> list[dict]:
    count = wt.DWORD(0)
    pcreds = PPCREDENTIALW()
    if not advapi32.CredEnumerateW(None, 0, ctypes.byref(count), ctypes.byref(pcreds)):
        err = ctypes.get_last_error()
        if err == 1168:  # ERROR_NOT_FOUND — empty vault
            return []
        raise OSError(f"CredEnumerateW failed: error {err}")
    out: list[dict] = []
    try:
        for i in range(count.value):
            entry = pcreds[i]           # PCREDENTIALW → pointer to one CREDENTIALW
            if not entry:
                continue
            c = entry.contents
            out.append({
                "target": c.TargetName or "",
                "username": c.UserName or "",
                "type": CRED_TYPE_NAMES.get(c.Type, str(c.Type)),
                "persist": c.Persist,
                "last_written": _filetime_to_iso(c.LastWritten),
                "blob_size": c.CredentialBlobSize,
            })
    finally:
        advapi32.CredFree(ctypes.cast(pcreds, ctypes.c_void_p))
    return out


def read_credential_secret(target: str, cred_type: int) -> bytes | None:
    pcred = PCREDENTIALW()
    if not advapi32.CredReadW(target, cred_type, 0, ctypes.byref(pcred)):
        return None
    try:
        c = pcred.contents
        if not c.CredentialBlob or c.CredentialBlobSize == 0:
            return b""
        return ctypes.string_at(c.CredentialBlob, c.CredentialBlobSize)
    finally:
        advapi32.CredFree(ctypes.cast(pcred, ctypes.c_void_p))


def decode_secret(blob: bytes) -> str:
    """Credential blobs are usually UTF-16LE; fall back to UTF-8/latin-1."""
    for enc in ("utf-16-le", "utf-8", "latin-1"):
        try:
            text = blob.decode(enc).rstrip("\x00")
            if text and all(ch.isprintable() or ch in "\t\r\n" for ch in text):
                return text
        except (UnicodeDecodeError, ValueError):
            continue
    return f"<{len(blob)} bytes, non-text>"


def dpapi_self_test() -> dict:
    """Verify DPAPI works in THIS user's context with a round-trip on a throwaway blob."""
    secret = b"abrasax-dpapi-self-test"
    blob_in = DATA_BLOB(len(secret), ctypes.cast(ctypes.c_char_p(secret), ctypes.POINTER(ctypes.c_char)))
    blob_enc = DATA_BLOB()
    if not crypt32.CryptProtectData(
        ctypes.byref(blob_in), "self-test", None, None, None, 0, ctypes.byref(blob_enc)
    ):
        return {"ok": False, "error": f"CryptProtectData failed: {ctypes.get_last_error()}"}
    try:
        blob_out = DATA_BLOB()
        if not crypt32.CryptUnprotectData(
            ctypes.byref(blob_enc), None, None, None, None, 0, ctypes.byref(blob_out)
        ):
            return {"ok": False, "error": f"CryptUnprotectData failed: {ctypes.get_last_error()}"}
        try:
            recovered = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            return {"ok": recovered == secret, "roundtrip_bytes": len(recovered)}
        finally:
            kernel32.LocalFree(blob_out.pbData)
    finally:
        kernel32.LocalFree(blob_enc.pbData)


# ── Stealer-indicator audit ────────────────────────────────────────────
def _run(cmd: list[str], timeout: int = 20) -> str:
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        ).stdout
    except Exception:
        return ""


def audit_registry_autoruns() -> list[dict]:
    import winreg
    findings = []
    keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU Run"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HKCU RunOnce"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM Run"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HKLM RunOnce"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\RunServices", "HKLM RunServices"),
    ]
    for hive, path, label in keys:
        try:
            with winreg.OpenKey(hive, path) as k:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(k, i)
                    except OSError:
                        break
                    findings.append({"where": label, "name": name, "value": value})
                    i += 1
        except FileNotFoundError:
            continue
        except OSError:
            continue
    return findings


def audit_startup_folders() -> list[dict]:
    findings = []
    candidates = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup",
        Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Microsoft/Windows/Start Menu/Programs/Startup",
    ]
    for folder in candidates:
        if not folder.is_dir():
            continue
        for f in folder.iterdir():
            if f.is_file() and f.name.lower() != "desktop.ini":
                findings.append({"where": str(folder), "file": f.name, "size": f.stat().st_size})
    return findings


def audit_browser_login_data() -> list[dict]:
    """Recently-modified browser credential stores are a prime stealer target."""
    findings = []
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    targets = {
        "Edge": local / "Microsoft/Edge/User Data",
        "Chrome": local / "Google/Chrome/User Data",
        "Brave": local / "BraveSoftware/Brave-Browser/User Data",
    }
    for name, base in targets.items():
        if not base.is_dir():
            continue
        for profile in base.iterdir():
            login = profile / "Login Data"
            if login.is_file():
                st = login.stat()
                findings.append({
                    "browser": name,
                    "profile": profile.name,
                    "path": str(login),
                    "size": st.st_size,
                    "modified": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                    "modified_age_hours": round((datetime.now().timestamp() - st.st_mtime) / 3600, 1),
                })
    return findings


def audit_suspicious_processes() -> list[dict]:
    """Flag processes that commonly appear in stealer chains or are unsigned copies."""
    out = _run(["tasklist", "/fo", "csv", "/nh"])
    findings = []
    suspect_names = {
        "curl.exe", "certutil.exe", "bitsadmin.exe", "mshta.exe", "wscript.exe",
        "cscript.exe", "rundll32.exe", "regsvr32.exe", "powershell_ise.exe",
    }
    suspect_path_hints = ("\\temp\\", "\\appdata\\local\\temp\\", "\\downloads\\", "\\public\\")
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) < 2:
            continue
        name = parts[0].strip('"')
        if name.lower() in suspect_names:
            findings.append({"process": name, "pid": parts[1]})
    # Flag any process with an executable path in temp/downloads
    wmi = _run([
        "powershell", "-NoProfile", "-Command",
        "Get-CimInstance Win32_Process | "
        "Select-Object Name,ProcessId,ExecutablePath | ConvertTo-Json -Compress",
    ], timeout=30)
    if wmi:
        try:
            data = json.loads(wmi)
            if isinstance(data, dict):
                data = [data]
            for p in data:
                path = (p.get("ExecutablePath") or "").lower()
                if path and any(h in path for h in suspect_path_hints):
                    findings.append({
                        "process": p.get("Name"),
                        "pid": p.get("ProcessId"),
                        "path": p.get("ExecutablePath"),
                        "reason": "runs from temp/downloads",
                    })
        except json.JSONDecodeError:
            pass
    return findings


def audit_defender() -> dict:
    threats = _run([
        "powershell", "-NoProfile", "-Command",
        "Get-MpThreatDetection -ErrorAction SilentlyContinue | "
        "Select-Object -First 25 ThreatID,InitialDetectionTime,Resources | ConvertTo-Json -Compress",
    ], timeout=40)
    status = _run([
        "powershell", "-NoProfile", "-Command",
        "Get-MpComputerStatus -ErrorAction SilentlyContinue | "
        "Select-Object RealTimeProtectionEnabled,AntivirusEnabled,"
        "AntispywareEnabled,AMServiceEnabled,QuickScanEndTime | ConvertTo-Json -Compress",
    ], timeout=40)
    result = {}
    try:
        result["detections"] = json.loads(threats) if threats.strip() else []
    except json.JSONDecodeError:
        result["detections"] = threats[:400] or "unavailable"
    try:
        result["status"] = json.loads(status) if status.strip() else "unavailable"
    except json.JSONDecodeError:
        result["status"] = status[:400] or "unavailable"
    return result


def audit_scheduled_tasks_recent(days: int = 14) -> list[dict]:
    out = _run([
        "powershell", "-NoProfile", "-Command",
        "Get-ScheduledTask | ForEach-Object { "
        "$i = $_ | Get-ScheduledTaskInfo; "
        "[pscustomobject]@{Name=$_.TaskName;Path=$_.TaskPath;"
        "Author=$_.Author;LastRun=$i.LastRunTime;NextRun=$i.NextRunTime}"
        "} | ConvertTo-Json -Compress",
    ], timeout=40)
    findings = []
    if not out.strip():
        return findings
    try:
        data = json.loads(out)
        if isinstance(data, dict):
            data = [data]
        cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
        for t in data:
            lr = t.get("LastRun") or ""
            if "T" in lr:  # e.g. 2026-10-11T12:00:00
                try:
                    when = datetime.fromisoformat(lr.replace("Z", "+00:00")).timestamp()
                    if when >= cutoff:
                        findings.append({
                            "name": t.get("Name"), "path": t.get("Path"),
                            "author": t.get("Author"), "last_run": lr,
                        })
                except ValueError:
                    continue
    except json.JSONDecodeError:
        pass
    return findings


def run_audit() -> dict:
    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "user": os.environ.get("USERNAME"),
        "computer": os.environ.get("COMPUTERNAME"),
        "dpapi_self_test": dpapi_self_test(),
        "autoruns": audit_registry_autoruns(),
        "startup_folder": audit_startup_folders(),
        "browser_login_data": audit_browser_login_data(),
        "suspect_processes": audit_suspicious_processes(),
        "recent_scheduled_tasks": audit_scheduled_tasks_recent(),
        "defender": audit_defender(),
    }


# ── Reporting ──────────────────────────────────────────────────────────
def print_creds(creds: list[dict], reveal: bool) -> None:
    print("=" * 68)
    print("  WINDOWS CREDENTIAL MANAGER — current user only")
    print("=" * 68)
    if not creds:
        print("  (vault is empty for this user)")
    for i, c in enumerate(creds, 1):
        print(f"\n  [{i}] {c['target']}")
        print(f"      user:   {c['username'] or '—'}")
        print(f"      type:   {c['type']}   persist: {c['persist']}")
        print(f"      size:   {c['blob_size']} bytes")
        if c["last_written"]:
            print(f"      written:{c['last_written']}")
        if reveal:
            blob = read_credential_secret(c["target"], 1) or b""
            if blob:
                print(f"      secret: {decode_secret(blob)}")
            else:
                print("      secret: <no generic blob / use CredUI for this type>")


def print_audit(rep: dict) -> None:
    print("\n" + "=" * 68)
    print("  STEALER-INDICATOR AUDIT (read-only)")
    print("=" * 68)
    print(f"  user: {rep['user']}   host: {rep['computer']}   at {rep['generated']}")

    d = rep["dpapi_self_test"]
    print(f"\n  DPAPI self-test:      {'OK' if d.get('ok') else 'FAILED'}  ({d})")

    print(f"\n  Autoruns ({len(rep['autoruns'])}):")
    for a in rep["autoruns"]:
        print(f"    - [{a['where']}] {a['name']} = {str(a['value'])[:90]}")

    print(f"\n  Startup files ({len(rep['startup_folder'])}):")
    for f in rep["startup_folder"]:
        print(f"    - {f['file']} ({f['size']} bytes)")

    print(f"\n  Browser credential stores ({len(rep['browser_login_data'])}):")
    if not rep["browser_login_data"]:
        print("    - none found")
    for b in rep["browser_login_data"]:
        flag = "  <-- recently touched" if b["modified_age_hours"] < 24 else ""
        print(f"    - {b['browser']}/{b['profile']}: modified {b['modified_age_hours']}h ago{flag}")

    sp = rep["suspect_processes"]
    print(f"\n  Suspect processes ({len(sp)}):")
    if not sp:
        print("    - none of the flagged tools/pathed processes are running")
    for p in sp:
        extra = f"  ({p.get('reason')}: {p.get('path')})" if p.get("path") else ""
        print(f"    - {p['process']} pid={p.get('pid')}{extra}")

    print(f"\n  Recently-run scheduled tasks ({len(rep['recent_scheduled_tasks'])}):")
    for t in rep["recent_scheduled_tasks"][:15]:
        print(f"    - {t['path']}{t['name']}  last_run={t['last_run']}  author={t['author']}")

    df = rep["defender"]
    print("\n  Defender:")
    print(f"    status:     {df.get('status')}")
    det = df.get("detections")
    if isinstance(det, list):
        print(f"    detections: {len(det)}")
        for t in det[:10]:
            print(f"      - {t}")
    else:
        print(f"    detections: {det}")

    print("\n" + "-" * 68)
    print("  Rotate any password that appears in a browser 'Login Data' file")
    print("  modified in the last 24h, and re-run this audit after cleanup.")
    print("-" * 68)


def main() -> int:
    # Windows consoles default to cp1252 — force UTF-8 so box/glyph output can't crash
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="Own-context credential & stealer audit")
    ap.add_argument("--creds", action="store_true", help="list current user's Credential Manager entries")
    ap.add_argument("--reveal", action="store_true", help="with --creds: also show the secret")
    ap.add_argument("--audit", action="store_true", help="scan for stealer indicators")
    ap.add_argument("--all", action="store_true", help="--creds + --audit")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    do_creds = args.creds or args.all
    do_audit = args.audit or args.all
    if not (do_creds or do_audit):
        ap.print_help()
        return 0

    payload: dict = {}
    if do_creds:
        creds = enumerate_credentials()
        payload["credentials"] = creds
        if not args.json:
            print_creds(creds, args.reveal)
    if do_audit:
        rep = run_audit()
        payload["audit"] = rep
        if not args.json:
            print_audit(rep)

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
