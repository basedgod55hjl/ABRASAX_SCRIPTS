import pathlib

p = pathlib.Path(r"C:\ABRASAX\abrasax\nervous_ui.py")
src = p.read_text(encoding="utf-8")

# The system calls itself ABRASAX in 103 places: the package directory, the
# distribution name in pyproject, the CLI prog, ABRASAX_ALLOW_CONSTANT_OVERRIDE,
# ABRASAX_ADB, ABRASAX_PHONE_URL, every module docstring. ABRAXIS appears only
# in this page - twice - because I typed it that way when rebuilding the header
# and the title. An interface that displays the product's name incorrectly is
# the first thing an operator notices and the last thing they trust.
before = (src.count("ABRAXIS"), src.count("ABRASAX"))

src = src.replace("<title>ABRAXIS \u00b7 Nervous System</title>",
                  "<title>ABRASAX \u00b7 Nervous System</title>", 1)
src = src.replace("<h1>\u25c8 ABRAXIS WORLD MODEL</h1>",
                  "<h1>\u25c8 ABRASAX WORLD MODEL</h1>", 1)

after = (src.count("ABRAXIS"), src.count("ABRASAX"))
p.write_text(src, encoding="utf-8", newline="\n")
print(f"ABRAXIS before={before[0]} after={after[0]}")
print(f"ABRASAX before={before[1]} after={after[1]}")
