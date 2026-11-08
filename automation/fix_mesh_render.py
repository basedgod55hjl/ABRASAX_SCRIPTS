import io, os, shutil

P = r"C:\ABRASAX\abrasax\mesh_log.py"
src = io.open(P, encoding="utf-8").read()

OLD = '''    rowsm = []
    for name, e in sorted(latest.items()):
        if e["kind"] != "probe":
            continue
        got = e.get("content") or "-"
        rowsm.append("| %s | %s | %s | %s | %s | %s |" % (
            name, e.get("status"), e.get("latency_ms"), e.get("verdict"),
            (e.get("served_model") or "-")[:38], got[:38].replace("|", "/")))
'''

NEW = '''    rowsm = []
    for name, e in sorted(latest.items()):
        if e["kind"] != "probe":
            continue
        # An oracle (JEV /systemone) answers with probabilities, not chat
        # content, so "no content" must not make it look broken.
        got = e.get("content") or e.get("detail") or "-"
        if got == "-" and e.get("ok"):
            got = "(ok, no chat content)"
        rowsm.append("| %s | %s | %s | %s | %s | %s |" % (
            name, e.get("status"), e.get("latency_ms"), e.get("verdict"),
            (e.get("served_model") or "-")[:38], got[:38].replace("|", "/")))
'''

if OLD not in src:
    raise SystemExit("ANCHOR NOT FOUND")
src = src.replace(OLD, NEW, 1)

# record a human-readable detail alongside json probes
OLD2 = '''        else:
            ok = True
'''
NEW2 = '''        else:
            ok = True
            if isinstance(body, dict):
                if "answers" in body:
                    parts = []
                    for qid, a in list(body["answers"].items())[:4]:
                        if a.get("type") == "noul":
                            parts.append("%s=%.2f" % (qid, a.get("noul", 0)))
                        elif a.get("type") == "choice":
                            parts.append("%s=%s" % (qid, a.get("choice")))
                        elif a.get("type") == "score":
                            parts.append("%s=%.2f" % (qid, a.get("score", 0)))
                    body_detail = "model=%s %s" % (body.get("model"), " ".join(parts))
                elif "login" in body:
                    body_detail = "login=%s" % body["login"]
                else:
                    body_detail = "json ok"
            else:
                body_detail = "ok"
'''
if OLD2 not in src:
    raise SystemExit("ANCHOR2 NOT FOUND")
src = src.replace(OLD2, NEW2, 1)

src = src.replace(
    '''    served = None
    content = None
    ok = False''',
    '''    served = None
    content = None
    body_detail = None
    ok = False''', 1)

src = src.replace(
    '''                  content=(content or "")[:120] if content else None,
                  error=err)''',
    '''                  content=(content or "")[:120] if content else None,
                  detail=(body_detail or "")[:160] or None,
                  error=err)''', 1)

bak = P + ".bak-render"
if not os.path.exists(bak):
    shutil.copy2(P, bak)
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("patched", P)
