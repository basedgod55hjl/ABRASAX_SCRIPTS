#!/usr/bin/env bash
# vlc_ctl.sh — one entry point for everything we know how to do to VLC on this box.
#
# Subcommands:
#   status            what is playing, on which GPU, which control interfaces are up
#   reload [xspf]     restart VLC and restore the exact item + position (position-preserving)
#   av1 [path...]     report the video codec of files (default: the live playlist) - flags AV1
#   crystal [n]       run the GPU crystal kernels on live frames from what VLC is playing
#   doctor            full health check: config, GPU routing, interfaces, decode path
#
# Everything here is read-only except `reload`, which stops and restarts vlc.exe.
set -uo pipefail

HOME_VLC="/c/Users/sirch/AppData/Roaming/vlc"
VLCRC="$HOME_VLC/vlcrc"
API="http://127.0.0.1:8080/requests/status.json"
SCRIPTS="/c/Users/sirch/Desktop/ABRASAX_GOD_OS/agents/ABRASAX_SCRIPTS/vlc/scripts"
CRYSTAL="/c/Users/sirch/Desktop/ABRASAX_GOD_OS/build/crystal_dll/vlc_crystal_live.py"
FFPROBE="/c/Users/sirch/AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin/ffprobe.exe"
VLC_EXE="C:/Program Files/VideoLAN/VLC/vlc.exe"

pw() { grep -E '^http-password=' "$VLCRC" 2>/dev/null | cut -d= -f2-; }
api() { curl -s -m 6 -u ":$PW_VAL" "$API"; }
get() { api | python -c "import sys,json;d=json.load(sys.stdin);print(d.get('$1'))" 2>/dev/null; }

cmd_status() {
  PW_VAL=$(pw)
  echo "== VLC status =="
  local n
  n=$(MSYS_NO_PATHCONV=1 tasklist /FI "IMAGENAME eq vlc.exe" 2>/dev/null | grep -ci "vlc.exe")
  echo "  processes: $n"
  if [ "$n" = "0" ]; then echo "  (not running)"; return; fi
  api | python -c "
import sys,json
d=json.load(sys.stdin)
m=d.get('information',{}).get('category',{}).get('meta',{})
print('  state :',d.get('state'))
print('  plid  :',d.get('currentplid'))
print('  time  : %s / %s' % (d.get('time'),d.get('length')))
print('  file  :',m.get('filename'))
" 2>/dev/null || echo "  (HTTP not answering yet - the Lua handler starts after the port opens)"
  local gl
  gl=$(MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "(Get-ItemProperty 'HKCU:\Software\Microsoft\DirectX\UserGpuPreferences' -ErrorAction SilentlyContinue).'C:\Program Files\VideoLAN\VLC\vlc.exe'" 2>/dev/null | tr -d '\r')
  echo "  gpu   : ${gl:-<default>}   (GpuPreference=1 AMD iGPU, 2 NVIDIA dGPU)"
  echo "  nvidia decoder: $(MSYS_NO_PATHCONV=1 nvidia-smi --query-gpu=utilization.decoder --format=csv,noheader 2>/dev/null)  (0% while playing => decode is on the iGPU)"
}

cmd_reload() {
  echo "== reloading VLC (preserving item + position) =="
  bash "$SCRIPTS/vlc_reload_resume.sh" "${1:-}"
}

