from pathlib import Path

for p in (Path(r"C:\abrasax\SCRIPTS\fix_verify_tick_handover.py"),
          Path(r"C:\abrasax\SCRIPTS\verify_stack_run.py")):
    s = p.read_text(encoding="utf-8")
    n = s.count("unparsable[-n:]")
    if n == 1:
        p.write_text(s.replace("unparsable[-n:]", "unparsable[:n]"), encoding="utf-8", newline="")
        print("fixed", p)
    else:
        print("count", n, p)
