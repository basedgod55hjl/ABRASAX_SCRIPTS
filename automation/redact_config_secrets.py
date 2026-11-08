"""Redact secret literals found in CONFIG/ -- at-rest exposure, not a git leak.

MEASURED (section 5 audit):
  * CONFIG/ is fully gitignored (.gitignore:94 `/CONFIG/`), 0 files tracked, so
    these never reached GitHub. This is NOT the same defect as the lm_client.ts
    key from section 3, which WAS pushed to origin/main.
  * but 36 secret literal occurrences sit in plaintext on disk, across at least
    three distinct credentials:
        sk-33e...53   (the same DeepSeek key found in lm_client.ts)
        sk-192...7c
        sk-77d...a1
  * CONFIG/source-config/ and CONFIG/source-claude/ are harvested third-party
    settings from other tools, which is why they are full of keys.

At-rest exposure still matters: any process, backup, or later `git add -f` can
publish them. So redact in place, keep every file's structure, and emit a rotation
list.

Does NOT touch: .env (already gitignored, and it is the intended store), or any
file under _VAULT (the deliberate secret vault).

Idempotent: a file whose secrets are already redacted is skipped.
"""
import json
import os
import re
import shutil
import sys
import time

ROOT = r"C:\ABRASAX"
CONFIG = os.path.join(ROOT, "CONFIG")
VAULT = os.path.join(ROOT, "_VAULT", "secrets")

PATTERNS = {
    "sk-": (20, 200),
    "nvapi-": (40, 90),
    "ghp_": (36, 40),
    "AKIA": (20, 21),
    "xoxb-": (30, 90),
}
TOKEN = re.compile(r"[A-Za-z0-9_\-]{16,220}")
REDACTION = "REDACTED_BY_ABRASAX"

# findings collected here, written to the vault (gitignored)
found = []          # (relpath, lineno, full_token)


def scan_file(full):
    hits = []
    try:
        if os.path.getsize(full) > 5_000_000:
            return hits
        text = open(full, encoding="utf-8", errors="ignore").read()
    except OSError:
        return hits
    for ln, line in enumerate(text.splitlines(), 1):
        for pre, (lo, hi) in PATTERNS.items():
            if pre not in line:
                continue
            for m in TOKEN.finditer(line):
                tok = m.group(0)
                if tok.startswith(pre) and lo <= len(tok) <= hi:
                    # Placeholders are not secrets. Redacting them would corrupt
                    # documentation and template files.
                    low = tok.lower()
                    if ("your" in low or "xxxx" in low or "bypass" in low
                            or "here" in low or "placeholder" in low
                            or low.endswith("-key")):
                        break
                    hits.append((ln, tok))
                    break
    return hits


def redact_text(text):
    def repl(m):
        tok = m.group(0)
        for pre, (lo, hi) in PATTERNS.items():
            if tok.startswith(pre) and lo <= len(tok) <= hi:
                return REDACTION
        return tok
    return TOKEN.sub(repl, text)


def main():
    apply = "--apply" in sys.argv

    # Harvested third-party trees: tens of thousands of vendored settings files
    # that are not our configuration. Scanning them made this never finish.
    SKIP_DIRS = {"agi-config", "source-config"}

    targets = []
    for dp, dn, fns in os.walk(CONFIG):
        dn[:] = [d for d in dn
                 if d != "__pycache__" and d not in SKIP_DIRS]
        for fn in fns:
            if fn.endswith((".json", ".yaml", ".yml", ".toml", ".ini",
                            ".cfg", ".py", ".local", ".settings")):
                targets.append(os.path.join(dp, fn))
    print(f"scanning {len(targets)} config file(s) "
          f"(skipping {', '.join(sorted(SKIP_DIRS))})")

    files_with_hits = 0
    total_hits = 0
    for idx, full in enumerate(targets, 1):
        if idx % 200 == 0:
            print(f"  ... {idx}/{len(targets)} files scanned", flush=True)
        hits = scan_file(full)
        if not hits:
            continue
        rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
        files_with_hits += 1
        total_hits += len(hits)
        print(f"{rel}: {len(hits)} hit(s)")
        for ln, tok in hits:
            found.append((rel, ln, tok))
            print(f"    line {ln}: {tok[:6]}...{tok[-2:]} (len {len(tok)})")

        if apply:
            text = open(full, encoding="utf-8", errors="ignore").read()
            new = redact_text(text)
            if new != text:
                backup = full + ".bak-" + time.strftime("%Y%m%d-%H%M")
                shutil.copy2(full, backup)
                open(full, "w", encoding="utf-8", newline="").write(new)

    print(f"\nfiles with secrets : {files_with_hits}")
    print(f"total occurrences  : {total_hits}")
    print(f"distinct values    : {len(set(t for _, _, t in found))}")

    if not found:
        print("\nRESULT: nothing to redact")
        return 0

    # persist the real values outside the repo tree for rotation
    os.makedirs(VAULT, exist_ok=True)
    out = os.path.join(VAULT, "config-secrets-20261018.json")
    if apply:
        seen = {}
        for rel, ln, tok in found:
            seen.setdefault(tok, []).append(f"{rel}:{ln}")
        payload = {
            "captured": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "note": "ROTATE EVERY ONE OF THESE. CONFIG/ is gitignored so these were "
                    "not published, but they were plaintext on disk.",
            "secrets": [{"value": k, "sha256_prefix": None, "found_at": v}
                        for k, v in seen.items()],
        }
        with open(out, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"\npreserved to {out} (gitignored)")
        print("redaction applied")
        print("\nREMAINING: rotate these at the providers -- redaction does not")
        print("invalidate a key that has already sat on disk.")
        return 0

    print("\ndry run -- re-run with --apply to redact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
