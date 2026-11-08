import pathlib
import re

p = pathlib.Path(r"C:\ABRASAX\abrasax\nervous_ui.py")
src = p.read_text(encoding="utf-8")

# The <title> contains a middle dot (U+00B7) that the previous literal replace
# missed, so only the <h1> was corrected. Fix every remaining ABRAXIS with a
# regex, which is encoding-agnostic.
before = len(re.findall(r"ABRAXIS", src))
src = re.sub(r"ABRAXIS", "ABRASAX", src)
after = len(re.findall(r"ABRAXIS", src))

p.write_text(src, encoding="utf-8", newline="\n")
print(f"replaced {before - after} occurrence(s); remaining={after}")

# prove the page now names the system the way the system names itself
page = p.read_text(encoding="utf-8")
print(f"  ABRASAX occurrences in the module: {len(re.findall('ABRASAX', page))}")
for m in re.finditer(r"<title>([^<]+)</title>|<h1>([^<]+)</h1>", page):
    print("  ", (m.group(1) or m.group(2)))
