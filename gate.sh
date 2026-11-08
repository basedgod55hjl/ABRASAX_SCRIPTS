#!/usr/bin/env bash
# gate.sh — the exact gate the workflow runs, extracted so it can be tested.
# Usage: PY=python3 ./gate.sh <dir>
# Exits non-zero if any .py anywhere in <dir> fails to byte-compile.
set -u
PY="${PY:-python}"
root="${1:-.}"
cd "$root" || exit 2
fail=0
count=0
while IFS= read -r -d '' f; do
  count=$((count + 1))
  if "$PY" -m py_compile "$f" 2>/tmp/err; then
    echo "  OK: $f"
  else
    echo "::error file=$f::does not compile"
    sed -n '1,6p' /tmp/err | sed 's/^/     /'
    fail=1
  fi
done < <(find . -name '*.py' -not -path './.git/*' -print0)
echo "compiled $count file(s); failures=$fail"
exit $fail
