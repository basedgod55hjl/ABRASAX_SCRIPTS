#!/usr/bin/env bash
# av1_dav1d_threads.sh — does parallelising dav1d make 4K AV1 playable?
#
# The GTX 1660 Ti has no AV1 hardware decoder, so 4K AV1 falls to dav1d (software). VLC exposes
# --dav1d-thread-frames (default 0 = auto), which is FRAME-level parallelism. This box has 16
# logical cores. If raising it makes the clock advance steadily, AV1 is fixable by config and
# the ~30-hour transcoding job is unnecessary.
#
# Real window on a throwaway port; the user's session is untouched.
set -uo pipefail

VLC="/c/Program Files/VideoLAN/VLC/vlc.exe"
SRC="G:\\SORTED_MEDIA\\Videos\\04_Large_1GB_to_5GB\\in-dick-cisive-bride_2160p.mp4"
PORT=18101
PW="dav1dt"

measure() {  # $1 = thread-frames value, $2 = label
  local tt="$1" label="$2"
  echo "=============================================================="
  echo "  dav1d-thread-frames=$tt   ($label)"
  echo "=============================================================="

  MSYS_NO_PATHCONV=1 "$VLC" --ignore-config --no-one-instance --avcodec-hw=none \
    --dav1d-thread-frames="$tt" \
    --extraintf=http --http-port=$PORT --http-host=127.0.0.1 --http-password="$PW" \
    --no-media-library --no-video-title-show "$SRC" >/dev/null 2>&1 &
  local vpid=$!

  local up=0 code
  for i in $(seq 1 30); do
    code=$(curl -s -o /dev/null -m 3 -w '%{http_code}' -u ":$PW" \
           "http://127.0.0.1:$PORT/requests/status.json" 2>/dev/null)
    [ "$code" = "200" ] && { up=1; break; }
    sleep 1
  done
  if [ "$up" != "1" ]; then echo "  HTTP never came up"; kill $vpid 2>/dev/null; return 1; fi

  # let it get past startup before sampling (the 0->412 stall is a startup artefact)
  sleep 8
  local vals=()
  for i in $(seq 1 9); do
    local t
    t=$(curl -s -m 4 -u ":$PW" "http://127.0.0.1:$PORT/requests/status.json" \
        | python -c "import sys,json;print(json.load(sys.stdin).get('time'))" 2>/dev/null)
    vals+=("$t")
    sleep 3
  done
  echo "  clock: ${vals[*]}"

  python - "$label" "${vals[@]}" <<'PY'
import sys, statistics
label = sys.argv[1]
vals = []
for s in sys.argv[2:]:
    try: vals.append(float(s))
    except Exception: pass
if len(vals) < 3:
    print("  VERDICT: not enough samples"); raise SystemExit
deltas = [vals[i+1]-vals[i] for i in range(len(vals)-1)]
resets = sum(1 for d in deltas if d < -5)

# A MEAN advance is the wrong statistic here and produced nonsense: a trace of
# 617 650 654 657 165 1060 1407 1749 averages to "+180s per 3s sample -> 60x realtime",
# which reads as "perfect" for a stream that is visibly stuttering. Catch-up jumps after a
# reset and fast-forward bursts both inflate the mean. Measure STEADINESS instead: with 3s
# sampling, healthy realtime playback advances ~3s per sample. Count how many samples
# actually did that.
NEAR = sum(1 for d in deltas if 2.0 <= d <= 4.5)
med = statistics.median(deltas)
print(f"  deltas: {[round(d,1) for d in deltas]}")
print(f"  resets {resets}   out-of-band jumps {sum(1 for d in deltas if d > 4.5)}")
print(f"  median advance {med:.1f}s per 3s sample")
print(f"  samples at ~realtime (2-4.5s): {NEAR}/{len(deltas)}")
verdict = ("PLAYABLE" if NEAR >= len(deltas) - 1 and resets == 0 else
           "CHOPPY/UNSTABLE" if NEAR >= 1 or resets else "TOO SLOW / STALLED")
print(f"  VERDICT: {verdict}")
PY
  MSYS_NO_PATHCONV=1 taskkill /PID $vpid /T /F >/dev/null 2>&1
  sleep 3
}

measure 0  "auto (current default)"
measure 16 "all 16 logical cores"

echo
echo "DONE"
