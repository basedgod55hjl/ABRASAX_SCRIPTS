"""Runner: execute one registered ABRASAX tool by name and return its output.

This is the "chain automation on the fly" piece. Because every tool is a plain
process with text output on stdout, tools compose: one tool's output can be parsed
and fed to the next without any framework.

Design constraints that matter for chaining:
  * every call has a HARD timeout -- a wedged tool must not hang a chain
  * stdout and stderr are captured separately, and a non-zero exit is reported as
    data, not raised, so a chain can decide what to do
  * the child gets stdin=DEVNULL and CREATE_NO_WINDOW: measured tonight, both are
    required for tools to run when there is no console
  * cwd is fixed to the repo root so relative paths behave

Usage:
    python mcp_runner.py --list
    python mcp_runner.py --describe check-alive
    python mcp_runner.py check-alive
    python mcp_runner.py audit-source-control --offline
    python mcp_runner.py --chain check-abra-paths,check-doc-index,check-mem-governor
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

ROOT = r"C:\ABRASAX"
MANIFEST = os.path.join(ROOT, "CONFIG", "mcp.abrasax.json")
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _ensure_manifest():
    """Generate the manifest if it is absent.

    CONFIG/ is gitignored, so the manifest is a build artifact, not source. Every
    consumer regenerates it rather than assuming a previous run left it behind.
    """
    if os.path.exists(MANIFEST):
        return
    gen = r"C:\ABRASAX\SCRIPTS\automation\register_mcp_tools.py"
    subprocess.run([sys.executable, "-u", gen], cwd=ROOT,
                   capture_output=True, text=True, timeout=120,
                   stdin=subprocess.DEVNULL,
                   creationflags=CREATE_NO_WINDOW)


def load():
    _ensure_manifest()
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)


def find(m, name):
    for t in m["tools"]:
        if t["name"] == name:
            return t
    return None


def run_one(tool, extra_args=None, timeout=300.0):
    cmd = list(tool["command"]) + list(extra_args or [])
    t0 = time.time()
    try:
        r = subprocess.run(
            cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )
        return {
            "tool": tool["name"],
            "ok": r.returncode == 0,
            "rc": r.returncode,
            "elapsed_s": round(time.time() - t0, 2),
            "stdout": (r.stdout or "")[-4000:],
            "stderr": (r.stderr or "")[-1000:],
        }
    except subprocess.TimeoutExpired:
        return {
            "tool": tool["name"], "ok": False, "rc": None,
            "elapsed_s": round(time.time() - t0, 2),
            "stdout": "", "stderr": f"TIMEOUT after {timeout:.0f}s",
        }
    except OSError as e:
        return {
            "tool": tool["name"], "ok": False, "rc": None,
            "elapsed_s": 0.0, "stdout": "", "stderr": f"{type(e).__name__}: {e}",
        }


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    m = load()

    if args[0] == "--list":
        print(f"{len(m['tools'])} tool(s) in {MANIFEST}")
        for t in m["tools"]:
            print(f"  {t['name']:34s} {t['description'][:66]}")
        return 0

    if args[0] == "--describe":
        if len(args) < 2:
            print("usage: --describe <tool>")
            return 2
        t = find(m, args[1])
        if not t:
            print(f"unknown tool: {args[1]}")
            return 2
        print(json.dumps(t, indent=2))
        return 0

    if args[0] == "--chain":
        if len(args) < 2:
            print("usage: --chain a,b,c")
            return 2
        names = [n.strip() for n in args[1].split(",") if n.strip()]
        results = []
        chain_ok = True
        for n in names:
            t = find(m, n)
            if not t:
                print(f"  {n}: UNKNOWN")
                chain_ok = False
                continue
            print(f"=== {n} ===", flush=True)
            res = run_one(t)
            results.append(res)
            print(f"  ok={res['ok']} rc={res['rc']} {res['elapsed_s']}s")
            tail = [ln for ln in res["stdout"].strip().splitlines() if ln.strip()][-3:]
            for ln in tail:
                print(f"  | {ln[:100]}")
            if not res["ok"]:
                chain_ok = False
        print(f"\nCHAIN: {'PASS' if chain_ok else 'FAIL'} "
              f"({sum(1 for r in results if r['ok'])}/{len(names)} tools ok)")
        return 0 if chain_ok else 1

    # single tool, any remaining args forwarded
    t = find(m, args[0])
    if not t:
        print(f"unknown tool: {args[0]}")
        return 2
    res = run_one(t, args[1:])
    sys.stdout.write(res["stdout"])
    if res["stderr"]:
        sys.stderr.write(res["stderr"])
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
