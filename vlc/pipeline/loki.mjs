#!/usr/bin/env node
// ============================================================================
// loki.mjs — the ABRASAX "query -> build -> repeat" pipeline orchestrator
// ----------------------------------------------------------------------------
// Each iteration:
//   1. BRAINSTORM  derive the next question from the previous iteration's results
//   2. QUERY       ask every NotebookLM notebook (nlm cross query --all)
//   3. BUILD       recompile CUDA kernels + Rust crates
//   4. ENHANCE     run the NVIDIA-enhance -> AMD-final-output video pipelines
//   5. VERIFY      check every artifact really exists and is non-empty
//   6. REPORT      append to loki-report.json / .md, then loop
//
// USAGE
//   node loki.mjs                          # 3 iterations, default clip
//   node loki.mjs --iters 5 --clip G:\x.mp4
//   node loki.mjs --no-notebooks           # skip the (slow) NotebookLM stage
//   node loki.mjs --stage kernels          # only rebuild kernels, one pass
// ============================================================================
import { writeFileSync, existsSync, statSync, readFileSync } from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {
  stageVideo, stageGpuInventory, stageBuildKernels, stageBuildRust,
  stageNotebooks, VIDEO_PRESETS, OUTDIR, RUST_DIR,
} from './stages.mjs';

// ---------------------------------------------------------------- CLI
const argv = process.argv.slice(2);
const arg = (name, dflt) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : dflt;
};
const flag = (name) => argv.includes(`--${name}`);

const ITERS = parseInt(arg('iters', '3'), 10);
const CLIP = arg('clip', 'G:\\SORTED_MEDIA\\Videos\\01_Tiny_Under_50MB\\tmph42d67ie.mp4');
const ONLY = arg('stage', null);
const DO_NOTEBOOKS = !flag('no-notebooks');

const REPORT_JSON = path.join(OUTDIR, 'loki-report.json');
const REPORT_MD = path.join(OUTDIR, 'loki-report.md');

// ---------------------------------------------------------------- helpers
const stamp = () => new Date().toISOString().replace('T', ' ').slice(0, 19);
const hr = (s) => console.log(`\n${'='.repeat(78)}\n ${s}\n${'='.repeat(78)}`);
const tick = (ok) => (ok ? '\x1b[32mOK\x1b[0m' : '\x1b[31mFAIL\x1b[0m');
const bold = (s) => `\x1b[1m${s}\x1b[0m`;

function loadReport() {
  if (existsSync(REPORT_JSON)) { try { return JSON.parse(readFileSync(REPORT_JSON, 'utf8')); } catch {} }
  return { created: stamp(), iterations: [] };
}

// ---------------------------------------------------------------- brainstorm
// Turns the previous iteration's measured results into the next question.
function brainstorm(prev) {
  if (!prev) {
    return 'List every stage of a heterogeneous NVIDIA decode -> AMD Radeon final-output video pipeline, '
         + 'with the exact tool, device index, and flag for each stage. Include CUDA kernels, Rust '
         + 'heterogeneous crates (hetero_core, cuda_node), and any Node.js orchestration.';
  }
  const failed = [];
  if (prev.kernels && !prev.kernels.ok) failed.push('CUDA kernel build');
  if (prev.rust && !prev.rust.ok) failed.push('Rust build');
  const slow = (prev.videos || []).filter(v => v.bytes > 0).sort((a, b) => b.ms - a.ms)[0];
  const fastest = (prev.videos || []).filter(v => v.bytes > 0).sort((a, b) => a.ms - b.ms)[0];

  const bits = ['Iteration ' + prev.n + ' measured these results.'];
  if (fastest) bits.push(`Fastest path was ${fastest.label} at ${fastest.ms} ms.`);
  if (slow) bits.push(`Slowest was ${slow.label} at ${slow.ms} ms.`);
  if (failed.length) bits.push(`These failed and need a fix: ${failed.join(', ')}.`);
  bits.push('How do we close the remaining gap and make the AMD Radeon final-output stage the '
          + 'default while keeping NVIDIA enhancement? Give concrete fixes, not theory.');
  return bits.join(' ');
}

