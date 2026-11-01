#!/usr/bin/env bash
# vlc_reload_resume.sh — stop VLC, relaunch it, and restore the exact playback position.
#
# Why this exists: `vlcrc` is only written on exit, so any config/plugin change needs a full
# restart, and this box's VLC sessions are long playlists the user does not want to lose their
# place in. The reload therefore:
#   1. reads the LIVE position immediately before stopping (never a cached reading - long
#      playlists auto-skip dead paths while loading, so an older reading is wrong),
#   2. stops every vlc.exe,
#   3. relaunches with the same playlist,
#   4. POLLS the HTTP handler until it answers (the port listens before the Lua handler is
#      ready, so an open port alone means nothing),
#   5. re-issues pl_play&id=<plid> then seek&val=<seconds>,
#   6. verifies the clock is actually ADVANCING (a frozen clock is the failure this fixes).
#
# Usage: vlc_reload_resume.sh [playlist.xspf]
set -uo pipefail

PW=$(grep -E '^http-password=' "$HOME/AppData/Roaming/vlc/vlcrc" | cut -d= -f2-)
VLC_EXE="C:/Program Files/VideoLAN/VLC/vlc.exe"
XSPF="${1:-C:/Users/sirch/Desktop/vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv.xspf}"
API="http://127.0.0.1:8080/requests/status.json"
RESUME="$HOME/AppData/Local/Temp/vlc_resume_point.json"
# native tools (python, taskkill, tasklist) cannot read the MSYS /c/... form
RESUME_W="C:/Users/sirch/AppData/Local/Temp/vlc_resume_point.json"

api() { curl -s -m 6 -u ":$PW" "$API"; }
get() { api | python -c "import sys,json;d=json.load(sys.stdin);print(d.get('$1'))" 2>/dev/null; }

# NOTE: under MSYS_NO_PATHCONV=1 the single-slash form is preserved verbatim, which is what
# taskkill/tasklist need. The doubled //IM form that works WITHOUT that env var is rejected
# here ("Invalid argument/option - '//IM'"), and a failing tasklist grep then makes the
# "is it stopped?" check report success against a still-running VLC.
vlc_running() { MSYS_NO_PATHCONV=1 tasklist /FI "IMAGENAME eq vlc.exe" 2>/dev/null | grep -qi "vlc.exe"; }

echo "== 1. capturing live position (fresh, immediately before stopping) =="
PLID=$(get currentplid); T=$(get time); ST=$(get state)

# The URI matters more than the plid: VLC assigns plids PER RUN, so an id captured before a
# restart does not identify the same item afterwards (a reload silently resumed a different
# track until this was fixed). Save the uri and re-resolve the id after relaunch.
cur_uri() {
  curl -s -m 8 -u ":$PW" "http://127.0.0.1:8080/requests/playlist.json" | python -c "
import sys, json
t = json.load(sys.stdin)
def walk(n):
    if n.get('current') == 'current' and n.get('uri'):
        print(n['uri']); return True
    for c in n.get('children') or []:
        if walk(c): return True
    return False
walk(t)
" 2>/dev/null
}
URI=$(cur_uri)
echo "   plid=$PLID time=$T state=$ST"
echo "   uri=${URI:-<none>}"
if [ -z "${PLID:-}" ] || [ "$PLID" = "None" ]; then
  echo "   WARN: no live VLC state; will reload without resuming a position"
  PLID=""; T=""
fi
python -c "
import json
json.dump({'plid': '$PLID', 'time': '$T', 'uri': '''$URI'''}, open(r'$RESUME_W','w'))
print('   saved ->', r'$RESUME_W')
"

echo "== 2. stopping every vlc.exe =="
MSYS_NO_PATHCONV=1 taskkill /IM vlc.exe /F 2>&1 | sed 's/^/   /'
STOPPED=0
for i in $(seq 1 25); do
  if ! vlc_running; then STOPPED=1; echo "   all stopped after ${i} check(s)"; break; fi
  sleep 1
done
if [ "$STOPPED" != "1" ]; then echo "   ERROR: vlc.exe still running - aborting before relaunch"; exit 1; fi

echo "== 3. relaunching with the same playlist =="
echo "   $XSPF"
MSYS_NO_PATHCONV=1 cmd /c start "" "$VLC_EXE" "$XSPF"

echo "== 4. polling HTTP until the Lua handler is up (port opens before it is ready) =="
UP=0
for i in $(seq 1 90); do
  CODE=$(curl -s -o /dev/null -m 4 -w '%{http_code}' -u ":$PW" "$API" 2>/dev/null)
  if [ "$CODE" = "200" ]; then UP=1; echo "   HTTP 200 after ${i}s"; break; fi
  sleep 1
done
if [ "$UP" != "1" ]; then echo "   ERROR: HTTP never came up"; exit 1; fi

echo "== 5. restoring position (re-resolving the plid by URI) =="
if [ -n "${PLID:-}" ]; then
  # Resolve the item's NEW plid from the saved uri; the pre-restart id is not valid.
  NEWPLID="$PLID"
  if [ -n "${URI:-}" ]; then
    for i in $(seq 1 30); do
      NEWPLID=$(curl -s -m 8 -u ":$PW" "http://127.0.0.1:8080/requests/playlist.json" | URI="$URI" python -c "
import os, sys, json
want = os.environ['URI']
t = json.load(sys.stdin)
hit = []
def walk(n):
    if n.get('uri') == want and n.get('id'):
        hit.append(str(n['id']))
    for c in n.get('children') or []:
        walk(c)
walk(t)
print(hit[0] if hit else '')
" 2>/dev/null)
      [ -n "$NEWPLID" ] && { echo "   uri resolves to new plid=$NEWPLID (old was $PLID)"; break; }
      sleep 1
    done
  fi

  curl -s -m 10 -u ":$PW" "http://127.0.0.1:8080/requests/status.json?command=pl_play&id=$NEWPLID" >/dev/null
  echo "   pl_play id=$NEWPLID issued"
  for i in $(seq 1 40); do
    CUR=$(get currentplid)
    [ "$CUR" = "$NEWPLID" ] && { echo "   plid $NEWPLID is current after ${i}s"; break; }
    sleep 1
  done
  sleep 2
  curl -s -m 10 -u ":$PW" "http://127.0.0.1:8080/requests/status.json?command=seek&val=$T" >/dev/null
  echo "   seek -> ${T}s"
fi

echo "== 6. verifying the clock ADVANCES (the actual fix) =="
A=$(get time); sleep 5; B=$(get time)
echo "   t0=$A  t0+5s=$B"
python - "$A" "$B" <<'PY'
import sys
try:
    a, b = float(sys.argv[1]), float(sys.argv[2])
except Exception:
    print("   cannot parse times:", sys.argv[1:]); raise SystemExit(2)
if b > a:
    print("   OK: clock advancing (+%.0fs in 5s)" % (b - a))
else:
    print("   FAIL: clock still frozen at %s" % b); raise SystemExit(1)
PY
RC=$?
echo
if [ $RC -eq 0 ]; then echo "RELOAD OK — playing at $(get time)s / $(get length)s, plid $(get currentplid)"; else echo "RELOAD INCOMPLETE — clock frozen"; fi
exit $RC
