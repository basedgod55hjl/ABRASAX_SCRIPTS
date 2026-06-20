# ABRASAX VLC 7D Enhanced Player — Complete System

## System
- **CPU**: AMD Ryzen 7 4800H (8C/16T) @ 2.9GHz
- **GPU**: NVIDIA GeForce GTX 1660 Ti (6GB VRAM) — Turing NVENC/NVDEC
- **iGPU**: AMD Radeon Graphics
- **VLC**: 3.0.23 (Vetinari)

## Directory Structure
```
_SCRIPTS\vlc\
├── VLC_ABRASAX_LAUNCHER.bat  ← MASTER LAUNCHER (run this!)
├── VLC_MASTER.bat             ← Original master control
├── VLC_ULTIMATE.bat           ← ALL GPU + ALL filters maxed out
├── VLC_RELAUNCH_ENHANCED.bat  ← Auto-relaunch on close
├── scripts\                   ← Specialized launchers
│   ├── 7D_VRAM_PLAYER.bat     ← 555 playlist VRAM optimized
│   ├── ABRASAX_VLC_AI_ENHANCE.bat  ← AI enhancement loop
│   ├── ABRASAX_VLC_DUAL_MONITOR.bat  ← Dual screen
│   ├── ABRASAX_VLC_INFINITE_MONITOR.bat ← 24/7 never-stop
│   ├── LAUNCH_ALL_VLC_ENHANCED.bat ← Heterogeneous engine
│   ├── VLC_HW_ACCEL_MAX.bat   ← Pure hardware decode
│   └── VLC_NVENC_ENCODE.bat   ← GPU encoding
├── playlists\                  ← All XSPF playlists
│   ├── 46464.xspf              ← Top videos by duration
│   ├── ABRASAX_VLC_MASTER.xspf ← 804+ tracks from G:/OF
│   ├── ALL_VIDEOS_BY_DURATION_DEDUPED.xspf
│   ├── ALL_VIDEOS_MASTER.xspf
│   └── 555...xspf              ← VRAM optimized
├── config\                     ← VLC config files
├── docs\                       ← Documentation + analytics
├── ai\                         ← Python AI/consciousness scripts
├── logs\                       ← Runtime logs
├── thumbnails\                 ← Video snapshots
└── plugins\                    ← Plugin documentation
```

## GPU Acceleration (ALL available)
| Engine | Status | Description |
|--------|--------|-------------|
| D3D11VA | 🟢 | Direct3D11 Video Acceleration |
| DXVA2 | 🟢 | DirectX Video Acceleration 2 |
| NVDEC | 🟢 | NVIDIA Pure Hardware Decode |
| NVENC | 🟢 | NVIDIA Turing Encoder (H.264/H.265) |
| OpenGL | 🟢 | OpenGL rendering fallback |
| FFmpeg HW | 🟢 | Software + hardware bridge |

## Available Video Filters (41 DLLs)
`adjust`, `alphamask`, `anaglyph`, `antiflicker`, `ball`, `blend`, `bluescreen`, `canvas`, `colorthres`, `croppadd`, `deinterlace`, `edgedetection`, `erase`, `extract`, `fps`, `freeze`, `gaussianblur`, `gradfun`, `gradient`, `grain`, `hqdn3d`, `invert`, `magnify`, `mirror`, `motionblur`, `motiondetect`, `oldmovie`, `posterize`, `postproc`, `psychedelic`, `puzzle`, `ripple`, `rotate`, `scale`, `scene`, `sepia`, `sharpen`, `transform`, `vhs`, `wave`

## Available Audio Filters (25 DLLs)
`audiobargraph_a`, `audio_format`, `chorus_flanger`, `compressor`, `dolby_surround_decoder`, `equalizer`, `gain`, `headphone_channel_mixer`, `karaoke`, `mad`, `mono`, `normvol`, `param_eq`, `remap`, `samplerate`, `scaletempo_pitch`, `scaletempo`, `simple_channel_mixer`, `spatialaudio`, `spatializer`, `speex_resampler`, `stereo_widen`, `tospdif`, `trivial_channel_mixer`, `ugly_resampler`

## Available Codecs
**Video decode**: H.264 (x264/10b), H.265/HEVC (x265), VP9 (vpx), AV1 (dav1d/aom), MPEG-2 (libmpeg2), Theora, WMV (dmo), JPEG/MJPEG, PNG, WebP, CDG, CrystalHD
**Audio decode**: MP3 (mpg123), AAC (faad), FLAC, Opus, Vorbis, Speex, DTS (dca), AC3 (a52), LPCM, ADPCM, G.711
**HW accel**: D3D11VA, DXVA2, QSV (Intel), MFT (Windows Media Foundation)

## LUA Extensions
- `VLSub.luac` — Subtitle downloader
- HTTP interface, Telnet, CLI, Dummy, Dumpmeta

## Quick Launch (from anywhere)
Just double-click `_SCRIPTS\vlc\VLC_ABRASAX_LAUNCHER.bat` or run:
```cmd
C:\Users\BASEDGOD\Desktop\_SCRIPTS\vlc\VLC_ABRASAX_LAUNCHER.bat
```

## PRIMAL HEX
`4f5349524953424c58434b` | φ = 1.618033988749895