// ---------------------------------------------------------------- verify
function verifyArtifacts(r) {
  const checks = [];
  for (const v of r.videos || []) {
    checks.push({ what: `video:${v.label}`, ok: v.bytes > 0, detail: `${v.bytes} bytes -> ${v.outfile}` });
  }
  for (const k of r.kernels?.results || []) {
    checks.push({ what: k.label, ok: k.ok, detail: k.ok ? `${k.ms} ms` : k.out.slice(0, 120) });
  }
  if (r.kernels?.kernelRun) {
    const o = r.kernels.kernelRun;
    checks.push({ what: 'kernel:execute', ok: o.ok && /PASS/.test(o.out), detail: (o.out.match(/RESULT: \w+/) || [''])[0] });
  }
  if (r.rust) {
    checks.push({ what: 'rust:abrasax_7d_core', ok: r.rust.core?.ok, detail: r.rust.core?.ok ? `${r.rust.core.ms} ms` : 'see log' });
    checks.push({ what: 'rust:cuda_node', ok: r.rust.cudaNode?.ok, detail: r.rust.cudaNode?.ok ? `${r.rust.cudaNode.ms} ms` : 'see log' });
  }
  return checks;
}

// ---------------------------------------------------------------- main
const report = loadReport();

async function oneIteration(n) {
  hr(`LOKI ITERATION ${n}/${ITERS}  @ ${stamp()}`);
  const iter = { n, started: stamp(), videos: [], checks: [] };

  // --- GPU inventory
  const gpu = await stageGpuInventory();
  iter.gpu = { ok: gpu.ok, devices: gpu.devices };
  console.log(`${bold('GPUs')} (${tick(gpu.ok)})`);
  gpu.devices.forEach(d => console.log('   ' + d));

  // --- kernels
  if (!ONLY || ONLY === 'kernels') {
    console.log(`\n${bold('CUDA kernels')} — nvcc -arch=sm_75 ...`);
    const k = await stageBuildKernels();
    iter.kernels = { ok: k.results.every(r => r.ok), results: k.results.map(r => ({ label: r.label, ok: r.ok, ms: r.ms, out: r.out.slice(0, 200) })), kernelRun: k.kernelRun };
    k.results.forEach(r => console.log(`   ${tick(r.ok)} ${r.label}  ${r.ms} ms`));
    if (k.kernelRun) {
      const line = (k.kernelRun.out.split('\n').find(l => /RESULT/.test(l)) || '').trim();
      console.log(`   ${tick(k.kernelRun.ok)} execute -> ${line}`);
    }
  }

  // --- rust
  if (!ONLY || ONLY === 'rust') {
    console.log(`\n${bold('Rust')} — cargo build (abrasax_7d_core + cuda_node)`);
    const coreR = await stageBuildRust();
    // cuda_node lives in the parent workspace; build it there
    const { execFile } = await import('node:child_process');
    const { promisify } = await import('node:util');
    const pexec = promisify(execFile);
    let cudaR;
    try {
      const t0 = Date.now();
      await pexec('cargo', ['build', '-p', 'cuda_node'], { cwd: path.join(os.homedir(), 'Desktop', 'ABRASAX_GOD_OS'), timeout: 900000, windowsHide: true });
      cudaR = { ok: true, ms: Date.now() - t0 };
    } catch (e) { cudaR = { ok: false, ms: 0, out: (e.message || '').slice(0, 200) }; }
    iter.rust = { ok: coreR.core.ok && cudaR.ok, core: coreR.core, cudaNode: cudaR };
    console.log(`   ${tick(coreR.core.ok)} abrasax_7d_core  ${coreR.core.ms} ms`);
    console.log(`   ${tick(cudaR.ok)} cuda_node        ${cudaR.ms} ms`);
  }

  // --- video: NVIDIA enhance -> AMD final output
  if ((!ONLY || ONLY === 'video') && existsSync(CLIP)) {
    console.log(`\n${bold('Video: NVIDIA enhance -> AMD Radeon final output')}`);
    for (const preset of Object.keys(VIDEO_PRESETS)) {
      const v = await stageVideo(preset, CLIP, { measure: true });
      iter.videos.push({ label: preset, ok: v.ok && v.bytes > 0, ms: v.ms, bytes: v.bytes, outfile: v.outfile, note: v.note });
      console.log(`   ${tick(v.bytes > 0)} ${preset.padEnd(28)} ${String(v.ms).padStart(6)} ms  ${v.bytes.toLocaleString().padStart(12)} bytes`);
    }
  } else if (!existsSync(CLIP)) {
    console.log(`\n${bold('Video')}  skipped — clip not found: ${CLIP}`);
  }

  // --- notebooks
  if (DO_NOTEBOOKS && (!ONLY || ONLY === 'notebooks')) {
    const q = brainstorm(report.iterations[report.iterations.length - 1]);
    console.log(`\n${bold('NotebookLM (all notebooks)')}`);
    console.log(`   Q: ${q.slice(0, 150)}...`);
    const nb = await stageNotebooks(q, `iter${n}`);
    iter.notebook = { ok: nb.ok, answered: nb.answered, outfile: nb.outfile, bytes: nb.out.length };
    console.log(`   ${tick(nb.ok)} ${nb.answered}  -> ${nb.outfile}`);
  }

  // --- verify
  iter.checks = verifyArtifacts(iter);
  const passed = iter.checks.filter(c => c.ok).length;
  iter.ended = stamp();
  console.log(`\n${bold('VERIFY')}: ${passed}/${iter.checks.length} artifacts confirmed`);
  iter.checks.filter(c => !c.ok).forEach(c => console.log(`   ${tick(false)} ${c.what}: ${c.detail}`));
  return iter;
}

