#requires -Version 5.1
<#
  ABRASAX - repair the uv venv interpreter stub.

  PROBLEM (measured 2026-10-19)
  -----------------------------
  PYTHON\.venv_gui was created by uv from a different path
  (C:\Users\sirch\Desktop\ABRASAX_GOD_OS\.venv_gui) and then moved here. What
  sits in Scripts\ is not a normal venv python: it is a 262,144-byte stub that
  re-execs the base interpreter. The re-exec re-runs the SAME command line, so:

      venv\Scripts\python.exe -m pytest ...
        -> base python.exe -m pytest ...        (same argv, venv context lost)
        -> which resolves back through the same entry point
        -> repeats until it deadlocks

  Symptoms this caused in practice:
    * the full test suite froze at ~47% forever
      (TESTS/python/test_brain.py::test_step_persists_and_fresh_process_sees_it
       spawns sys.executable -c "...", which is exactly the stub)
    * abrasax.pulse died after one tick
    * every non-interactive launch looked "hung" in Task Scheduler

  FIX
  ---
  A venv does not need a special python.exe. The stock interpreter reads
  pyvenv.cfg from its parent directory and adopts sys.prefix from it. So we put
  the REAL base binary in place of the stub and ship the two DLLs the venv was
  missing (python3.dll, python311.dll). Verified by
  `sys.prefix != sys.base_prefix` being True and pytest reporting from the venv.

  The old stub is kept as python.exe.shim-bak.
#>
param(
  [string]$Venv = 'C:\ABRASAX\PYTHON\.venv_gui',
  # DEAD PATH (sirch): uv cpython-3.11.15 not installed on this host (only cpython-3.14.9 exists). Pass -Base explicitly to repair.
  [string]$Base = ''
)

$ErrorActionPreference = 'Stop'
$scripts = Join-Path $Venv 'Scripts'
$py      = Join-Path $scripts 'python.exe'

if (-not (Test-Path $py))    { throw "no interpreter at $py" }
if (-not (Test-Path $Base))  { throw "no base interpreter at $Base" }

$size = (Get-Item $py).Length
Write-Host "[repair] current python.exe: $size bytes"

if ($size -lt 150000) {
  Write-Host "[repair] already a real interpreter; nothing to do"
} else {
  Write-Host "[repair] looks like the re-exec stub; replacing"
  if (-not (Test-Path "$py.shim-bak")) {
    Copy-Item $py "$py.shim-bak" -Force
  }
  Copy-Item (Join-Path $Base 'python.exe')   $py -Force
  Copy-Item (Join-Path $Base 'python3.dll')   (Join-Path $scripts 'python3.dll')   -Force -EA SilentlyContinue
  Copy-Item (Join-Path $Base 'python311.dll') (Join-Path $scripts 'python311.dll') -Force -EA SilentlyContinue
}

# --- verify ------------------------------------------------------------
$out = & $py -c "import sys; print('INVENV' if sys.prefix != sys.base_prefix else 'OUTSIDE'); print(sys.prefix)" 2>&1
$out | ForEach-Object { Write-Host "[verify] $_" }

if (($out -join "`n") -notmatch 'INVENV') {
  throw "venv not adopted after repair: $out"
}

$pytestVersion = & $py -m pytest --version 2>&1 | Select-Object -First 1
Write-Host "[verify] $pytestVersion"
Write-Host "[repair] OK - interpreter is venv-aware and pytest resolves"
