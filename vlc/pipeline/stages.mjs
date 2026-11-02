// ============================================================================
// stages.mjs — concrete pipeline stages for the NVIDIA->AMD media pipeline
// Every command here was verified on this machine (2026-10-10).
// ============================================================================
import { execFile, execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, statSync } from 'node:fs';
import { promisify } from 'node:util';
import path from 'node:path';
import os from 'node:os';

const pexec = promisify(execFile);

export const FFMPEG = path.join(
  process.env.LOCALAPPDATA, 'hermes', 'tools', 'ffmpeg-9.0.1-win32-x64', 'bin', 'ffmpeg.exe');
export const NLM = path.join(os.homedir(), '.local', 'bin', 'nlm.exe');
export const OUTDIR = path.join(
  os.homedir(), 'Desktop', 'ABRASAX_GOD_OS', 'agents', 'ABRASAX_SCRIPTS', 'vlc', 'streamout');
export const RUST_DIR = path.join(
  os.homedir(), 'Desktop', 'ABRASAX_GOD_OS', 'repos', 'ABRASAX-7D-Crystal', 'kernels', 'rust');
export const KERNEL_DIR = path.join(os.homedir(), 'Desktop', 'ABRASAX_GOD_OS', 'build', 'cuda_kernels_hermes');

function ensureOut() { if (!existsSync(OUTDIR)) mkdirSync(OUTDIR, { recursive: true }); return OUTDIR; }

async function run(cmd, args, label, timeout = 900000, cwd = undefined) {
  const t0 = Date.now();
  try {
    const { stdout, stderr } = await pexec(cmd, args, { timeout, maxBuffer: 64 * 1024 * 1024, windowsHide: true, cwd });
    return { ok: true, ms: Date.now() - t0, out: (stdout + stderr).trim(), label };
  } catch (e) {
    return { ok: false, ms: Date.now() - t0, out: ((e.stdout || '') + (e.stderr || '') + e.message).trim().slice(0, 1500), label };
  }
}

// ---------------------------------------------------------------------------
// STAGE: video — NVIDIA decodes + enhances, AMD Radeon is the FINAL output
// ---------------------------------------------------------------------------
export const VIDEO_PRESETS = {
  // NVIDIA decode -> NVIDIA upscale -> hwdownload -> AMD AMF final encode   [1278 ms]
  amd_final_nvidia_enhanced: {
    note: 'NVIDIA decodes + scale_cuda 2x, AMD Vega performs the FINAL encode',
    pre: ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda'],
    post: ['-vf', 'scale_cuda=1088:1408:format=nv12,hwdownload,format=nv12',
           '-c:v', 'h264_amf', '-b:v', '6M', '-quality', 'quality'],
  },
  // AMD final output + shader upscale on the iGPU     [3721 ms]
  amd_final_libplacebo: {
    note: 'libplacebo upscale ON the Vega iGPU, AMD final encode',
    pre: ['-init_hw_device', 'vulkan=vk:1', '-filter_hw_device', 'vk'],
    post: ['-vf', 'libplacebo=w=1088:h=1408:upscaler=ewa_lanczos',
           '-c:v', 'h264_amf', '-b:v', '6M', '-quality', 'quality'],
  },
  // AMD final output, CPU denoise                     [674 ms]
  amd_final_cpu_denoise: {
    note: 'CPU hqdn3d denoise, AMD final encode (fastest full path)',
    pre: [],
    post: ['-vf', 'hqdn3d=4:3:6:4.5', '-c:v', 'h264_amf', '-b:v', '6M', '-quality', 'quality'],
  },
  // All NVIDIA, for comparison                        [1141 ms]
  nvidia_reference: {
    note: 'all-NVIDIA reference: decode + scale_cuda + NVENC',
    pre: ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda'],
    post: ['-vf', 'scale_cuda=1088:1408:format=nv12', '-c:v', 'h264_nvenc', '-b:v', '6M'],
  },
};

