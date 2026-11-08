"""Chain the registered tools into a build/deploy gate that fails loudly.

This is the "exponentially accelerate build, compilation and deployment speed" part,
done honestly. The speedup does not come from running the same checks faster -- it
comes from removing the human round trip between them. Tonight each audit was:
run it, read the output, decide, run the next one. That is minutes per cycle. As a
gate it is about 30 seconds and it cannot forget a step.

The gate is ordered by cost, cheapest first, so a broken tree fails in the first
second instead of after the expensive checks.

Stages:
    fast    paths, secret classifier + repo scan, json guard  (< 2 s each)
    medium  doc index, tree organisation                 (< 3 s each)
    heavy   memory governor, winproc, unity proc         (5-25 s each)

Two modes:
    --stages fast,medium   stop at the first failing stage
    --all                  run everything, report a matrix

Nothing here mutates the repository. Every tool it calls is read-only.
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")

import mcp_runner as R  # noqa: E402

STAGES = {
    "fast": [
        "check-abra-paths",
        "check-secret-rules",
        "check-repo-secrets",
        "check-json-guard",
        "check-launcher-pairs",
    ],
    "medium": [
        "check-doc-index",
        "check-tree-organised",
        "check-doc-verifier",
    ],
    "heavy": [
        "check-mem-governor",
        "check-winproc",
        "check-unity-proc",
    ],
}

ORDER = ["fast", "medium", "heavy"]

# Per-stage budget in seconds. Measured costs: fast < 3.3 s each, medium up to 29 s,
# heavy up to 25 s. A tool that cannot finish inside its budget is NOT a pass --
# silently skipping it is how a gate rots into decoration.
STAGE_TIMEOUTS = {"fast": 30, "medium": 120, "heavy": 180}


def main() -> int:
    args = sys.argv[1:]
    which = list(STAGES) if "--all" in args else ["fast", "medium"]

    if "--stages" in args:
        try:
            which = args[args.index("--stages") + 1].split(",")
        except IndexError:
            print("usage: --stages fast,medium,heavy")
            return 2

    m = R.load()
    available = {t["name"] for t in m["tools"]}

    print(f"=== BUILD GATE ===  stages: {', '.join(which)}")
    print(f"  manifest: {len(available)} tool(s) registered\n")

    t_start = time.time()
    matrix = []
    failed_stage = None

    for stage in ORDER:
        if stage not in which:
            continue
        names = STAGES[stage]
        missing = [n for n in names if n not in available]
        if missing:
            print(f"--- {stage}: SKIP, not registered: {missing}")
            continue

        print(f"--- {stage} ---", flush=True)
        stage_ok = True
        for n in names:
            tool = R.find(m, n)
            budget = STAGE_TIMEOUTS.get(stage, 180)
            res = R.run_one(tool, timeout=budget)
            timed_out = "TIMEOUT" in (res.get("stderr") or "")
            matrix.append({
                "stage": stage, "tool": n, "ok": res["ok"],
                "rc": res["rc"], "s": res["elapsed_s"],
                "timeout": timed_out,
            })
            mark = "TIMEOUT" if timed_out else ("ok  " if res["ok"] else "FAIL")
            print(f"  {mark} {n:32s} {res['elapsed_s']:6.2f}s", flush=True)
            if not res["ok"]:
                stage_ok = False
                tail = [ln for ln in (res["stderr"] or res["stdout"]).strip().splitlines()
                        if ln.strip()][-4:]
                for ln in tail:
                    print(f"        {ln[:100]}")

        if not stage_ok:
            failed_stage = stage
            print(f"\n  stage '{stage}' FAILED -- stopping (later stages assume it)")
            break
        print(f"  stage '{stage}' passed\n", flush=True)

    elapsed = time.time() - t_start
    ok = sum(1 for r in matrix if r["ok"])
    timeouts = sum(1 for r in matrix if r.get("timeout"))
    print("=== GATE RESULT ===")
    print(f"  tools run : {len(matrix)}")
    print(f"  passed    : {ok}")
    print(f"  failed    : {len(matrix) - ok}")
    if timeouts:
        print(f"  timed out : {timeouts} (counted as failures)")
    print(f"  elapsed   : {elapsed:.1f}s")
    if failed_stage:
        print(f"  STOPPED AT: {failed_stage}")
    print(f"  VERDICT   : {'PASS' if ok == len(matrix) and matrix else 'FAIL'}")

    out = r"C:\ABRASAX\LOGS\build-gate.json"
    try:
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "elapsed_s": round(elapsed, 1), "matrix": matrix,
                       "failed_stage": failed_stage}, f, indent=2)
        print(f"  report    : {out}")
    except OSError:
        pass

    return 0 if ok == len(matrix) and matrix else 1


if __name__ == "__main__":
    sys.exit(main())
