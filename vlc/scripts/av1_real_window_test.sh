#!/usr/bin/env bash
# av1_real_window_test.sh — will a 4K AV1 file play with SOFTWARE decode in a real window?
#
# Background: the GTX 1660 Ti is Turing and has no AV1 hardware decoder. 4K AV1 files jump and
# reset in the normal session. Earlier `--intf dummy` tests are NOT trustworthy here because a
# dummy interface has no video output, so they cannot reproduce a video-output fault at all.
# This uses a REAL window on a throwaway port so the user's main session is untouched.
set -uo pipefail

VLC="/c/Program Files/VideoLAN/VLC/vlc.exe"
SRC="G:\\SORTED_MEDIA\\Videos\\04_Large_1GB_to_5GB\\in-dick-cisive-bride_2160p.mp4"
PORT=18099
PW="av1soft"

probe() {  # $1 = avcodec-hw value, $2 = label
  local hw="$1" label="$2"
  echo "=============================================================="
  echo "  REAL WINDOW, avcodec-hw=$hw   ($label)"
  echo "=============================================================="

  MSYS_NO_PATHCONV=1 "$VLC" --ignore-config --no-one-instance --avcodec-hw="$hw" \
    --extraintf=http --http-port=$PORT --http-host=127.0.0.1 --http-password="$PW" \
    --no-media-library --no-video-title-show --start-time=120 \
    "$SRC" >/dev/null 2>&1 &
  local vpid=$!

  local up=0 code
  for i in $(seq 1 30); do
    code=$(curl -s -o /dev/null -m 3 -w '%{http_code}' -u ":$PW" \
           "http://127.0.0.1:$PORT/requests/status.json" 2>/dev/null)
    [ "$code" = "200" ] && { up=1; break; }
    sleep 1
  done
  if [ "$up" != "1" ]; then echo "  HTTP never came up"; kill $vpid 2>/dev/null; return 1; fi

  echo "  sampling the clock and the NVIDIA decoder for 24s..."
  local samples=() decs=()
  for i in $(seq 1 8); do
    local t d
    t=$(curl -s -m 4 -u ":$PW" "http://127.0.0.1:$PORT/requests/status.json" \
        | python -c "import sys,json;print(json.load(sys.stdin).get('time'))" 2>/dev/null)
    d=$(MSYS_NO_PATHCONV=1 nvidia-smi --query-gpu=utilization.decoder --format=csv,noheader 2>/dev/null)
    samples+=("$t"); decs+=("$d")
    echo "    t+$((i*3))s  time=$t   nvidia_decoder=$d"
    sleep 3
  done

  python - "${samples[@]}" <<'PY'
import sys
vals = []
for s in sys.argv[1:]:
    try: vals.append(float(s))
    except Exception: pass
if len(vals) < 3:
    print("  VERDICT: not enough samples")
else:
    deltas = [vals[i+1]-vals[i] for i in range(len(vals)-1)]
    pos = sum(1 for d in deltas if d > 0)
    resets = sum(1 for i in range(len(vals)-1) if vals[i+1] < vals[i] - 5)
    print(f"  clock trace: {vals}")
    print(f"  advancing steps: {pos}/{len(deltas)}   resets: {resets}")
    if pos >= len(deltas) - 1 and resets == 0:
        print("  VERDICT: PLAYING CLEANLY")
    elif resets:
        print("  VERDICT: UNSTABLE - clock resets, VLC is giving up on frames")
    else:
        print("  VERDICT: STALLED")
PY
  MSYS_NO_PATHCONV=1 taskkill /PID $vpid /T /F >/dev/null 2>&1
  sleep 3
}

probe none  "software dav1d"
probe any   "auto-select"

echo
echo "DONE"