(async () => {
  console.log(`\nLOKI PIPELINE  |  ${ITERS} iteration(s)  |  clip: ${CLIP}`);
  console.log(`output dir: ${OUTDIR}`);
  for (let n = 1; n <= ITERS; n++) {
    const it = await oneIteration(n);
    report.iterations.push(it);
    writeFileSync(REPORT_JSON, JSON.stringify(report, null, 2));
  }

  // markdown rollup
  const md = [];
  md.push('# Loki pipeline report', '', `Generated ${stamp()}`, '', `Iterations: ${report.iterations.length}`, '');
  for (const it of report.iterations) {
    md.push(`## Iteration ${it.n}  (${it.started} -> ${it.ended})`, '');
    md.push('### GPUs', '');
    (it.gpu?.devices || []).forEach(d => md.push(`- ${d}`));
    md.push('', '### Video: NVIDIA enhance -> AMD Radeon final output', '');
    md.push('| preset | ms | bytes | note |', '|---|---:|---:|---|');
    (it.videos || []).forEach(v => md.push(`| ${v.label} | ${v.ms} | ${v.bytes} | ${v.note} |`));
    md.push('', `### Verify: ${it.checks.filter(c => c.ok).length}/${it.checks.length}`, '');
    it.checks.forEach(c => md.push(`- [${c.ok ? 'x' : ' '}] ${c.what} — ${c.detail}`));
    if (it.notebook) md.push('', '### Notebook query', '', `- answered: ${it.notebook.answered}`, `- saved: ${it.notebook.outfile}`);
    md.push('');
  }
  writeFileSync(REPORT_MD, md.join('\n'));
  console.log(`\nReport: ${REPORT_MD}`);
  console.log(`JSON  : ${REPORT_JSON}\n`);
})();