cmd_av1() {
  echo "== codec check =="
  local -a files=("$@")
  if [ "${#files[@]}" -eq 0 ]; then
    PW_VAL=$(pw)
    # pull the live playlist and check the first N entries that exist on disk
    mapfile -t files < <(curl -s -m 25 -u ":$PW_VAL" "http://127.0.0.1:8080/requests/playlist.json" 2>/dev/null | python -c "
import sys, json, os
t=json.load(sys.stdin); out=[]
def walk(n):
    u=n.get('uri') or ''
    if u.startswith('file:///'):
        p=u[8:].replace('/', os.sep)
        try:
            import urllib.parse
            p=urllib.parse.unquote(p)
        except Exception: pass
        if os.path.exists(p): out.append(p)
    for c in n.get('children') or []: walk(c)
walk(t)
for p in out[:25]: print(p)
" 2>/dev/null)
  fi
  if [ "${#files[@]}" -eq 0 ]; then echo "  no files to check"; return; fi
  local av1=0 checked=0
  for f in "${files[@]}"; do
    [ -f "$f" ] || continue
    local c
    c=$(MSYS_NO_PATHCONV=1 "$FFPROBE" -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$f" 2>/dev/null | head -1)
    checked=$((checked+1))
    if [ "$c" = "av1" ]; then
      av1=$((av1+1))
      printf "  AV1   <- will not hardware-decode  %s\n" "$(basename "$f")"
    fi
  done
  echo "  checked $checked, AV1 $av1"
  if [ "$av1" -gt 0 ]; then
    echo
    echo "  AV1 cannot hardware-decode on the GTX 1660 Ti (Turing has no AV1 decoder)."
    echo "  Options: (1) transcode once:  ffmpeg -i in.mp4 -c:v hevc_nvenc -preset p4 -cq 24 -c:a copy out.mp4"
    echo "           (2) try software decode:  vlc --avcodec-hw=none --dav1d-thread-frames=16 <file>"
  fi
}

cmd_crystal() {
  local n="${1:-2}"
  echo "== crystal kernels on live VLC frames ($n passes) =="
  MSYS_NO_PATHCONV=1 python "$CRYSTAL" --watch "$n" --interval 4
}

cmd_doctor() {
  PW_VAL=$(pw)
  echo "== VLC doctor =="
  echo "-- config --"
  # VLC's own save format writes every option and COMMENTS OUT any that sit at its default.
  # So a missing active line does NOT mean "unset" - it means "at default", and the commented
  # line right there records what that default is. Reporting "<not set>" here was misleading:
  # it made a perfectly configured VLC look broken.
  for k in avcodec-hw vout extraintf file-caching http-port telnet-port dav1d-thread-frames; do
    local a c
    a=$(grep -E "^$k=" "$VLCRC" 2>/dev/null | head -1)
    c=$(grep -E "^#$k=" "$VLCRC" 2>/dev/null | head -1)
    if [ -n "$a" ]; then
      printf "   %-22s %-28s (explicit)\n" "$k" "${a#*=}"
    elif [ -n "$c" ]; then
      printf "   %-22s %-28s (default)\n" "$k" "${c#\#*=}"
    else
      printf "   %-22s %-28s (not present)\n" "$k" "-"
    fi
  done
  echo "-- dangerous settings (must all be absent) --"
  for k in "video-filter=" "postproc-q=" "deinterlace=1" "gpu-yuv"; do
    if grep -qE "^${k}" "$VLCRC" 2>/dev/null; then printf "   %-22s PRESENT (should not be)\n" "$k"
    else printf "   %-22s absent ok\n" "$k"; fi
  done
  echo "-- interfaces --"
  local code
  code=$(curl -s -o /dev/null -m 4 -w '%{http_code}' -u ":$PW_VAL" "$API" 2>/dev/null)
  echo "   HTTP  : $code  (200 = up)"
  echo "   Telnet: $(MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "(Test-NetConnection -ComputerName 127.0.0.1 -Port 4212 -WarningAction SilentlyContinue).TcpTestSucceeded" 2>/dev/null | tr -d '\r') (True = up)"
  echo "-- GPU --"
  MSYS_NO_PATHCONV=1 nvidia-smi --query-gpu=name,utilization.gpu,utilization.decoder,memory.used --format=csv,noheader 2>/dev/null | sed 's/^/   /'
  cmd_status
}

case "${1:-status}" in
  status)  cmd_status ;;
  reload)  shift; cmd_reload "${1:-}" ;;
  av1)     shift; cmd_av1 "$@" ;;
  crystal) shift; cmd_crystal "${1:-2}" ;;
  doctor)  cmd_doctor ;;
  *) echo "usage: vlc_ctl.sh {status|reload [xspf]|av1 [file...]|crystal [n]|doctor}"; exit 2 ;;
esac
