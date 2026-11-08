import io, os, shutil

P = r"C:\ABRASAX\SCRIPTS\automation\supervisor.py"
src = io.open(P, encoding="utf-8").read()

OLD = '''    for req in spec.get("requires") or []:
        if not Path(req).exists():
            return {"error": f"missing prerequisite: {req}", "blocked": True}
    return None
'''

NEW = '''    for req in spec.get("requires") or []:
        if not Path(req).exists():
            return {"error": f"missing prerequisite: {req}", "blocked": True}

    # Existence is not enough. On 2026-11-01 BUILD/llamacpp/build/bin/llama-server.exe
    # existed as a 10,752-byte stub whose import llama-server-impl.dll was absent from
    # that directory; it died with 0xC0000135 (STATUS_DLL_NOT_FOUND) in ~40 ms, so the
    # supervisor "started" it, saw it down next tick, and burned the 180 s cooldown for
    # ever. A binary that cannot survive its own startup is a blocked prerequisite.
    exe = spec.get("cmd") or []
    if exe and str(exe[0]).lower().endswith(".exe"):
        why = _exe_unrunnable(Path(exe[0]))
        if why:
            return {"error": f"unrunnable binary: {Path(exe[0]).name} ({why})",
                    "blocked": True}
    return None


_EXE_PROBE_TTL_S = 600.0
_exe_probe_cache: dict[str, tuple[float, str | None]] = {}


def _exe_unrunnable(path: Path) -> str | None:
    """Return a short reason if `path` cannot run, else None.

    Probes once and caches for _EXE_PROBE_TTL_S: a Windows process that exits
    non-zero within a couple of seconds, with no stdout, is treated as broken.
    Only used for services that name a literal .exe.
    """
    import subprocess as _sp
    key = str(path).lower()
    now = time.time()
    hit = _exe_probe_cache.get(key)
    if hit and now - hit[0] < _EXE_PROBE_TTL_S:
        return hit[1]
    reason = None
    try:
        cp = _sp.run([str(path), "--version"], cwd=str(path.parent),
                     capture_output=True, timeout=8)
        if cp.returncode != 0 and not (cp.stdout or b"").strip():
            reason = "exit 0x%08X" % (cp.returncode & 0xFFFFFFFF)
    except _sp.TimeoutExpired:
        reason = None                      # slow but alive: not our call to block
    except OSError as exc:
        reason = exc.__class__.__name__
    except Exception:
        reason = None
    _exe_probe_cache[key] = (now, reason)
    return reason
'''

if OLD not in src:
    raise SystemExit("ANCHOR NOT FOUND")
if "_exe_unrunnable" in src:
    raise SystemExit("already patched")

src = src.replace(OLD, NEW, 1)

bak = P + ".bak-exeprobe"
if not os.path.exists(bak):
    shutil.copy2(P, bak)
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("patched", P, os.path.getsize(P), "bytes")
