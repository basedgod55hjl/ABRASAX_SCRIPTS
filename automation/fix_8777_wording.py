"""Correct the :8777 wording in FINAL_RUN_STATE.md.

The refresh script measured two different things and the doc blurred them:

    TCP connect  -> UP
    HTTP GET /   -> HTTPError

"DOWN (HTTPError)" is wrong: the port is listening, the HTTP layer just does not
answer GET / the way my probe expected (it is an LLM server, not a web root).
Reporting a live listener as DOWN because my probe hit the wrong path is exactly
the false-negative class of bug I hit three times already tonight.

Fix: say, precisely, that the socket is open and that GET / is not a valid probe
for it, and cite the endpoint that IS valid.
"""
import sys

PATH = r"C:\ABRASAX\DOC\FINAL_RUN_STATE.md"
src = open(PATH, encoding="utf-8").read()

if "socket open, `GET /` not a valid probe" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = "| `:8777` node LLM | **DOWN (HTTPError)** | LISTENING |"
NEW = ("| `:8777` node LLM | **socket open, `GET /` not a valid probe** "
       "(use its `/v1` routes) | LISTENING |")

if OLD not in src:
    print("ANCHOR-NOT-FOUND: :8777 row")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: :8777 row now distinguishes listener from HTTP route")
