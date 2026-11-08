from pathlib import Path

p = Path(r"C:\abrasax\DOC\RUN-STATE-20261101T1735Z.md")
s = p.read_text(encoding="utf-8")

old = """| `abrasax/services.py` | `subprocess.run(powershell -File ...)` | `winproc.run` + `-WindowStyle Hidden` |
| supervisor / ops monitor | already `CREATE_NO_WINDOW` / `DETACHED_PROCESS` | unchanged |"""
new = """| `abrasax/services.py` | `subprocess.run(powershell -File ...)` | `winproc.run` + `-WindowStyle Hidden` |
| `SCRIPTS/automation/ops_monitor.py` | `subprocess.run(nvidia-smi)` **and** `subprocess.run(powershell)` every 30 s tick | `winproc.run` (both) |
| supervisor spawn | already `CREATE_NO_WINDOW` | unchanged |

The warden was the worst case and was found last: `ops_monitor` runs under
`pythonw` and ticks every 30 s, so its `nvidia-smi` and PowerShell calls were a
console window every half minute, forever - it would have re-created the symptom
even after every service was fixed. Its `start()` already used
`DETACHED_PROCESS`; its *probes* did not. `fix_ops_monitor_headless.py` refused
to report success while any raw `subprocess.run` remained, which is why the
second call site (`proc_table`) was caught instead of shipped."""
assert s.count(old) == 1
s = s.replace(old, new, 1)

old2 = """Tests: `tests/test_headless_spawns.py` - 8 pass, including "no raw
`subprocess.Popen`/`run` left in the two local-server tools", "the llama.cpp
child is spawned detached", and "the launcher call is hidden"."""
new2 = """Tests: `tests/test_headless_spawns.py` - 8 pass, including "no raw
`subprocess.Popen`/`run` left in the two local-server tools", "the llama.cpp
child is spawned detached", and "the launcher call is hidden". The monitor's two
call sites are pinned the same way (`winproc.run`, no raw `subprocess.run`)."""
assert s.count(old2) == 1
s = s.replace(old2, new2, 1)

p.write_text(s, encoding="utf-8", newline="")
print("doc updated with the ops_monitor finding")
