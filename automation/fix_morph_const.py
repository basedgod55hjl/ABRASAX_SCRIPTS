"""Fix const-qualifier errors in the morph_demo kernel argument arrays.

MSVC: "cannot convert from 'const int *' to 'void *'" at three cuLaunchKernel sites.

cuLaunchKernel takes `void** kernelParams`, and a `const int*` (e.g. `&n` where n is
declared const, or a string literal address) cannot convert to void*. The fix is to
pass addresses of non-const locals.

Affected lines pass &n, &fw, &field, &max_emit, &ball -- some of those are const.
This rewrites them to use mutable copies so the addresses are `int*` / `float*`.
"""
import re

PATH = r"C:\ABRASAX\ENGINE\floating_brain\cuda\src\morph_demo.cpp"
src = open(PATH, encoding="utf-8").read()

if "karg_n" in src:
    print("ALREADY-PATCHED")
    raise SystemExit(0)

# insert mutable copies right after the const declarations
anchor = "    const int n = DEMO_NODES;\n    const int field = DEMO_FIELD_W * DEMO_FIELD_H;\n"
if anchor not in src:
    print("ANCHOR-NOT-FOUND: const n/field")
    raise SystemExit(1)

mutable = anchor + (
    "\n    // cuLaunchKernel wants void**; addresses of const ints cannot convert.\n"
    "    int karg_n = n;\n"
    "    int karg_field = field;\n"
    "    int karg_fw = DEMO_FIELD_W;\n"
    "    int karg_max_emit = 256;\n"
    "    float karg_ball = 0.9f;\n"
    "    float karg_clock = 0.0f;\n"
    "    float karg_t = 0.0f;\n"
    "    int karg_mode = 0;\n"
)
src = src.replace(anchor, mutable, 1)

# now replace the addresses used in the launch arrays
src = src.replace("&n, &fw, &clock0 }", "&karg_n, &karg_fw, &karg_clock }")
src = src.replace("&n, &fw, &clock0 }", "&karg_n, &karg_fw, &karg_clock }")
src = src.replace("&d_frame_a, &d_frame_b, &d_blend, &field, &t }",
                  "&d_frame_a, &d_frame_b, &d_blend, &karg_field, &karg_t }")
src = src.replace("&d_xyz_in, &d_radius, &d_xyz_out, &n, &mode, &t, &clock0 }",
                  "&d_xyz_in, &d_radius, &d_xyz_out, &karg_n, &karg_mode, &karg_t, &karg_clock }")
src = src.replace(
    "&d_charge, &d_conf, &d_emit_pos, &d_emit_str, &d_emit_count,\n"
    "                      &fw, &fw, &max_emit, &ball }",
    "&d_charge, &d_conf, &d_emit_pos, &d_emit_str, &d_emit_count,\n"
    "                      &karg_fw, &karg_fw, &karg_max_emit, &karg_ball }")

# the lambdas capture t and mode by value; assign into the mutable copies
src = src.replace(
    "    auto blend_at = [&](float t) {\n"
    "        int fblock = 256, fgrid = (field + fblock - 1) / fblock;",
    "    auto blend_at = [&](float t) {\n"
    "        karg_t = t;\n"
    "        int fblock = 256, fgrid = (field + fblock - 1) / fblock;")
src = src.replace(
    "    auto morph_at = [&](int mode, float t) {\n"
    "        void* a[] = { &d_xyz_in, &d_radius, &d_xyz_out, &karg_n, &karg_mode, &karg_t, &karg_clock };",
    "    auto morph_at = [&](int mode, float t) {\n"
    "        karg_mode = mode; karg_t = t;\n"
    "        void* a[] = { &d_xyz_in, &d_radius, &d_xyz_out, &karg_n, &karg_mode, &karg_t, &karg_clock };")

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("patched: mutable kernel-argument copies")

# show the launch arrays so the substitution is verifiable
for i, line in enumerate(open(PATH, encoding="utf-8").read().splitlines(), 1):
    if "void* a[]" in line or "&karg_" in line:
        print(f"  {i:4d}: {line.strip()[:96]}")
