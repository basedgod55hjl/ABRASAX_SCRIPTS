import io
import ast

p = r"C:\abrasax\.gitignore"
s = io.open(p, encoding="utf-8").read()
anchor = "# ---- runtime state is generated, never published ----\nLOGS/\n"
assert anchor in s
add = anchor + """
# ---- release artifacts (built by `python -m build`, never committed) ----
# These are reproducible from pyproject.toml; keeping binaries out of the
# production line is what makes the line buildable from a clone.
/dist/
*.whl
*.tar.gz
"""
if "/dist/" not in s:
    s = s.replace(anchor, add, 1)
io.open(p, "w", encoding="utf-8").write(s)

# the sdist must build without a README for LOGS/abx files
print("gitignore: dist/ and archives now excluded")
