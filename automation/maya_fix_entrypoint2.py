"""Final fix: forward the child's stdout/stderr as the PARENT'S stream objects.

Evidence chain (all measured):
  1. test_docker_entrypoint.py asserts the entrypoint prints exactly 1 newline;
     it observed 0.            -> real defect, correct test.
  2. A file-marker probe proved the child DOES run through the entrypoint.
  3. The child reported isatty=True inside the wrapper, i.e. its stdout was a
     console handle rather than the capturing parent's pipe. That is why the
     bytes never reached the caller.
  4. `stdin=None/stdout=None/stderr=None` means "use our current std handles",
     which is not the same as continuing the caller's redirection.

FIX: pass the parent's actual stream objects. subprocess dups them into the
child, so whatever the caller redirected to (pipe, file, console) keeps
receiving the child's output, exactly like the os.execvp path on Linux.
"""
from __future__ import annotations

import sys
from pathlib import Path

P = Path(r"C:\ABRASAX\TYPESCRIPT\maya\docker\entrypoint.py")
src = P.read_text(encoding="utf-8")

start = src.find("        # Wire the child's streams to OURS.")
end = src.find("        sys.exit(completed.returncode)")
if start < 0 or end < 0:
    # already in the original form?
    old = "        sys.exit(subprocess.run(sys.argv[1:]).returncode)"
    if old not in src:
        sys.exit("could not locate the child-launch block")
    start = src.find(old)
    end = start + len(old)

new_block = '''        # Forward OUR OWN stream objects, not `None`. `None` means "give the
        # child our current std handles", which on Windows resolves to the
        # console even when the caller captured a pipe -- measured: the child
        # reported isatty=True inside this wrapper while the capturing parent saw
        # an empty stdout. Passing the parent's real streams makes subprocess
        # dup them into the child, so a redirected caller keeps receiving output
        # exactly as the os.execvp path does on Linux.
        completed = subprocess.run(
            sys.argv[1:],
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
            env=os.environ,
        )
        sys.exit(completed.returncode)'''

src = src[:start] + new_block + src[end + len("        sys.exit(completed.returncode)"):]
P.write_text(src, encoding="utf-8")
print(f"rewrote child launch in {P} ({P.stat().st_size} B)")
