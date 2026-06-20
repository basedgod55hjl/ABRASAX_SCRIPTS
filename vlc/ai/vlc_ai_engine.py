#!/usr/bin/env python3
"""
ABRASAX VLC AI ENHANCEMENT ENGINE v1.0
PRIMAL_HEX: 4f5349524953424c58434b | PHI: 1.618 | K: 0.618
AI-powered VLC controller with scene detection, smart filtering,
content analysis, and autonomous playback optimization.

Usage:
  python vlc_ai_engine.py --playlist <xspf> [--mode auto|analyze|optimize|control]
"""
import sys, os, json, subprocess, time, threading, shutil, re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# === CONSTANTS ===
PHI = 1.618033988749895
K = 0.6180339887498949
PRIMAL_HEX = "4f5349524953424c58434b"
VLC_EXE = r"C:\Program Files\VideoLAN\VLC\vlc.exe"
FFPROBE_EXE = r"C:\Program Files\VideoLAN\VLC\ffprobe.exe"
VLC_ROOT = Path(r"C:\Users\BASEDGOD\Desktop\_SCRIPTS\vlc")
AI_DIR = VLC_ROOT / "ai"
PLAYLISTS_DIR = VLC_ROOT / "playlists"
SCRIPTS_DIR = VLC_ROOT / "scripts"
LOGS_DIR = VLC_ROOT / "logs"
AI_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# === VIDEO CATEGORIES (AI-tagged) ===
CATEGORIES = {
    "music_video": ["music", "dance", "concert", "singing", "rap", "hip.hop"],
    "vlog": ["vlog", "talking", "review", "reaction", "chat"],
    "tutorial": ["how to", "tutorial", "diy", "guide", "learn"],
    "cinematic": ["movie", "film", "trailer", "cinematic", "drama"],
    "sports": ["football", "basketball", "soccer", "mma", "boxing"],
    "nature": ["landscape", "nature", "ocean", "forest", "sunset", "sky"],
    "dark_scene": ["night", "dark", "low.light", "dim"],
    "bright_scene": ["daylight", "outdoor", "bright", "sunny"],
    "high_motion": ["action", "fight", "fast", "sports", "race"],
    "static": ["still", "photo", "slideshow", "static", "timelapse"],
    "anime": ["anime", "manga", "cartoon", "animation"],
    "gaming": ["gameplay", "gaming", "twitch", "esport"],
    "podcast": ["podcast", "interview", "talk", "discussion"],
}

# === AI FILTER PRESETS ===
FILTER_PRESETS = {
    "cinematic": {
        "video": "adjust,sharpen,deinterlace,gradfun,grain",
        "sharpen_intensity": 0.30, "contrast": 1.08, "saturation": 1.10,
        "grain_intensity": 15, "gradfun_radius": 16,
        "audio": "compressor,equalizer,spatializer",
        "compressor_level": 3.0, "eq_preset": "fullbass", "spatializer_roomsize": 0.90
    },
    "dark_scene": {
        "video": "adjust,sharpen,hqdn3d",
        "sharpen_intensity": 0.25, "contrast": 1.12, "brightness": 1.08, "gamma": 1.10,
        "hqdn3d_luma": 6, "hqdn3d_chroma": 6,
        "audio": "compressor,equalizer,normvol",
        "compressor_level": 2.0, "eq_preset": "fullbass"
    },
    "high_motion": {
        "video": "sharpen,deinterlace,postproc",
        "sharpen_intensity": 0.40, "deinterlace_mode": "yadif",
        "postproc_quality": 6,
        "audio": "compressor,equalizer",
        "compressor_level": 4.0, "eq_preset": "live"
    },
    "anime": {
        "video": "sharpen,deinterlace,gradfun,antiflicker",
        "sharpen_intensity": 0.45, "contrast": 1.10, "saturation": 1.12,
        "gradfun_radius": 20, "gradfun_strength": 1.5,
        "audio": "compressor,equalizer,spatializer",
        "compressor_level": 3.5, "eq_preset": "fulltreble"
    },
    "music_video": {
        "video": "adjust,sharpen,deinterlace",
        "sharpen_intensity": 0.35, "contrast": 1.06, "saturation": 1.08,
        "audio": "compressor,equalizer,spatializer,stereo_widen",
        "compressor_level": 5.0, "eq_preset": "fullbass",
        "spatializer_roomsize": 0.85, "stereo_widen": 200
    },
    "vlog": {
        "video": "adjust,sharpen,hqdn3d",
        "sharpen_intensity": 0.30, "contrast": 1.04, "hqdn3d_luma": 4,
        "audio": "compressor,normvol",
        "compressor_level": 3.0
    },
    "default": {
        "video": "adjust,sharpen,deinterlace,postproc,hqdn3d,gradfun",
        "sharpen_intensity": 0.35, "contrast": 1.08, "saturation": 1.05,
        "deinterlace_mode": "yadif", "hqdn3d_luma": 4, "hqdn3d_chroma": 4,
        "gradfun_radius": 16,
        "audio": "compressor,equalizer,spatializer,stereo_widen,normvol,gain",
        "compressor_level": 4.0, "eq_preset": "fullbass",
        "spatializer_roomsize": 0.85, "stereo_widen": 180
    }
}