export async function stageVideo(presetName, input, { measure = false } = {}) {
  const p = VIDEO_PRESETS[presetName];
  if (!p) throw new Error(`unknown preset ${presetName}`);
  ensureOut();
  const base = path.basename(input, path.extname(input));
  const out = path.join(OUTDIR, `${base}-${presetName}.mp4`);
  const args = ['-hide_banner', '-loglevel', 'error'];
  if (measure) args.push('-benchmark');
  args.push('-y', ...p.pre, '-i', input, ...p.post, out);
  const r = await run(FFMPEG, args, `video:${presetName}`);
  r.outfile = out;
  r.bytes = existsSync(out) ? statSync(out).size : 0;
  r.note = p.note;
  return r;
}

// ---------------------------------------------------------------------------
// STAGE: gpu inventory — both GPUs, and which device index is which
// ---------------------------------------------------------------------------
export async function stageGpuInventory() {
  const r = await run(FFMPEG, ['-hide_banner', '-v', 'verbose', '-init_hw_device', 'vulkan',
                               '-f', 'lavfi', '-i', 'nullsrc', '-frames:v', '1', '-f', 'null', '-'],
                     'gpu:inventory', 120000);
  const devices = r.out.split('\n')
    .map(l => l.replace(/^\[Vulkan @ [0-9a-fx]+\]\s*/, '').trim())   // strip prefix FIRST
    .filter(l => /^GPU listing|^\d+:\s|Device \d selected/.test(l));
  return { ...r, devices };
}

// ---------------------------------------------------------------------------
// STAGE: CUDA kernels — recompile the enhanced color-conversion kernels
// ---------------------------------------------------------------------------
export async function stageBuildKernels() {
  const nvcc = 'nvcc';
  const results = [];
  for (const [src, out] of [['vlc_yuv_kernels.cu', 'vlc_yuv_kernels.cubin'],
                            ['vlc_yuv_kernels.cu', 'vlc_yuv_kernels.ptx']]) {
    const flag = out.endsWith('.ptx') ? '-ptx' : '-cubin';
    // cwd matters: nvcc resolves the source path relative to the child cwd
    results.push(await run(nvcc, ['-arch=sm_75', flag, src, '-o', out], `nvcc:${out}`, 300000, KERNEL_DIR));
  }
  const exe = await run(nvcc, ['-arch=sm_75', '-O2', 'harness_vlc_yuv.cu', '-o', 'vlc_yuv_test.exe'],
                        'nvcc:harness', 300000, KERNEL_DIR);
  results.push(exe);
  let runRes = null;
  if (exe.ok) runRes = await run(path.join(KERNEL_DIR, 'vlc_yuv_test.exe'), [], 'run:vlc_yuv_test', 300000, KERNEL_DIR);
  return { results, kernelRun: runRes };
}

// ---------------------------------------------------------------------------
// STAGE: Rust — cargo build the core + cuda-node
// ---------------------------------------------------------------------------
export async function stageBuildRust() {
  // Only the standalone crate here; cuda_node lives in the PARENT workspace and
  // is built separately by loki.mjs (running `-p cuda_node` from this dir would
  // just fail with "package not found in workspace").
  const core = await run('cargo', ['build'], 'cargo:abrasax_7d_core', 900000, RUST_DIR);
  return { core };
}

// ---------------------------------------------------------------------------
// STAGE: notebooks — ask every notebook, capture the answer
// ---------------------------------------------------------------------------
export async function stageNotebooks(question, tag = 'q') {
  const out = path.join(OUTDIR, `notebook-${tag}.txt`);
  const r = await run(NLM, ['cross', 'query', question, '--all'], `nlm:${tag}`, 1800000);
  const fs = await import('node:fs');
  fs.writeFileSync(out, r.out, 'utf8');
  return { ...r, outfile: out, answered: /notebooks responded/.exec(r.out)?.[0] || '?' };
}
