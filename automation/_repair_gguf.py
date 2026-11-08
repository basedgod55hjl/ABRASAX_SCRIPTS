def repair():
    p = r"C:\ABRASAX\SCRIPTS\automation\gguf_probe.py"
    src = open(p, encoding="utf-8").read()
    bad = ('            if n > 4096:`n                return f"<{n} x type{at} skipped>"`n'
           '            if at == STRING:')
    good = ('            if n > 4096:\n'
            '                return f"<{n} x type{at} skipped>"\n'
            '            if at == STRING:')
    if bad not in src:
        return "anchor not found"
    open(p, "w", encoding="utf-8").write(src.replace(bad, good))
    return "repaired"


print(repair())
