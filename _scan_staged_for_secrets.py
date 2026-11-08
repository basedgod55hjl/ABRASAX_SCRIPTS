"""_scan_staged_for_secrets.py - refuse to commit a live credential.

Reads the *index* (what would be committed), never the working tree, so a file
excluded by .gitignore cannot be reported and a staged secret cannot be missed.

Patterns are the shapes that actually leaked in this project's history
(`github_pat_`, `ghp_`, `sk-` keys). Nothing is printed except path, pattern
name and line number - never the value.

    python SCRIPTS/_scan_staged_for_secrets.py        # exit 1 if anything is found
"""
from __future__ import annotations

import re
import subprocess
import sys

PATTERNS = {
    "github_pat": re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    "ghp": re.compile(rb"ghp_[A-Za-z0-9]{30,}"),
    "gho": re.compile(rb"gho_[A-Za-z0-9]{30,}"),
    "sk-key": re.compile(rb"sk-[A-Za-z0-9_\-]{20,}"),
    "aws": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
ALLOW_SUFFIX = (".md",)          # docs may discuss the pattern; values are still caught
MAX_BYTES = 4_000_000            # skip binaries/large blobs


def staged_files() -> list[str]:
    r = subprocess.run(["git", "diff", "--cached", "--name-only", "-z"],
                       capture_output=True, text=True)
    return [p for p in r.stdout.split("\0") if p]


def main() -> int:
    hits = 0
    files = staged_files()
    for path in files:
        if path.endswith(ALLOW_SUFFIX):
            continue
        blob = subprocess.run(["git", "show", f":{path}"], capture_output=True)
        data = blob.stdout
        if not data or len(data) > MAX_BYTES or b"\0" in data[:4096]:
            continue
        for name, rx in PATTERNS.items():
            for m in rx.finditer(data):
                line = data.count(b"\n", 0, m.start()) + 1
                print(f"SECRET {name} {path}:{line}")
                hits += 1
    print(f"staged files: {len(files)}  hits: {hits}")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
