#!/usr/bin/env bash
# gate_test.sh — prove the CI gate can FAIL and can PASS.
# A gate that has never been seen failing is not evidence; this builds a tree with
# a known-broken file in a subdirectory, runs the gate, and asserts exit 1, then
# runs it against the repaired ABRASAX-UI stage tree and asserts exit 0.
set -u
PY="/c/ABRASAX/.venv/Scripts/python.exe"
GATE="/c/ABRASAX/SCRIPTS/gate.sh"
T="/c/Users/lucar/_gatetest"

rm -rf "$T"; mkdir -p "$T/src"

printf 'x = 1\n' > "$T/good_root.py"
printf 'def ok():\n    return 1\n' > "$T/src/good_sub.py"
{
  printf '"""ABRASAX banner"""\n'
  printf '#!/usr/bin/env python3\n'
  printf '"""second string literal - this is the generator bug"""\n'
  printf 'from __future__ import annotations\n'
  printf 'x = 1\n'
} > "$T/src/bad_future.py"

export PY
echo "=== case 1: broken file in a subdirectory (must FAIL)"
bash "$GATE" "$T"; rc1=$?
echo "exit=$rc1"

echo
echo "=== case 2: repaired ABRASAX-UI stage tree (must PASS)"
bash "$GATE" /c/Users/lucar/abrasax-build/stage/ABRASAX-UI > /tmp/gate2.log 2>&1; rc2=$?
tail -3 /tmp/gate2.log
echo "exit=$rc2"

rm -rf "$T"
echo
if [ "$rc1" -ne 0 ] && [ "$rc2" -eq 0 ]; then
  echo "GATE VERIFIED: fails on a broken file, passes on a clean tree"
  exit 0
else
  echo "GATE NOT VERIFIED: rc1=$rc1 (want non-zero) rc2=$rc2 (want 0)"
  exit 1
fi
