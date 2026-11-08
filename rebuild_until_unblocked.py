"""rebuild_until_unblocked.py — probe until GitHub lifts the creation block,
then finish the rebuild immediately.

A secondary rate limit on content creation answers 403 while the rest of the API
is healthy. Burning eight in-process retries per repo wastes half an hour per
repo and makes the block worse; probing once every few minutes with a single
request is both cheaper and more responsive — the moment a create succeeds, the
whole remaining set is created and published in one paced pass.

    python SCRIPTS/rebuild_until_unblocked.py            # probe every 180 s
    python SCRIPTS/rebuild_until_unblocked.py --probe 120 --deadline 7200
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "SCRIPTS"))

from tools.abx import repo  # noqa: E402

PENDING = [
    "ABRASAX-UI", "ABRASAX-core", "ABRASAX-core-v2", "ABRASAX-ecosystem",
    "ABRASAX-ecosystem-v2", "ABRASAX_DATA", "ABRASAX_SCRIPTS", "ALL_REPOS",
    "OSIRISBLXCK-CORE", "OSIRISBLXCK-CORE-v2",
]

# private flag + description come from the pre-delete snapshot; keep the probe
# harmless (it creates the real repo or nothing at all)
PROBE_REPO = "ABRASAX-UI"


def pending_now() -> list[str]:
    listing = repo.remote_repos()
    live = listing.get("repos", {}) if listing["ok"] else {}
    return [n for n in PENDING if n not in live]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", type=float, default=180.0)
    ap.add_argument("--deadline", type=float, default=7200.0)
    args = ap.parse_args(argv)

    t0 = time.time()
    log = ROOT / "LOGS" / "rebuild_unblock.jsonl"

    while time.time() - t0 < args.deadline:
        missing = pending_now()
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        print(f"{now} pending={len(missing)} {missing}", flush=True)
        log.write_text("", encoding="utf-8") if False else None
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": now, "pending": missing}) + "\n")
        if not missing:
            print("ALL PRESENT", flush=True)
            return 0

        # one cheap write to see whether creation is allowed again
        probe = repo.create(PROBE_REPO, private=False, description="ImGui dashboard, web UI, desktop interfaces")
        if probe.ok:
            print(f"{now} creation allowed again - running the rebuild", flush=True)
            import rebuild_repos
            rc = rebuild_repos.main(["--repos", ",".join(missing), "--skip-delete", "--go", "--pace", "45"])
            print(f"rebuild exit={rc}", flush=True)
            still = pending_now()
            if not still:
                print("ALL PRESENT", flush=True)
                return 0
            print(f"still pending after rebuild: {still}", flush=True)
        else:
            err = str(probe.data.get("error"))[:100]
            print(f"{now} still blocked: {err}", flush=True)
        time.sleep(args.probe)

    print("DEADLINE REACHED", flush=True)
    print(json.dumps({"pending": pending_now()}), flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
