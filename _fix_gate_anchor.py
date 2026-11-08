from pathlib import Path

p = Path(r"C:\abrasax\SCRIPTS\local_first_routing.py")
s = p.read_text(encoding="utf-8")
old = '''OLD_GATE = \'\'\'        if jev_gate and cfg["policy"].get("jev_gate") and route == "auto":
            if name != order[0] and not _jev_approve(
                    name, f"Primary \'{order[0]}\' unavailable. Errors: {errors[-1:]} "):\'\'\''''
new = '''OLD_GATE = \'\'\'        if jev_gate and cfg["policy"].get("jev_gate") and route == "auto":
            if name != order[0] and not _jev_approve(
                    name, f"Primary \'{order[0]}\' unavailable. Errors: {errors[-1:]}"):\'\'\''''
assert s.count(old) == 1, s.count(old)
p.write_text(s.replace(old, new, 1), encoding="utf-8", newline="")
print("fix script corrected")
