import io, os, shutil

P = r"C:\ABRASAX\SCRIPTS\automation\supervisor.py"
src = io.open(P, encoding="utf-8").read()

OLD = '''def _port_open(port: int, timeout: float = 0.4) -> bool:
    """True when something accepts TCP on the port.

    The health probe is HTTP with a 0.6 s budget; a service that is listening but
    slow to answer used to be classified 'down' and a second instance was spawned
    after the cooldown (SO_REUSEADDR then allowed both to bind). This guard makes
    'a listener exists' sufficient reason not to start another one.
    """
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout):
            return True
    except OSError:
        return False
'''

NEW = '''def _port_open(port: int, timeout: float = 0.4) -> bool:
    """True when something accepts TCP on the port.

    The health probe is HTTP with a 0.6 s budget; a service that is listening but
    slow to answer used to be classified 'down' and a second instance was spawned
    after the cooldown (SO_REUSEADDR then allowed both to bind). This guard makes
    'a listener exists' sufficient reason not to start another one.

    Measured 2026-11-01: `socket.create_connection(..., timeout=1.2)` blocked the
    supervisor loop indefinitely (main thread parked in socket.py:836 from here,
    zero CPU, heartbeat frozen). The socket timeout does not reliably interrupt a
    connect() on this host, so the call is driven on a daemon thread and given a
    hard wall. A stuck connect can then only strand its own thread - which is
    daemonised precisely so it can never keep the supervisor alive or block it.
    """
    deadline = float(timeout)
    result = {"open": False}

    def _connect() -> None:
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(deadline)
            s.connect(("127.0.0.1", int(port)))
            result["open"] = True
        except OSError:
            pass
        finally:
            if s is not None:
                try:
                    s.close()
                except OSError:
                    pass

    t = threading.Thread(target=_connect, name=f"portprobe-{port}", daemon=True)
    t.start()
    # Small slack on top of the socket timeout; never return before the probe
    # has had its full budget, never wait meaningfully longer than that.
    t.join(deadline + 0.8)
    return result["open"]
'''

if OLD not in src:
    raise SystemExit("ANCHOR NOT FOUND - refusing to patch")
if "portprobe-" in src:
    raise SystemExit("already patched")

src = src.replace(OLD, NEW, 1)

if "\nimport threading" not in src:
    src = src.replace("import subprocess\n", "import subprocess\nimport threading\n", 1)

bak = P + ".bak-portlock"
if not os.path.exists(bak):
    shutil.copy2(P, bak)
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("patched", P, os.path.getsize(P), "bytes; backup", bak)
print("threading imported:", "\nimport threading" in src)
