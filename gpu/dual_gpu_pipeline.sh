#!/usr/bin/env bash
# dual_gpu_pipeline.sh — verified cross-GPU encode/decode for AMD Vega iGPU + NVIDIA GTX 1660 Ti.
#
# Device indices on this box (confirmed by ffmpeg accepting them and by the outputs decoding):
#     cuda:0     = NVIDIA GeForce GTX 1660 Ti
#     d3d11va:1  = AMD Radeon Vega iGPU
#
# Directions, all measured on 2026-10-10:
#
#   A  nv_decode_amd_encode   NVIDIA NVDEC/CUDA decode -> AMD AMF encode       WORKS
#   B  amd_decode_nv_encode   AMD d3d11va decode -> NVIDIA NVENC encode       WORKS
#   C  nv_decode_nv_encode    NVIDIA end to end (smallest CPU involvement)    WORKS
#   D  amd_only               AMD decode + AMD encode                         WORKS
#
# WHAT FAILS AND WHY (do not re-derive):
#   * NVENC refuses to open while frames are still bound to the AMD d3d11 device:
#     "OpenEncodeSessionEx failed: no encode device (1)". The frames must first be moved to
#     system memory and re-uploaded to the CUDA device.
#   * `hwdownload` after a CUDA decode WORKS. `hwdownload` after a `d3d11va` decode, with a
#     CUDA filter device active, fails with the confusing
#         "Impossible to convert between the formats supported by the filter"  src: nv12 dst: nv12
#     The fix is NOT to re-upload by hand — it is to set the filter device with
#     `-filter_hw_device <cuda-alias>` and let `hwupload` derive the CUDA device. That is what
#     direction B below does.
#   * The filter is spelled `derive_device` (a real hwupload AVOption). `derived_device` and
#     `extra_hw_frames` as hwupload options are NOT valid and fail with "Option not found".
#   * `-hwaccel*` and `-init_hw_device` MUST precede `-i`; filters and encoders must follow it.
#
# Usage:  dual_gpu_pipeline.sh <A|B|C|D> <input> <output> [start_seconds] [duration_seconds]
set -uo pipefail

FF="${FFMPEG:-/c/Users/sirch/AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin/ffmpeg.exe}"
PROBE="${FFPROBE:-/c/Users/sirch/AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin/ffprobe.exe}"

MODE="${1:-}"; IN="${2:-}"; OUT="${3:-}"; SS="${4:-0}"; T="${5:-}"

if [ -z "$MODE" ] || [ -z "$IN" ] || [ -z "$OUT" ]; then
  sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
fi
[ -f "$IN" ] || { echo "no such input: $IN"; exit 2; }

# quote a Windows-style path for ffmpeg's -ss/-t are numeric; paths carry backslashes safely
INW="$(cygpath -m "C:${IN#/c}" 2>/dev/null || echo "$IN")"
OUTW="$(cygpath -m "C:${OUT#/c}" 2>/dev/null || echo "$OUT")"

RANGE=()
[ "$SS" != "0" ] && RANGE+=(-ss "$SS")
[ -n "$T" ] && RANGE+=(-t "$T")

AMF='-c:v h264_amf -b:v 6M -quality quality'
NVENC='-c:v h264_nvenc -preset p5 -b:v 6M'
# NOTE: -hwaccel/-init_hw_device must precede -i, so each mode below assembles its own
# pre-input half rather than sharing one. Sharing a COMMON that already contains -i is exactly
# how mode A silently degraded to "cannot be applied to output url" the first time.

START=$(date +%s%3N)
case "$MODE" in
  A)  # NVIDIA decode -> AMD encode   (frames come home via hwdownload, AMF uploads internally)
      "$FF" -y -hide_banner -v error \
        -hwaccel cuda -hwaccel_output_format cuda \
        "${RANGE[@]}" -i "$INW" \
        -vf "scale_cuda=1920:1080:format=nv12,hwdownload,format=nv12" \
        -c:v h264_amf -b:v 6M -quality quality -c:a copy "$OUTW"
      ;;
  B)  # AMD decode -> NVIDIA encode   (filter device is CUDA; hwupload re-homes the frames)
      "$FF" -y -hide_banner -v error \
        -init_hw_device d3d11va=amd:1 -init_hw_device cuda=nv_gpu \
        -hwaccel d3d11va -hwaccel_device amd -hwaccel_output_format d3d11 \
        "${RANGE[@]}" -i "$INW" \
        -filter_hw_device nv_gpu -vf "hwdownload,format=nv12,hwupload" \
        -c:v h264_nvenc -preset p5 -b:v 6M -c:a copy "$OUTW"
      ;;
  C)  # NVIDIA end to end
      "$FF" -y -hide_banner -v error \
        -hwaccel cuda -hwaccel_output_format cuda \
        "${RANGE[@]}" -i "$INW" \
        -vf "scale_cuda=1920:1080:format=nv12" \
        -c:v h264_nvenc -preset p5 -b:v 6M -c:a copy "$OUTW"
      ;;
  D)  # AMD only
      "$FF" -y -hide_banner -v error \
        "${RANGE[@]}" -i "$INW" \
        -c:v h264_amf -b:v 6M -quality quality -c:a copy "$OUTW"
      ;;
  *)  echo "unknown mode '$MODE' (expected A|B|C|D)"; exit 2 ;;
esac
RC=$?
END=$(date +%s%3N)

echo "mode $MODE : rc=$RC  wall=$((END-START)) ms"
if [ -s "$OUTW" ]; then
  ls -la "$OUTW" | awk '{print "  size:",$5}'
  "$PROBE" -v error -show_entries stream=codec_name,width,height \
    -show_entries format=duration -of default=noprint_wrappers=1 "$OUTW" | sed 's/^/  /'
else
  echo "  NO OUTPUT PRODUCED"
fi
exit $RC
