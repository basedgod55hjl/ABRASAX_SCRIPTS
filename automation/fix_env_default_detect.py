"""Fix audit_config_secrets.py: `os.environ.get("X") or DEFAULT` has a default too.

Section D reported 5 env vars as "read with no definition and no default":

    ABRASAX_GATEWAY_PORT   SCRIPTS/automation/bench_models.py
    ABRASAX_GATEWAY_URL    SCRIPTS/automation/bench_models.py
    ABRASAX_MEMORY_DB      abrasax/memory.py:304
    ABRASAX_MEMORY_DOC     abrasax/memory.py:312
    ABRASAX_MEMORY_SEEDS   abrasax/memory.py:308

Measured reality:

    return Path(os.environ.get("ABRASAX_MEMORY_DB") or DEFAULT_DB)

The `or DEFAULT_DB` is a default. My detector only knew the two-argument form
`environ.get("X", default)` and missed the `or` idiom entirely.

Eleventh false red tonight. Two forms to accept:
    os.environ.get("X", default_expression)
    os.environ.get("X") or default_expression
    os.getenv("X") or default_expression
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\audit_config_secrets.py"
src = open(PATH, encoding="utf-8").read()

if "OR_DEFAULT" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''            for m in re.finditer(r"""environ\\.get\\s*\\(\\s*["'](\\w+)["']\\s*,\\s*[^)]+\\)""", text):
                UNDEFINED_OK.add(m.group(1))'''

NEW = '''            # Two default idioms exist in this codebase. Missing the second one
            # produced five false defects.
            #   os.environ.get("X", default)      <- keyword form
            for m in re.finditer(r"""environ\\.get\\s*\\(\\s*["'](\\w+)["']\\s*,\\s*[^)]+\\)""", text):
                UNDEFINED_OK.add(m.group(1))
            #   os.environ.get("X") or default    <- boolean-or form
            OR_DEFAULT = re.finditer(
                r"""environ\\.get\\s*\\(\\s*["'](\\w+)["']\\s*\\)\\s*or\\s+[^\\n#]+""", text)
            for m in OR_DEFAULT:
                UNDEFINED_OK.add(m.group(1))
            #   os.getenv("X") or default
            for m in re.finditer(
                    r"""getenv\\s*\\(\\s*["'](\\w+)["']\\s*\\)\\s*or\\s+[^\\n#]+""", text):
                UNDEFINED_OK.add(m.group(1))'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: default detection")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: `or DEFAULT` idiom now counted as a default")
