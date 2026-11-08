import io
import ast

# 1. team._investigate: state the threat model the evidence is judged against,
#    and label the model's role as NARRATOR (the evidence is already on disk).
p = r"C:\abrasax\tools\abx\team.py"
s = io.open(p, encoding="utf-8").read()

old = '''    prompt = (
        f"ROLE: {spec['agent']} — {spec['role']}\\n"
        f"EVIDENCE (verbatim tool output, JSON):\\n{str(compact)[:6000]}\\n\\n"
        "Write the finding in <=120 words. Every sentence must cite a number, id, port or SHA "
        "that appears in the evidence. If the evidence does not prove something, say what is missing."
    )'''
new = '''    prompt = (
        f"ROLE: {spec['agent']} — {spec['role']}\\n"
        f"THREAT MODEL: this host is the operator's own build box; .env is the intended "
        f"credential store and is strictly git-ignored/untracked, so it cannot be published. "
        f"Vendored test certificates inside third-party source (site-packages, src/vlc-3.0.24) "
        f"are fixtures, not leaks. Only a TRACKED secret-shaped file is an incident.\\n"
        f"EVIDENCE (verbatim tool output, JSON):\\n{str(compact)[:6000]}\\n\\n"
        "You are the NARRATOR, not the investigator. The evidence above is already recorded on "
        "disk. Write the finding in <=120 words. Every sentence must cite a number, id, port or "
        "SHA that appears in the evidence. Do not restate these instructions. Do not explain "
        "your reasoning. If the evidence does not prove something, say what is missing."
    )'''
assert old in s
s = s.replace(old, new, 1)
io.open(p, "w", encoding="utf-8").write(s)
ast.parse(s)

# 2. toolcore.Result must carry its failures in stdout, not only via the exit code.
p2 = r"C:\abrasax\tools\abx\toolcore.py"
s2 = io.open(p2, encoding="utf-8").read()
old2 = '''def emit(result: Result) -> int:
    """Print the envelope as JSON and return the process exit code."""
    json.dump(result.to_dict(), sys.stdout, indent=2, default=str)
    sys.stdout.write("\\n")
    return 0 if result.ok else 1'''
new2 = '''def emit(result: Result) -> int:
    """Print the envelope as JSON and return the process exit code."""
    json.dump(result.to_dict(), sys.stdout, indent=2, default=str)
    sys.stdout.write("\\n")
    if not result.ok:
        # a non-zero exit with empty stderr is indistinguishable from a crash
        for err in result.errors or ["tool reported ok=false"]:
            sys.stderr.write(f"[{result.tool}] {err}\\n")
    return 0 if result.ok else 1'''
assert old2 in s2
s2 = s2.replace(old2, new2, 1)
io.open(p2, "w", encoding="utf-8").write(s2)
ast.parse(s2)
print("narrator prompt scoped; emit now explains failures on stderr")
