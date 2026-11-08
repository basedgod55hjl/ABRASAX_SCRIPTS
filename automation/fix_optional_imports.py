"""Fix audit_dependencies.py: do not report OPTIONAL imports as missing deps.

It flagged abrasax_jev as a missing dependency. Measured:

    abrasax/selfedit.py:32   from abrasax_jev import yesno   # inside try/except
    abrasax/selfedit.py:34   except Exception: return None

That is a deliberate optional path: if the JEV helper is not installed the function
returns None and the caller degrades. Reporting it as a defect is wrong -- and it is
the seventh time tonight a red result was the checker's fault.

Fix: an import is only a REQUIRED dependency if it appears outside a try/except.
Detect that in the AST by tracking whether the Import node is inside a Try body.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\audit_dependencies.py"
src = open(PATH, encoding="utf-8").read()

if "OPTIONAL" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''def collect_imports(paths):
    found = defaultdict(set)   # module -> set of files
    for base in paths:
        if not os.path.isdir(base):
            continue
        for dp, _dn, fns in os.walk(base):
            for fn in fns:
                if not fn.endswith(".py"):
                    continue
                full = os.path.join(dp, fn)
                try:
                    tree = ast.parse(open(full, encoding="utf-8", errors="replace").read())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for a in node.names:
                            found[a.name.split(".")[0]].add(full)
                    elif isinstance(node, ast.ImportFrom):
                        if node.level == 0 and node.module:
                            found[node.module.split(".")[0]].add(full)
    return found'''

NEW = '''class _OptVisitor(ast.NodeVisitor):
    """Walk a module, recording imports as REQUIRED or OPTIONAL.

    An import inside a `try:` block is optional by construction: the author has
    already decided how to degrade if it is absent. Treating those as missing
    dependencies produced a false defect on abrasax_jev, which selfedit.py imports
    inside try/except and handles returning None.
    """

    def __init__(self):
        self.required = set()
        self.optional = set()
        self._try_depth = 0

    def visit_Try(self, node):
        self._try_depth += 1
        for n in node.body:
            self.visit(n)
        self._try_depth -= 1
        # handlers / orelse / finalbody are not "optional import" territory
        for n in node.handlers + node.orelse + node.finalbody:
            self.visit(n)

    def visit_Import(self, node):
        for a in node.names:
            top = a.name.split(".")[0]
            (self.optional if self._try_depth else self.required).add(top)

    def visit_ImportFrom(self, node):
        if node.level == 0 and node.module:
            top = node.module.split(".")[0]
            (self.optional if self._try_depth else self.required).add(top)


def collect_imports(paths):
    required = defaultdict(set)   # module -> files importing it OUTSIDE try
    optional = defaultdict(set)   # module -> files importing it INSIDE try
    for base in paths:
        if not os.path.isdir(base):
            continue
        for dp, _dn, fns in os.walk(base):
            for fn in fns:
                if not fn.endswith(".py"):
                    continue
                full = os.path.join(dp, fn)
                try:
                    tree = ast.parse(open(full, encoding="utf-8", errors="replace").read())
                except SyntaxError:
                    continue
                v = _OptVisitor()
                v.visit(tree)
                for m in v.required:
                    required[m].add(full)
                for m in v.optional:
                    optional[m].add(full)
    # a module imported both ways is required somewhere -> required
    return required, optional'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: collect_imports")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)

OLD2 = '''imports = collect_imports(CODE_DIRS)
print(f"distinct top-level modules imported: {len(imports)}")'''
NEW2 = '''imports, optional_mods = collect_imports(CODE_DIRS)
print(f"distinct top-level modules imported: {len(imports)}")
print(f"optional (inside try/except)       : {len(optional_mods)}")
for m in sorted(optional_mods):
    if m not in imports:
        print(f"  optional-only: {m}  ({len(optional_mods[m])} file(s))")'''
if OLD2 not in src:
    print("ANCHOR-NOT-FOUND: imports call")
    sys.exit(1)
src = src.replace(OLD2, NEW2, 1)

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: imports inside try/except are recorded as optional")
