"""Point string_brain.py at the renderer's /drive route.

The brain service has no field-write route (POST /field -> 404, verified), so the
original push_to_brain() could only fall back to /step -- it never actually moved
the field with LLM output.

The renderer now owns its own drive field (POST /drive, verified working), so push
the quantised token field there. That is the real coupling: model output -> pixels.

Idempotent.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\string_brain.py"
src = open(PATH, encoding="utf-8").read()

if "push_to_renderer" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

start = src.find("def push_to_brain(field, dry_run=False):")
end = src.find("def ask_llm(prompt, max_tokens=48):")
if start == -1 or end == -1 or end < start:
    print("ANCHOR-NOT-FOUND: push_to_brain/ask_llm")
    sys.exit(1)

new_fn = '''def push_to_renderer(field, dry_run=False):
    """Push the LLM-derived field to the renderer's /drive route.

    Quantise to uint8 the same way the shader will read it, base64-encode, POST.
    The renderer stores it and the next /frame.png renders *this* instead of the
    brain feed, so the model's reply literally becomes the image.
    """
    if dry_run:
        return "dry-run"

    raw = bytes(int(max(0.0, min(1.0, v)) * 255) for v in field)
    payload = {
        "w": W,
        "h": H,
        "data": base64.b64encode(raw).decode("ascii"),
    }
    try:
        st, body = post_json(f"{RENDER}/drive", payload, timeout=10)
        if 200 <= st < 300:
            return "drive-ok"
        return f"drive-http-{st}"
    except Exception as e:  # noqa: BLE001
        return f"drive-failed ({type(e).__name__})"


'''

src = src[:start] + new_fn + src[end:]

# import base64
if "import base64" not in src:
    src = src.replace("import argparse\n", "import argparse\nimport base64\n", 1)

# call the new function
src = src.replace("result = push_to_brain(field, args.dry_run)",
                  "result = push_to_renderer(field, args.dry_run)")

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: push_to_renderer wired to POST /drive")
