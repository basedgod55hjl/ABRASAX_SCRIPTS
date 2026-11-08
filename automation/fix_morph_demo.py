"""Remove the deliberate bad kernel lookup from morph_demo.cpp.

The file contained:

    CU_CHECK(cuModuleGetFunction(&fBlend,  mod, "fb_blend_unused_check_absent")
             == CUDA_SUCCESS ? CUDA_SUCCESS : CUDA_SUCCESS);
    // the name above is intentionally wrong; fetch the real one and report
    CUresult rb = cuModuleGetFunction(&fBlend, mod, "fb_morph_blend");

That first call passes a nonsense symbol name and would abort with CUDA_ERROR_NOT_FOUND
before the real lookup runs. It was a leftover from drafting; delete it and keep only
the correct fetch.
"""
import re

PATH = r"C:\ABRASAX\ENGINE\floating_brain\cuda\src\morph_demo.cpp"
src = open(PATH, encoding="utf-8").read()

if "fb_blend_unused_check_absent" not in src:
    print("ALREADY-CLEAN")
    raise SystemExit(0)

# delete the whole bogus statement, which may span lines
pattern = re.compile(
    r'\s*CU_CHECK\(cuModuleGetFunction\(&fBlend,\s*mod,\s*'
    r'"fb_blend_unused_check_absent"\).*?;\s*\n',
    re.S)
src, n = pattern.subn("\n", src, count=1)

# and the stale comment
src = src.replace(
    "    // the name above is intentionally wrong; fetch the real one and report\n",
    "")

open(PATH, "w", encoding="utf-8", newline="").write(src)
print(f"removed {n} bad statement(s)")
print("still contains the bad name:", "fb_blend_unused_check_absent" in src)
for i, line in enumerate(open(PATH, encoding="utf-8").read().splitlines(), 1):
    if "fBlend" in line and "cuModuleGetFunction" in line:
        print(f"  line {i}: {line.strip()}")
