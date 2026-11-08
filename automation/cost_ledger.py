"""Count provider usage and publish a spend budget other loops can obey.

Why this exists
---------------
I kept refusing to let unattended automation run against NVIDIA and
Experiential Labs on the grounds that there is no cost telemetry. This is that
telemetry, built from what the system actually records -- and explicit about
what it does NOT record.

What IS measurable (verified against the files):
  * LOGS/usage.jsonl -- one JSON record per LLM call, with `route`, `model`,
    `tokens_per_s`. 59 records present, routes: lmstudio, llamacpp-local.
  * LOGS/build-loop-ledger.jsonl -- one record per cycle, each holding agent
    results with `kind`, `ok`, `agent_id`, `duration_ms`.

What is NOT recorded, and is therefore NOT reported as fact:
  * prompt/completion token counts. Only tokens_per_s exists, which cannot be
    converted to tokens without a duration that is itself not recorded.
  * the provider used for each agent run (build-loop results carry no route).
  * any price table. No currency figure is produced anywhere in this file,
    because inventing one would be fabrication and would make the budget lie.

The budget therefore counts CALLS. That is a coarse unit, but it is measured,
and it is the only unit available that can stop a runaway loop.

Output: DATA/runtime-memory/cost.json
        {"day": "...", "calls_by_route": {...}, "paid_calls_today": N,
         "budget": M, "exhausted": bool, "gaps": [...]}
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(r"C:\ABRASAX")
USAGE = ROOT / "LOGS" / "usage.jsonl"
BUILD_LEDGER = ROOT / "LOGS" / "build-loop-ledger.jsonl"
OUT = ROOT / "DATA" / "runtime-memory" / "cost.json"

# Providers that bill per call. Keep this list conservative: a provider that
# bills and is missing here would be invisible to the budget.
PAID = {"nvidia", "xpl", "experientiallabs"}
FREE = {"llamacpp-local", "lmstudio", "local"}

MAX_PAID_CALLS = int(os.environ.get("ABRASAX_MAX_PAID_CALLS_PER_DAY", "200"))


def _day_of(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d")


def _read_jsonl(path: pathlib.Path) -> list[dict]:
    out = []
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def build() -> dict:
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    usage = _read_jsonl(USAGE)
    ledger = _read_jsonl(BUILD_LEDGER)

    calls_by_route: dict[str, int] = {}
    calls_today = 0
    for rec in usage:
        route = str(rec.get("route") or rec.get("provider") or "unknown")
        if _day_of(float(rec.get("ts") or 0)) == today:
            calls_today += 1
            calls_by_route[route] = calls_by_route.get(route, 0) + 1

    paid_calls_today = sum(n for r, n in calls_by_route.items() if r.lower() in PAID)
    free_calls_today = sum(n for r, n in calls_by_route.items() if r.lower() in FREE)
    unattributed = sum(n for r, n in calls_by_route.items()
                       if r.lower() not in PAID and r.lower() not in FREE)

    agent_runs_today = 0
    for rec in ledger:
        ts = rec.get("ts") or ""
        if not str(ts).startswith(today):
            continue
        for res in (rec.get("results") or []):
            if res.get("kind") == "agent":
                agent_runs_today += 1

    gaps = [
        "token counts are not recorded (only tokens_per_s), so token budgets "
        "cannot be enforced",
        "build-loop agent results carry no route, so agent spend cannot be "
        "attributed per provider",
        "no price table exists, so no currency figure is produced",
    ]

    return {
        "ts": dt.datetime.now(dt.timezone.utc).timestamp(),
        "day": today,
        "calls_by_route": calls_by_route,
        "calls_today": calls_today,
        "paid_calls_today": paid_calls_today,
        "free_calls_today": free_calls_today,
        "unattributed_calls_today": unattributed,
        "agent_runs_today": agent_runs_today,
        "paid_budget": MAX_PAID_CALLS,
        "exhausted": paid_calls_today >= MAX_PAID_CALLS,
        "paid_providers": sorted(PAID),
        "gaps": gaps,
    }


def main() -> int:
    rec = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    if "--json" in sys.argv:
        print(json.dumps(rec, indent=2))
        return 0
    print(f"{rec['day']}  calls={rec['calls_today']} "
          f"(paid {rec['paid_calls_today']}/{rec['paid_budget']}, "
          f"free {rec['free_calls_today']}, unattributed {rec['unattributed_calls_today']})  "
          f"agent_runs={rec['agent_runs_today']}  "
          f"exhausted={rec['exhausted']}")
    for r, n in sorted(rec["calls_by_route"].items(), key=lambda kv: -kv[1]):
        print(f"    {r:<18} {n}")
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
