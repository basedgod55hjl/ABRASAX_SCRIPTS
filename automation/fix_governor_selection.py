"""Fix the governor's selection: reclaim memory, not a process count.

The dry run exposed a flaw in my own caps:

    would reclaim 12 process(es), 1200 MB
        19244  363 MB  dotnet.exe
        34396  260 MB  dotnet.exe
        34684  250 MB  dotnet.exe
        18256  248 MB  dotnet.exe
        32628   79 MB  powershell.exe
        31880    0 MB  conhost.exe     <-- wastes a slot
        32792    0 MB  bash.exe        <-- wastes a slot
        ... six more at 0 MB

The cap was MAX_RECLAIM_PROCESSES=12, so eight zero-megabyte husks consumed the
remaining slots while 464 MB of real memory (vlc 179 MB, du.exe, grep, adb) was
left behind. Counting processes instead of bytes makes the cap actively harmful:
it looks thrifty while doing the opposite.

Fix: drop zero-MB entries from the plan entirely (killing a 0 MB husk frees
nothing and only risks collateral damage), and rank strictly by bytes so the cap
is always spent on the largest reclaimable blocks.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\mem_governor.py"
src = open(PATH, encoding="utf-8").read()

if "MIN_RECLAIM_MB" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

# 1. a floor: do not touch processes that are not actually holding memory
OLD_CONST = "MAX_RECLAIM_MB = 1200"
NEW_CONST = '''MAX_RECLAIM_MB = 1200
# A process using 0 MB frees nothing when killed and can only cause collateral
# damage. Observed: eight 0 MB husks consumed the process cap while 464 MB of real
# memory was skipped.
MIN_RECLAIM_MB = 5'''
if OLD_CONST not in src:
    print("ANCHOR-NOT-FOUND: MAX_RECLAIM_MB")
    sys.exit(1)
src = src.replace(OLD_CONST, NEW_CONST, 1)

# 2. filter below the floor, and rank purely by bytes
OLD_FILTER = '''    kept, dropped_mb, dropped_n = [], 0, 0
    for v in victims:'''
NEW_FILTER = '''    # below the floor: not worth a kill
    tiny = [v for v in victims if v["mb"] < MIN_RECLAIM_MB]
    victims = [v for v in victims if v["mb"] >= MIN_RECLAIM_MB]
    if tiny:
        print(f"  ({len(tiny)} process(es) under {MIN_RECLAIM_MB} MB ignored -- "
              f"killing them frees nothing)", flush=True)

    # largest first: the cap must be spent on bytes, not on count
    victims.sort(key=lambda d: -d["mb"])

    kept, dropped_mb, dropped_n = [], 0, 0
    for v in victims:'''
if OLD_FILTER not in src:
    print("ANCHOR-NOT-FOUND: cap loop")
    sys.exit(1)
src = src.replace(OLD_FILTER, NEW_FILTER, 1)

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: MIN_RECLAIM_MB floor + byte-ranked selection")