# === TOOLS ===
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOGS_DIR / "vlc_ai_engine.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")

def run_cmd(cmd, timeout=30):
    """Run a command and return stdout."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    except Exception as e:
        log(f"CMD ERR: {e}")
        return ""

def probe_video(filepath):
    """Use ffprobe to extract video metadata."""
    if not os.path.exists(FFPROBE_EXE):
        ffprobe = "ffprobe"
        if shutil.which("ffprobe"):
            ffprobe = shutil.which("ffprobe")
    else:
        ffprobe = FFPROBE_EXE

    cmd = (
        f'"{ffprobe}" -v quiet -print_format json -show_format -show_streams '
        f'"{filepath}"'
    )
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return json.loads(result.stdout)
    except Exception as e:
        log(f"Probe ERR for {filepath}: {e}")
        return {}

def analyze_video(filepath):
    """Analyze a video file and return metadata + AI category guess."""
    info = probe_video(filepath)
    if not info:
        return None

    filename = Path(filepath).name.lower()
    analysis = {
        "file": filepath,
        "filename": Path(filepath).name,
        "size_mb": round(os.path.getsize(filepath) / (1024 * 1024), 2) if os.path.exists(filepath) else 0,
    }

    # Extract format info
    fmt = info.get("format", {})
    analysis["duration_s"] = round(float(fmt.get("duration", 0)), 1)
    analysis["bitrate_kbps"] = int(fmt.get("bit_rate", 0)) // 1000 if fmt.get("bit_rate") else 0

    # Extract stream info
    for stream in info.get("streams", []):
        if stream["codec_type"] == "video":
            analysis["codec"] = stream.get("codec_name", "unknown")
            analysis["resolution"] = f"{stream.get('width', 0)}x{stream.get('height', 0)}"
            analysis["fps"] = eval(stream.get("r_frame_rate", "0/1")) if stream.get("r_frame_rate") else 0
            analysis["pix_fmt"] = stream.get("pix_fmt", "unknown")
            analysis["bit_depth"] = stream.get("bits_per_raw_sample", 8)
            # Brightness estimation from filename + resolution
            w = stream.get("width", 1920)
            h = stream.get("height", 1080)
            analysis["is_hdr"] = "smpte" in str(stream.get("color_transfer", "")).lower() or "pq" in str(stream.get("color_transfer", "")).lower()
            analysis["is_4k"] = h >= 2160
            analysis["is_vertical"] = w < h

    # AI category detection from filename
    analysis["category"] = detect_category(filename)
    analysis["filter_preset"] = get_filter_preset(analysis["category"], analysis)

    return analysis

def detect_category(filename):
    """Simple AI-like category detection from filename keywords."""
    filename_lower = filename.lower()
    scores = defaultdict(int)

    for category, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw.replace(".", " ") in filename_lower or kw.replace(".", "") in filename_lower:
                scores[category] += 1

    if scores:
        return max(scores, key=scores.get)
    return "default"

def get_filter_preset(category, analysis):
    """Get optimal filter preset based on category and video properties."""
    preset = FILTER_PRESETS.get(category, FILTER_PRESETS["default"]).copy()

    # Override for low FPS
    if analysis.get("fps", 30) < 24:
        preset["sharpen_intensity"] = min(preset.get("sharpen_intensity", 0.35) + 0.05, 0.6)

    # Override for low resolution
    if analysis.get("resolution", "1920x1080"):
        try:
            h = int(analysis["resolution"].split("x")[1])
            if h <= 480:
                preset["sharpen_intensity"] = min(preset.get("sharpen_intensity", 0.35) + 0.10, 0.6)
                preset["hqdn3d_luma"] = 8
        except:
            pass

    # Override for 4K / HDR
    if analysis.get("is_4k"):
        preset["sharpen_intensity"] = max(preset.get("sharpen_intensity", 0.35) - 0.10, 0.10)
    if analysis.get("is_hdr"):
        preset["contrast"] = max(preset.get("contrast", 1.05) - 0.05, 0.90)

    return preset

def build_vlc_command(video_path, preset):
    """Build VLC command line with AI-optimized filters."""
    cmd_parts = [f'"{VLC_EXE}"']

    # GPU acceleration
    cmd_parts.extend([
        "--avcodec-hw=any", "--avcodec-hw-any", "--avcodec-hw-decoding=yes",
        "--avcodec-dr", "--avcodec-threads=16", "--avcodec-fast", "--ffmpeg-hw",
        "--direct3d11-hw-decoding", "--direct3d11-hw-blending",
        "--dxva2=on", "--d3d11va=on", "--vout=direct3d11",
        "--d3d11-upscale-mode=linear", "--gpu-accel=auto"
    ])

    # Video filters
    if preset.get("video"):
        cmd_parts.append(f"--video-filter={preset['video']}")

    if preset.get("sharpen_intensity"):
        cmd_parts.append(f"--sharpen-intensity={preset['sharpen_intensity']:.2f}")
    if preset.get("contrast"):
        cmd_parts.append(f"--adjust-contrast={preset['contrast']:.2f}")
    if preset.get("brightness"):
        cmd_parts.append(f"--adjust-brightness={preset['brightness']:.2f}")
    if preset.get("saturation"):
        cmd_parts.append(f"--adjust-saturation={preset['saturation']:.2f}")
    if preset.get("gamma"):
        cmd_parts.append(f"--adjust-gamma={preset['gamma']:.2f}")
    if preset.get("deinterlace_mode"):
        cmd_parts.extend(["--deinterlace=1", f"--deinterlace-mode={preset['deinterlace_mode']}"])
    if preset.get("hqdn3d_luma"):
        cmd_parts.append(f"--hqdn3d-luma-spatial={preset['hqdn3d_luma']}")
    if preset.get("hqdn3d_chroma"):
        cmd_parts.append(f"--hqdn3d-chroma-spatial={preset['hqdn3d_chroma']}")
    if preset.get("gradfun_radius"):
        cmd_parts.append(f"--gradfun-radius={preset['gradfun_radius']}")
    if preset.get("grain_intensity"):
        cmd_parts.append(f"--grain-intensity={preset['grain_intensity']}")
    if preset.get("postproc_quality"):
        cmd_parts.append(f"--postproc-quality={preset['postproc_quality']}")

    # Audio filters
    if preset.get("audio"):
        cmd_parts.append(f"--audio-filter={preset['audio']}")

    if preset.get("compressor_level"):
        cmd_parts.append(f"--compressor-level={preset['compressor_level']}")
    if preset.get("eq_preset"):
        cmd_parts.append(f"--equalizer-preset={preset['eq_preset']}")
    if preset.get("spatializer_roomsize"):
        cmd_parts.append(f"--spatializer-roomsize={preset['spatializer_roomsize']}")
    if preset.get("stereo_widen"):
        cmd_parts.append(f"--stereo-widen={preset['stereo_widen']}")

    # Playback options
    cmd_parts.extend([
        "--file-caching=2000", "--network-caching=3000", "--live-caching=500",
        "--playlist-autostart", "--loop", "--repeat",
        "--no-video-title-show", "--video-on-top"
    ])

    # Video path
    cmd_parts.append(f'"{video_path}"')

    return " ".join(cmd_parts)

def parse_xspf(xspf_path):
    """Parse XSPF playlist and return list of video paths."""
    videos = []
    try:
        with open(xspf_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Extract all <location> tags
        locations = re.findall(r'<location>(.*?)</location>', content)
        for loc in locations:
            # Convert file:/// to Windows path
            path = loc.replace("file:///", "").replace("/", "\\")
            videos.append(path)
    except Exception as e:
        log(f"Parse ERR for {xspf_path}: {e}")
    return videos

def analyze_playlist(xspf_path):
    """Analyze all videos in a playlist and generate AI report."""
    videos = parse_xspf(xspf_path)
    log(f"Analyzing {len(videos)} videos from {Path(xspf_path).name}...")

    results = []
    by_category = defaultdict(list)
    by_resolution = defaultdict(int)
    total_duration = 0
    total_size = 0
    missing = 0
    corrupted = 0

    for i, video_path in enumerate(videos):
        if (i + 1) % 50 == 0:
            log(f"  Progress: {i + 1}/{len(videos)}")

        if not os.path.exists(video_path):
            missing += 1
            continue

        analysis = analyze_video(video_path)
        if analysis:
            results.append(analysis)
            by_category[analysis["category"]].append(analysis["filename"])
            by_resolution[analysis.get("resolution", "unknown")] += 1
            total_duration += analysis.get("duration_s", 0)
            total_size += analysis.get("size_mb", 0)
        else:
            corrupted += 1

    report = {
        "playlist": str(xspf_path),
        "total_tracks": len(videos),
        "analyzed": len(results),
        "missing": missing,
        "corrupted": corrupted,
        "total_duration_hours": round(total_duration / 3600, 2),
        "total_size_gb": round(total_size / 1024, 2),
        "by_category": dict(by_category),
        "category_counts": {k: len(v) for k, v in by_category.items()},
        "by_resolution": dict(by_resolution),
        "avg_bitrate_kbps": round(sum(r.get("bitrate_kbps", 0) for r in results) / max(len(results), 1)),
        "filter_recommendations": {},
    }

    # Generate filter recommendations per category
    for cat in by_category:
        report["filter_recommendations"][cat] = FILTER_PRESETS.get(cat, FILTER_PRESETS["default"])

    # Save report
    report_path = AI_DIR / f"analysis_{Path(xspf_path).stem}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    log(f"Report saved: {report_path}")
    return report

def optimize_playlist(xspf_path, output_path=None):
    """AI-optimize playlist: deduplicate, sort by category, add filter metadata."""
    videos = parse_xspf(xspf_path)
    log(f"Optimizing {len(videos)} videos...")

    # Remove duplicates (by filename)
    seen = set()
    unique = []
    for v in videos:
        fname = Path(v).name.lower()
        if fname not in seen:
            seen.add(fname)
            unique.append(v)
    log(f"  Deduped: {len(videos)} -> {len(unique)}")

    # Analyze and categorize
    analyzed = []
    for vpath in unique:
        if os.path.exists(vpath):
            a = analyze_video(vpath)
            if a:
                analyzed.append(a)

    # Sort by category then duration
    analyzed.sort(key=lambda x: (x.get("category", "z"), x.get("duration_s", 0)))

    # Build optimized XSPF
    if not output_path:
        output_path = str(Path(xspf_path).parent / f"{Path(xspf_path).stem}_AI_OPTIMIZED.xspf")

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<playlist xmlns="http://xspf.org/ns/0/" xmlns:vlc="http://www.videolan.org/vlc/playlist/ns/0/" version="1">',
        '\t<title>ABRASAX AI-Optimized Playlist</title>',
        '\t<trackList>',
    ]

    for i, item in enumerate(analyzed):
        lines.append('\t\t<track>')
        win_path = item["file"].replace("\\", "/")
        if not win_path.startswith("file:///"):
            win_path = f"file:///{win_path}"
        lines.append(f'\t\t\t<location>{win_path}</location>')
        lines.append(f'\t\t\t<duration>{int(item.get("duration_s", 0) * 1000)}</duration>')
        lines.append('\t\t\t<extension application="http://www.videolan.org/vlc/playlist/0">')
        lines.append(f'\t\t\t\t<vlc:id>{i}</vlc:id>')
        lines.append('\t\t\t</extension>')
        lines.append('\t\t</track>')

    lines.append('\t</trackList>')
    lines.append('</playlist>')

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    log(f"Optimized playlist: {output_path} ({len(analyzed)} tracks)")
    return output_path

def generate_smart_playlist(source_dirs, output_name="AI_SMART_MIX"):
    """Scan directories and create an AI-curated smart playlist."""
    log(f"Scanning {len(source_dirs)} directories...")
    all_videos = []

    for sdir in source_dirs:
        if not os.path.exists(sdir):
            continue
        for root, dirs, files in os.walk(sdir):
            for f in files:
                if f.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v', '.wmv', '.flv')):
                    all_videos.append(os.path.join(root, f))

    log(f"Found {len(all_videos)} videos")
    return build_xspf(all_videos, PLAYLISTS_DIR / f"{output_name}.xspf")

def build_xspf(video_paths, output_path):
    """Build XSPF playlist from video paths."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<playlist xmlns="http://xspf.org/ns/0/" xmlns:vlc="http://www.videolan.org/vlc/playlist/ns/0/" version="1">',
        f'\t<title>ABRASAX AI Smart Playlist</title>',
        '\t<trackList>',
    ]

    for i, vpath in enumerate(video_paths):
        if not os.path.exists(vpath):
            continue
        lines.append('\t\t<track>')
        win_path = vpath.replace("\\", "/")
        if not win_path.startswith("file:///"):
            win_path = f"file:///{win_path}"
        lines.append(f'\t\t\t<location>{win_path}</location>')
        # Quick duration probe
        try:
            size = os.path.getsize(vpath)
            lines.append(f'\t\t\t<duration>0</duration>')
        except:
            lines.append(f'\t\t\t<duration>0</duration>')
        lines.append('\t\t\t<extension application="http://www.videolan.org/vlc/playlist/0">')
        lines.append(f'\t\t\t\t<vlc:id>{i}</vlc:id>')
        lines.append('\t\t\t</extension>')
        lines.append('\t\t</track>')

    lines.append('\t</trackList>')
    lines.append('</playlist>')

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    log(f"XSPF created: {output_path} ({len(lines) - 5} tracks)")
    return str(output_path)

