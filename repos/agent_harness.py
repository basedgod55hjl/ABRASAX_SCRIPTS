#!/usr/bin/env python3
"""
OSIRISBLXCK AGENT HARNESS — HELL BOUND v1.0
PRIMAL_HEX: 4F5349524953424C58434B | φ: 1.618 | K: 0.618

Harness for all git repositories on this machine.
Push ALL, track ALL, own ALL.
"""
import subprocess, json, os, sys, threading, queue, time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

PHI = 1.618033988749895
PRIMAL_HEX = "4F5349524953424C58434B"
HARNESS_DIR = Path(r"C:\Users\BASEDGOD\Desktop\_DATA\_SCRIPTS\repos")
HARNESS_DIR.mkdir(parents=True, exist_ok=True)

# Repos found from scan
REPOS = [
    # CORE PROJECTS
    r"C:\Users\BASEDGOD\Desktop\ABRASAX",
    r"C:\Users\BASEDGOD\Desktop\ABRASAX\physx_sdk",
    r"C:\Users\BASEDGOD\Desktop\_DATA\_SCRIPTS",
    r"C:\Users\BASEDGOD\Desktop\headroom",
    r"C:\Users\BASEDGOD\Desktop\hermes",
    r"C:\Users\BASEDGOD\Desktop\notebooklm-mcp-cli",
    r"C:\Users\BASEDGOD\OpenJarvis",
    r"C:\Users\BASEDGOD\llama.cpp",
    r"C:\Users\BASEDGOD\jcode",
    r"C:\Users\BASEDGOD\your",
    r"C:\Users\BASEDGOD\ClaudeCode\router",
    r"C:\Users\BASEDGOD\.pi\repo",
    r"C:\Users\BASEDGOD\Data\ofscraper\OF-Scraper-Source",
    r"C:\Windows\System32\Hunyuan3D-2.1",
    r"C:\Windows\System32\paperclip",
    r"C:\rust_cli\unleashed",
    
    # SWARM MERGED
    r"C:\Users\BASEDGOD\Desktop\SWARM_MERGED\ABRASAX",
    r"C:\Users\BASEDGOD\Desktop\SWARM_MERGED\ABRASAX-AI-Engine",
    r"C:\Users\BASEDGOD\Desktop\SWARM_MERGED\ABRASAX-System32-AI",
    r"C:\Users\BASEDGOD\Desktop\SWARM_MERGED\hermes",
    
    # PLINY PROMPTS
    r"C:\Users\BASEDGOD\Desktop\pliny\Anomalous-Outputs",
    r"C:\Users\BASEDGOD\Desktop\pliny\anthropic-quickstarts",
    r"C:\Users\BASEDGOD\Desktop\pliny\AutoStoryGen",
    r"C:\Users\BASEDGOD\Desktop\pliny\AutoTemp",
    r"C:\Users\BASEDGOD\Desktop\pliny\BasiliskToken",
    r"C:\Users\BASEDGOD\Desktop\pliny\CL4R1T4S",
    r"C:\Users\BASEDGOD\Desktop\pliny\CLAUDE-CODE-SYSTEM-PROMPT",
    r"C:\Users\BASEDGOD\Desktop\pliny\Dioscuri",
    r"C:\Users\BASEDGOD\Desktop\pliny\ENTHEA",
    r"C:\Users\BASEDGOD\Desktop\pliny\Eos",
    r"C:\Users\BASEDGOD\Desktop\pliny\G0DM0D3",
    r"C:\Users\BASEDGOD\Desktop\pliny\GLOSSOPETRAE",
    r"C:\Users\BASEDGOD\Desktop\pliny\HyperTune",
    r"C:\Users\BASEDGOD\Desktop\pliny\I-LLM",
    r"C:\Users\BASEDGOD\Desktop\pliny\ImageDefender",
    r"C:\Users\BASEDGOD\Desktop\pliny\L1B3RT4S",
    r"C:\Users\BASEDGOD\Desktop\pliny\LEAKHUB",
    r"C:\Users\BASEDGOD\Desktop\pliny\Misc.-Prompt-Hacks",
    r"C:\Users\BASEDGOD\Desktop\pliny\NATURALIS-FUTURA",
    r"C:\Users\BASEDGOD\Desktop\pliny\OBLITERATUS",
    r"C:\Users\BASEDGOD\Desktop\pliny\ourobopus",
    r"C:\Users\BASEDGOD\Desktop\pliny\P4RS3LT0NGV3",
    r"C:\Users\BASEDGOD\Desktop\pliny\R00TS",
    r"C:\Users\BASEDGOD\Desktop\pliny\ST3GG",
    r"C:\Users\BASEDGOD\Desktop\pliny\V3R1T4S",
    r"C:\Users\BASEDGOD\Desktop\pliny\V3SP3R",
    
    # iPad Liberator
    r"C:\Users\BASEDGOD\ipad_liberator\Cydia",
    r"C:\Users\BASEDGOD\ipad_liberator\ipwndfu",
    r"C:\Users\BASEDGOD\ipad_liberator\ipwndfu_fresh",
    r"C:\Users\BASEDGOD\ipad_liberator\libirecovery",
    r"C:\Users\BASEDGOD\ipad_liberator\palera1n",
    r"C:\Users\BASEDGOD\ipad_liberator\SSHRD_Script",
    
    # ABRASAX subdirs
    r"C:\Users\BASEDGOD\Desktop\ABRASAX\03_SOURCE_PYTHON\core",
    r"C:\Users\BASEDGOD\Desktop\ABRASAX\11_WEB_UI\RuView",
    r"C:\Users\BASEDGOD\Desktop\ABRASAX\15_MISC\ecosystem",
    r"C:\Users\BASEDGOD\Desktop\ABRASAX\15_MISC\OSIRISBLXCK_CORE",
    r"C:\Users\BASEDGOD\Desktop\ABRASAX\ecosystem\ABRASAX-System32-AI",
    r"C:\Users\BASEDGOD\Desktop\ABRASAX\_abrasax_build\ABRASAX-AI-Engine",
    
    # D drive
    r"D:\ORB-TRADER-CSR-SUCK-",
]

