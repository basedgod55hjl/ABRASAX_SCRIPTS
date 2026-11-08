import io
import ast

p = r"C:\abrasax\tools\abx\stack.py"
s = io.open(p, encoding="utf-8").read()

# 1. The catalog row is the unit of truth; DOWN must cover "bound but its health
#    contract fails" as well as "nothing listening". no-port rows are UNKNOWN.
s = s.replace('    up = down = skipped = 0', '    up = down = skipped = unknown = 0', 1)
s = s.replace('''            row["state"] = "no-port"
            skipped += 1''', '''            row["state"] = "unknown-no-port"
            skipped += 1
            unknown += 1''', 1)
s = s.replace('''    r.add(catalog_source=cat["source"], checked=len(rows), up=up, down=down,
          no_port=skipped, services=rows)''',
'''    # bucket everything so a summary can never disagree with its rows
    buckets: dict[str, list[str]] = {}
    for row in rows:
        buckets.setdefault(str(row.get("state")), []).append(str(row.get("id")))
    r.add(catalog_source=cat["source"], checked=len(rows), up=up, down=down,
          no_port=skipped, unknown=unknown, buckets=buckets, services=rows)
    if up + down != len(rows) - unknown:
        r.fail("internal: up+down does not reconcile with checked-unknown")''', 1)

# 2. Row-level reason so a reader never has to infer it.
s = s.replace('''            row["state"] = "up" if probe.get("ok") else "listening-but-unhealthy"''',
'''            row["state"] = "up" if probe.get("ok") else "down"
            if not probe.get("ok"):
                row["reason"] = f'bound but {hp} returned {probe.get("http") or probe.get("error")}\'''', 1)
s = s.replace('''        if not listening:
            row["state"] = "down"
            down += 1''', '''        if not listening:
            row["state"] = "down"
            row["reason"] = f"nothing listening on {host}:{port}"
            down += 1''', 1)

io.open(p, "w", encoding="utf-8").write(s)
ast.parse(s)
print("stack semantics hardened")
