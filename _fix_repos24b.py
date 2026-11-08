import io
import ast

p = r"C:\abrasax\tools\abx\repos24.py"
s = io.open(p, encoding="utf-8").read()

# ABRASAX-SWARM-AI was dissolved: the engine now lives in ENGINE/abrasax_engine,
# which is also the source for ABRASAX-AI-Engine. Publishing the same tree to
# two repos would fork the truth, so SWARM-AI is honestly marked as absorbed.
old = '''    {"repo": "ABRASAX-SWARM-AI", "branch": "main", "source": "AGENTS/SWARM/ABRASAX-SWARM-AI",
     "kind": "production", "note": "swarm AI engine package"},'''
new = '''    {"repo": "ABRASAX-SWARM-AI", "branch": "main", "source": None,
     "kind": "absorbed",
     "note": "absorbed into ENGINE/abrasax_engine -> published as ABRASAX-AI-Engine; "
             "publishing the same tree twice would fork the truth"},'''
assert old in s
s = s.replace(old, new, 1)

# accept the new kind in the plan contract
s = s.replace('assert row["kind"] in ("production", "shell", "data", "heritage", "source", "index", "fork")',
              'assert row["kind"] in ("production", "shell", "data", "heritage", "source", "index", "fork", "absorbed")')
io.open(p, "w", encoding="utf-8").write(s)
ast.parse(s)

t = r"C:\abrasax\tests\test_abx_repos24.py"
s = io.open(t, encoding="utf-8").read()
s = s.replace('assert row["kind"] in ("production", "shell", "data", "heritage", "source", "index", "fork"), row',
              'assert row["kind"] in ("production", "shell", "data", "heritage", "source", "index", "fork", "absorbed"), row')
s = s.replace('''def test_heritage_repo_is_never_a_publish_target():''',
'''def test_absorbed_rows_have_no_source():
    for row in repos24.ROWS:
        if row["kind"] == "absorbed":
            assert row["source"] is None, row
            assert "absorbed" in row["note"], row


def test_no_two_rows_publish_the_same_source():
    seen = {}
    for row in repos24.ROWS:
        if row.get("source"):
            assert row["source"] not in seen, f"{row['repo']} duplicates {seen[row['source']]}"
            seen[row["source"]] = row["repo"]


def test_heritage_repo_is_never_a_publish_target():''')
io.open(t, "w", encoding="utf-8").write(s)
ast.parse(s)
print("SWARM-AI marked absorbed; plan uniqueness test added")