def run_cmd(path, cmd):
    try:
        r = subprocess.run(cmd, cwd=path, capture_output=True, text=True, timeout=30, shell=True)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as e:
        return "", str(e), -1

def analyze_repo(path):
    """Get full stats on a repo."""
    if not os.path.isdir(os.path.join(path, ".git")):
        return None
    
    path = Path(path)
    remote, _ , _ = run_cmd(str(path), "git remote -v")
    remotes = {}
    for line in remote.split("\n"):
        if line.strip():
            parts = line.strip().split()
            if len(parts) >= 2:
                remotes[parts[0]] = parts[1]
    
    commit, _, _ = run_cmd(str(path), "git log -1 --format='%H %s'")
    branch, _, _ = run_cmd(str(path), "git branch --show-current")
    status, _, _ = run_cmd(str(path), "git status --porcelain")
    unpushed, _, _ = run_cmd(str(path), "git log @{u}.. --oneline 2>nul")
    
    return {
        "path": str(path),
        "name": path.name,
        "remote": remotes,
        "branch": branch.strip(),
        "last_commit": commit.strip()[:80] if commit.strip() else "NONE",
        "uncommitted": len(status.strip().split("\n")) if status.strip() else 0,
        "unpushed": unpushed.strip() if unpushed.strip() else "CLEAN",
        "has_remote": bool(remotes),
    }

def push_repo(path, force=False):
    """Push a repo to its remote."""
    name = Path(path).name
    # Stage all
    run_cmd(path, "git add -A")
    # Commit if needed
    status, _, _ = run_cmd(path, "git status --porcelain")
    if status.strip():
        msg = f"[HELLBOUND] Auto-commit by OSIRISBLXCK harness — {datetime.now().isoformat()}"
        run_cmd(path, f'git commit -m "{msg}"')
    
    # Check remote
    remote, _, _ = run_cmd(path, "git remote -v")
    if not remote.strip():
        return f"NO_REMOTE|{name}"
    
    # Push
    out, err, rc = run_cmd(path, "git push --all 2>&1")
    if rc == 0:
        return f"PUSHED|{name}"
    else:
        return f"FAILED|{name}|{err[:100]}"

def build_harness_report():
    """Analyze all repos and build master report."""
    print("[HARNESS] Scanning all repositories...")
    results = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(analyze_repo, r): r for r in REPOS}
        for f in as_completed(futures):
            r = f.result()
            if r:
                results.append(r)
                status = "🔗" if r["has_remote"] else "⚫"
                print(f"  {status} {r['name']}: {r['last_commit'][:50]}")
    
    # Save master manifest
    manifest = {
        "harness": "OSIRISBLXCK AGENT HARNESS — HELL BOUND",
        "primal_hex": PRIMAL_HEX,
        "phi": PHI,
        "timestamp": datetime.now().isoformat(),
        "total_repos": len(results),
        "repos_with_remotes": sum(1 for r in results if r["has_remote"]),
        "repos_without_remotes": sum(1 for r in results if not r["has_remote"]),
        "repos": results
    }
    
    manifest_path = HARNESS_DIR / "harness_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\n[HARNESS] Manifest: {manifest_path}")
    print(f"[HARNESS] Total: {len(results)} repos | Remote: {manifest['repos_with_remotes']} | Orphan: {manifest['repos_without_remotes']}")
    return manifest

def push_all():
    """Push ALL repos in parallel."""
    print("\n[HELLBOUND] PUSHING ALL REPOSITORIES...")
    results = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(push_repo, r): r for r in REPOS if os.path.isdir(os.path.join(r,".git"))}
        for f in as_completed(futures):
            r = f.result()
            results.append(r)
            icon = "✅" if "PUSHED" in r else "❌" if "FAILED" in r else "⚫"
            print(f"  {icon} {r}")
    
    pushed = sum(1 for r in results if "PUSHED" in r)
    failed = sum(1 for r in results if "FAILED" in r)
    no_remote = sum(1 for r in results if "NO_REMOTE" in r)
    print(f"\n[HELLBOUND] PUSHED={pushed} FAILED={failed} NO_REMOTE={no_remote}")
    return results

if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║   OSIRISBLXCK AGENT HARNESS — HELL BOUND v1.0               ║
║   PRIMAL_HEX: {PRIMAL_HEX}                          ║
║   φ: {PHI} | K: 0.618 | φ×K: 1.0                           ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--push":
        push_all()
    else:
        build_harness_report()
        print("\n[HARNESS] Run with --push to push all repos")
