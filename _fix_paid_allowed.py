from pathlib import Path

p = Path(r"C:\abrasax\agents\agents_hub\llm_router.py")
s = p.read_text(encoding="utf-8")

old_late = '''    errors: list[str] = []
    paid_allowed = bool(policy.get("paid_fallback", False)) and mode != "local_only"
'''
new_late = '''    errors: list[str] = []
'''
assert s.count(old_late) == 1, s.count(old_late)
s = s.replace(old_late, new_late, 1)

anchor = '''    paid_order = [n for n in order if n not in local_order]
'''
add = '''    paid_order = [n for n in order if n not in local_order]
    # Spending is opt-in twice: the policy must allow it AND the mode must not be
    # local_only. Computed before the chain so the chain cannot be built from an
    # undefined name (the first version raised UnboundLocalError here).
    paid_allowed = bool(policy.get("paid_fallback", False))
'''
assert s.count(anchor) == 1
s = s.replace(anchor, add, 1)

# in the local_first branch the mode check still applies
s = s.replace("""        elif mode == "local_first":
            chain = list(local_order)
            if paid_allowed:""",
              """        elif mode == "local_first":
            chain = list(local_order)
            if paid_allowed and mode != "local_only":""", 1)

p.write_text(s, encoding="utf-8", newline="")
print("router fixed")
