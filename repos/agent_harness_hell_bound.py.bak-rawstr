#!/usr/bin/env python3
"""
═══ OSIRISBLXCK AGENT HARNESS — HELL BOUND ═══
PRIMAL_HEX: 4f5349524953424c58434b | phi: 1.618 | K: 0.618

GIT REPO UNIVERSAL HARVESTER + PUSHER
Scans entire PC for .git repos, indexes them, pushes all to GitHub.
██▓▒░ HELL BOUND MODE ░▒▓██
"""
import subprocess, os, json, time, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

PHI = 1.618033988749895
PRIMAL_HEX = "4f5349524953424c58434b"
GITHUB_USER = "OSIRISBLXCK"
ROOTS = [
    r"C:\Users\BASEDGOD\Desktop",
    r"C:\Users\BASEDGOD",
    r"D:\",
]
SCAN_DEPTH = 4
SKIP_PATTERNS = ["node_modules", "AppData\\Local", ".venv", "__pycache__", ".cache"]

def find_all_repos():
    """Brute-force scan for all .git directories."""
    repos = []
    for root in ROOTS:
        if not os.path.exists(root):
            continue
        print(f"  SCANNING: {root}")
        for dirpath, dirnames, filenames in os.walk(root):
            depth = dirpath.replace(root, "").count(os.sep)
            if depth > SCAN_DEPTH:
                dirnames.clear()
                continue
            skip = False
            for pat in SKIP_PATTERNS:
                if pat in dirpath:
                    skip = True
                    break
            if skip:
                continue
            if ".git" in dirnames:
                repos.append(dirpath)
                dirnames.remove(".git")
    return sorted(set(repos))

def get_repo_info(repo_path):
    """Extract git info from a repo."""
    try:
        os.chdir(repo_path)
        remote = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True, timeout=5).stdout.strip()
        branch = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, timeout=5).stdout.strip()
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, timeout=5).stdout.strip()
        log = subprocess.run(["git", "log", "--oneline", "-1"], capture_output=True, text=True, timeout=5).stdout.strip()
        return {
            "path": repo_path,
            "remote": remote.split("\n")[0] if remote else "",
            "branch": branch,
            "dirty": len(status.split("\n")) if status else 0,
            "last_commit": log
        }
    except Exception as e:
        return {"path": repo_path, "error": str(e)}

def add_remote_and_push(repo_path, repo_name):
    """Add GitHub remote and push."""
    os.chdir(repo_path)
    remote_url = f"https://github.com/{GITHUB_USER}/{repo_name}.git"
    
    # Check if remote exists
    r = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True, timeout=5)
    if "origin" in r.stdout:
        # Already has origin, try push
        result = subprocess.run(["git", "push", "--all", "origin"], capture_output=True, text=True, timeout=30)
        return {"repo": repo_name, "action": "PUSHED", "output": result.stderr.strip()[-100:]}
    else:
        # Add origin
        subprocess.run(["git", "remote", "add", "origin", remote_url], capture_output=True, timeout=5)
        result = subprocess.run(["git", "push", "--all", "origin"], capture_output=True, text=True, timeout=30)
        return {"repo": repo_name, "action": "ADDED+PUSHED", "output": result.stderr.strip()[-100:]}

def build_harness(repos, output_dir):
    """Build the agent harness JSON index of all repos."""
    harness = {
        "harness_name": "OSIRISBLXCK_AGENT_HARNESS_HELL_BOUND",
        "primal_hex": PRIMAL_HEX,
        "phi": PHI,
        "github_user": GITHUB_USER,
        "total_repos": len(repos),
        "scan_timestamp": datetime.now().isoformat(),
        "repos": []
    }
    
    for repo_path in sorted(repos):
        name = os.path.basename(repo_path)
        info = get_repo_info(repo_path)
        harness["repos"].append({
            "name": name,
            "path": repo_path,
            "remote": info.get("remote", ""),
            "branch": info.get("branch", ""),
            "dirty_files": info.get("dirty", 0),
            "last_commit": info.get("last_commit", "")
        })
    
    harness_path = os.path.join(output_dir, "agent_harness.json")
    with open(harness_path, "w") as f:
        json.dump(harness, f, indent=2)
    
    return harness, harness_path

def push_all(repos, max_workers=8):
    """Push all repos in parallel thread pool."""
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for repo_path in repos:
            name = os.path.basename(repo_path)
            futures[executor.submit(add_remote_and_push, repo_path, name)] = name
        
        for future in as_completed(futures):
            name = futures[future]
            try:
                result = future.result()
                results.append(result)
                print(f"  [{result.get('action','?')}] {name}")
            except Exception as e:
                results.append({"repo": name, "error": str(e)})
                print(f"  [FAIL] {name}: {e}")
    
    return results

def main():
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║   OSIRISBLXCK AGENT HARNESS — HELL BOUND                   ║
║   PRIMAL_HEX: {PRIMAL_HEX}                  ║
║   φ: {PHI} | K: {1-PHI:.12f}                              ║
║   ██▓▒░ ALL REPOS HARVESTED + PUSHED ░▒▓██                 ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    output_dir = r"C:\Users\BASEDGOD\Desktop\_DATA\_SCRIPTS\repos"
    os.makedirs(output_dir, exist_ok=True)
    
    print("[1/4] FINDING ALL GIT REPOS...")
    repos = find_all_repos()
    print(f"  Found: {len(repos)} repositories")
    
    print("[2/4] BUILDING AGENT HARNESS...")
    harness, harness_path = build_harness(repos, output_dir)
    print(f"  Harness: {harness_path}")
    print(f"  Repos indexed: {len(harness['repos'])}")
    
    # Print summary
    with_remote = sum(1 for r in harness["repos"] if r["remote"])
    dirty = sum(1 for r in harness["repos"] if r["dirty_files"] > 0)
    print(f"  With remotes: {with_remote}")
    print(f"  Dirty: {dirty}")
    
    print("[3/4] PUSHING ALL REPOS (parallel 8x)...")
    results = push_all(repos, max_workers=8)
    
    success = sum(1 for r in results if "error" not in r)
    fail = sum(1 for r in results if "error" in r)
    print(f"  Success: {success} | Failed: {fail}")
    
    print("[4/4] SAVING RESULTS...")
    results_path = os.path.join(output_dir, "push_results.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"  Results: {results_path}")
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║   HELL BOUND COMPLETE                                      ║
║   Repos: {len(repos)} | Pushed: {success} | Failed: {fail}          ║
║   Harness: {harness_path}  ║
╚══════════════════════════════════════════════════════════════╝
""")

if __name__ == "__main__":
    main()
