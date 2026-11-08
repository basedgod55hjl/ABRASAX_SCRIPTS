"""fb_server.cpp: exclusive binding + concurrent request handling.

Two real defects observed 2026-10-25 on :9700:

1. SO_REUSEADDR on Windows does NOT mean "reuse a TIME_WAIT socket" the way it
   does on Linux -- it permits a SECOND process to bind an address already in
   use, and the two silently share incoming connections. Observed: pid 21460 and
   pid 36388 both LISTENING on 127.0.0.1:9700, interleaving responses. The bind
   error path even says "already running?" but never fired, because
   SO_REUSEADDR made the bind succeed.

2. The accept loop is single-threaded and each request is handled inline
   (recv until CRLFCRLF, then process). One slow client -- or llama/LM Studio
   holding a /chat request -- blocks every other connection. Observed: 1 of 4
   probes answered, the rest timed out at 6-8 s.

Fix: SO_EXCLUSIVEADDRUSE (Windows) so a second instance fails to bind, and
handle each accepted socket on its own thread.

Idempotent. Backs up first.
"""
import shutil
import sys
from pathlib import Path

TARGET = Path("C:/ABRASAX/ENGINE/floating_brain/cuda/src/fb_server.cpp")
BAK = TARGET.with_suffix(".cpp.bak-exclusive-bind")

OLD_SOCKOPT = """    int yes = 1;
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, (const char*)&yes, sizeof(yes));"""

NEW_SOCKOPT = """    // On Windows SO_REUSEADDR lets a SECOND process bind an address already in
    // use, quietly splitting traffic between two servers (observed on :9700).
    // SO_EXCLUSIVEADDRUSE makes the duplicate bind fail, which is what we want.
    int yes = 1;
    if (setsockopt(srv, SOL_SOCKET, SO_EXCLUSIVEADDRUSE,
                   (const char*)&yes, sizeof(yes)) != 0) {
        std::fprintf(stderr, "[fb] SO_EXCLUSIVEADDRUSE failed (%d)\\n", WSAGetLastError());
    }"""

OLD_ACCEPT = """    while (true) {
        SOCKET c = accept(srv, nullptr, nullptr);
        if (c == INVALID_SOCKET) continue;
"""

NEW_ACCEPT = """    while (true) {
        SOCKET c = accept(srv, nullptr, nullptr);
        if (c == INVALID_SOCKET) continue;
        // Handle concurrently: this loop used to process each request inline, so
        // one slow client blocked every other connection. Detach a worker and
        // let the body of the loop run inside it.
        if (!fb_spawn_worker(srv, c)) {
            // fall through: handle inline if the thread could not be created
        } else {
            continue;
        }
"""

WORKER_HELPER = '''
// ---------------------------------------------------------------------------
// per-connection worker
// ---------------------------------------------------------------------------
// The request handling below is written against a single socket. To serve
// several clients without restructuring it, each accepted socket is handed to a
// detached thread that re-enters the serve loop for exactly one connection.
static bool fb_spawn_worker(SOCKET srv, SOCKET c);
'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8", errors="surrogateescape")

    if "SO_EXCLUSIVEADDRUSE" in src:
        print("already applied - no change")
        return 0

    if OLD_SOCKOPT not in src:
        print("FAIL: setsockopt anchor not found verbatim")
        return 1

    if OLD_ACCEPT not in src:
        print("FAIL: accept-loop anchor not found verbatim")
        return 1

    if not BAK.exists():
        shutil.copy2(TARGET, BAK)
        print(f"backup: {BAK}")

    src = src.replace(OLD_SOCKOPT, NEW_SOCKOPT, 1)

    # Only the binding fix is applied automatically. The threading change needs a
    # restructure of the request body and is staged separately with proof.
    TARGET.write_text(src, encoding="utf-8", errors="surrogateescape")
    print(f"patched bind: {TARGET}")
    print("NOTE: threading fix NOT applied - requires restructure, see report")
    return 0


if __name__ == "__main__":
    sys.exit(main())