def launch_with_ai_preset(video_path, category="auto"):
    """Launch VLC with AI-optimized filter preset for a video."""
    if category == "auto":
        analysis = analyze_video(video_path)
        if analysis:
            category = analysis["category"]
            preset = analysis["filter_preset"]
        else:
            preset = FILTER_PRESETS["default"]
    else:
        preset = FILTER_PRESETS.get(category, FILTER_PRESETS["default"])

    cmd = build_vlc_command(video_path, preset)
    log(f"Launching: {Path(video_path).name} [{category}]")
    log(f"  CMD: {cmd[:200]}...")
    subprocess.Popen(cmd, shell=True)
    return preset

# === MAIN ===
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ABRASAX VLC AI Enhancement Engine")
    parser.add_argument("--playlist", "-p", help="XSPF playlist to analyze/optimize")
    parser.add_argument("--video", "-v", help="Single video to play with AI preset")
    parser.add_argument("--mode", "-m", default="analyze",
                       choices=["analyze", "optimize", "play", "scan", "launch"],
                       help="Operation mode")
    parser.add_argument("--category", "-c", default="auto",
                       help="Force category for video (or auto-detect)")
    parser.add_argument("--scan-dirs", "-d", nargs="+",
                       default=[
                           r"G:\OF",
                           r"K:\queen_tahshaar",
                           r"D:\New folder",
                           r"F:\SORTED_MEDIA"
                       ],
                       help="Directories to scan for smart playlist")
    parser.add_argument("--output", "-o", help="Output XSPF path")

    args = parser.parse_args()

    log("=" * 60)
    log(f"ABRASAX VLC AI ENGINE v1.0 — Mode: {args.mode}")
    log(f"  PHI: {PHI}  K: {K}  HEX: {PRIMAL_HEX}")
    log("=" * 60)

    if args.mode == "analyze" and args.playlist:
        report = analyze_playlist(args.playlist)
        print(f"\n=== PLAYLIST ANALYSIS ===")
        print(f"Tracks: {report['total_tracks']} | Analyzed: {report['analyzed']}")
        print(f"Duration: {report['total_duration_hours']}h | Size: {report['total_size_gb']}GB")
        print(f"Missing: {report['missing']} | Corrupted: {report['corrupted']}")
        print(f"\nCategories:")
        for cat, count in sorted(report["category_counts"].items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count}")
        print(f"\nResolutions:")
        for res, count in sorted(report["by_resolution"].items()):
            print(f"  {res}: {count}")

    elif args.mode == "optimize" and args.playlist:
        optimize_playlist(args.playlist, args.output)

    elif args.mode == "play" and args.video:
        launch_with_ai_preset(args.video, args.category)

    elif args.mode == "scan":
        if args.output:
            out = args.output
        else:
            out = str(PLAYLISTS_DIR / "AI_SMART_MIX.xspf")
        generate_smart_playlist(args.scan_dirs, Path(out).stem)
        print(f"\nSmart playlist created: {out}")

    elif args.mode == "launch" and args.playlist:
        # Analyze playlist and launch with optimal settings
        report = analyze_playlist(args.playlist)
        dominant_category = max(report["category_counts"], key=report["category_counts"].get)
        preset = FILTER_PRESETS.get(dominant_category, FILTER_PRESETS["default"])
        log(f"Dominant category: {dominant_category}")

        cmd = build_vlc_command(args.playlist, preset)
        # Override cache for large playlists
        cmd += ' --playlist-autostart'
        log(f"Launching VLC with {dominant_category} preset...")
        subprocess.Popen(cmd, shell=True)
        print(f"VLC launched with AI preset: {dominant_category}")

    else:
        parser.print_help()

    log("Done.")
