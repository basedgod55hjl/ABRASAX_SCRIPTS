@echo off
:: ABRASAX_JEV: decisions via abrasax_jev.py / _WORK/jev_client.py
REM Launch the ABRASAX synaptic brain service (learnable synapse layer) on :9625.
REM FlyWire v783 mirror: heavy-tailed hubs, 26.6% reciprocity, 23% GABA-like sign,
REM 9.2% DA/OA/5-HT modulator budget. Non-stop: --autoloop 5 (1 learn-step / 5 s),
REM --resume persists weights across restarts (data/state/synaptic_brain.npz).
REM Uses .venv (torch CUDA) so the field runs on the GTX 1660 Ti; falls back to numpy.
REM Any appended args after this line override the defaults (argparse: last wins).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [synaptic] .venv python not found, falling back to system python
  python tools\abraxas_synaptic_server.py --serve --port 9625 --autoloop 5 --resume %*
  goto :eof
)
".venv\Scripts\python.exe" tools\abraxas_synaptic_server.py --serve --port 9625 --autoloop 5 --resume %*
