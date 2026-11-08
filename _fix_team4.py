import io
import ast

p = r"C:\abrasax\tools\abx\team.py"
s = io.open(p, encoding="utf-8").read()

anchor = "from . import seat as _seat  # noqa: F401,E402  registers abx.seat\n"
add = (anchor
       + "from . import repos24 as _repos24  # noqa: F401,E402  registers abx.repos24*\n"
       + "from . import release as _release  # noqa: F401,E402  registers abx.release\n")
assert anchor in s and "from . import repos24" not in s
s = s.replace(anchor, add, 1)

# new members that use the production-line tools
old_members_end = '''    "security-sentinel": {'''
new_members = '''    "release-engineer": {
        "agent": "test-engineer",
        "role": "Prove the tree is installable: build sdist+wheel and import from a scratch target.",
        "tools": ["abx.release", "abx.test"],
        "capabilities": ["release", "package", "build"],
    },
    "publish-manager": {
        "agent": "tool-distributor",
        "role": "Report the 24-repo production plan row by row against live GitHub.",
        "tools": ["abx.repos24", "abx.repo.audit"],
        "capabilities": ["repo", "plan", "github"],
    },
    "security-sentinel": {'''
assert old_members_end in s
s = s.replace(old_members_end, new_members, 1)

# investigation plans for the new members
old_inv = '''    if member in ("code-reviewer", "security-sentinel"):'''
new_inv = '''    if member == "release-engineer":
        return {"abx.release": TOOLS["abx.release"]["fn"]().to_dict()}
    if member == "publish-manager":
        return {"abx.repos24": TOOLS["abx.repos24"]["fn"]().to_dict()}
    if member in ("code-reviewer", "security-sentinel"):'''
assert old_inv in s
s = s.replace(old_inv, new_inv, 1)

io.open(p, "w", encoding="utf-8").write(s)
ast.parse(s)
print("release-engineer + publish-manager wired")
