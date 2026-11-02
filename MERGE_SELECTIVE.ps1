param()

$src = "C:\Users\BASEDGOD\Desktop\ABRASAX"
$dst = "C:\Users\BASEDGOD\Desktop\ABRASAX AGI"

$excludeDirs = @(
    ".git", ".venv", "node_modules", "target", "build", "builds", "dist",
    "llama-cpp", "vlc", "vbcable", "vendor",
    "ABRASAX_LOCAL", "abrasax_llm\models\gguf",
    "LLM_ENGINE", "backups", "claude_backup", "claude_control",
    "_ARCHIVE", "_SYSTEM32_MIGRATED"
)

$excludeFiles = @(
    "*.gguf", "*.safetensors", "*.bin", "*.exe", "*.dll", "*.pdb",
    "*.rlib", "*.so", "*.dylib", "*.lib", "*.exp",
    "*.cubin", "*.ptx", "*.onnx",
    "*.zip", "*.7z", "*.rar", "*.tar.gz",
    "*.mp4", "*.mkv", "*.avi", "*.mov",
    "*.mp3", "*.wav", "*.flac",
    "*.ppm", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp",
    "*.o", "*.obj", "*.pyc", "*.pyo",
    "*.lock"
)

Write-Host "ABRASAX merge starting..." -ForegroundColor Cyan
Write-Host "Source: $src" -ForegroundColor Yellow
Write-Host "Dest:   $dst" -ForegroundColor Yellow
Write-Host ""

# Phase 1: All source code, configs, docs, scripts
Write-Host "Phase 1: Source code + configs + docs..." -ForegroundColor Green
$exts = "*.rs", "*.py", "*.ts", "*.js", "*.md", "*.json", "*.yaml", "*.yml", "*.toml", "*.txt", "*.bat", "*.ps1", "*.vbs", "*.sh", "*.env", "*.css", "*.html", "*.cfg", "*.conf", "*.ini", "*.cu", "*.cuh", "*.c", "*.cpp", "*.h", "*.hpp", "*.cs", "*.java", "*.cmd", "*.hex"

robocopy $src $dst /E /COPY:DAT /R:2 /W:2 /MT:8 /NP /NDL /NFL /XO /XD $excludeDirs /XF $excludeFiles /IF $exts
Write-Host "Phase 1 done." -ForegroundColor Green

# Phase 2: Critical data directories
Write-Host "Phase 2: Data directories..." -ForegroundColor Green
$dataDirs = @(
    "config", "docs", "skills", "core", "engine", "agents",
    "swarm", "telegram", "scripts", "tools", "deploy", "ops",
    "kernels", "abrasax", "agi_config", "ai_os",
    "notebooks", "tests", "data", "memory", "sessions",
    "docker", "k8s", "nginx", "web", "workflows", "pipeline",
    "training", "seed", "brain", "catalyst", "compiler",
    "integration", "plugins", "projects", "repos", "sdk",
    "terminals", "wasm", "runtime", "raw", "examples",
    "images", "media", "abrasax_stack", "abrasax_daemon",
    "mined_high_phi_seeds", "OSIRISBLXCK_CORE", "BGS_CRYSTAL",
    "CRYSTAL", "cbm_essence"
)

foreach ($dir in $dataDirs) {
    $s = Join-Path $src $dir
    $d = Join-Path $dst $dir
    if (Test-Path $s) {
        robocopy $s $d /E /COPY:DAT /R:2 /W:2 /MT:4 /NP /NDL /NFL /XO /XD $excludeDirs /XF $excludeFiles /IF $exts
    }
}
Write-Host "Phase 2 done." -ForegroundColor Green

# Phase 3: Root-level important files
Write-Host "Phase 3: Root config files..." -ForegroundColor Green
$rootFiles = @(
    "pyproject.toml", "package.json", "requirements.txt",
    ".env.example", ".gitignore",
    "README.md", "ARCHITECTURE.md", "BUILD.md", "CHANGELOG.md",
    "CONTRIBUTING.md", "CLAUDE.md", "LICENSE"
)

foreach ($file in $rootFiles) {
    $s = Join-Path $src $file
    $d = Join-Path $dst $file
    if (Test-Path $s) {
        $copyIt = $true
        if (Test-Path $d) {
            $srcTime = (Get-Item $s).LastWriteTime
            $dstTime = (Get-Item $d).LastWriteTime
            if ($srcTime -le $dstTime) { $copyIt = $false }
        }
        if ($copyIt) {
            Copy-Item $s $d -Force
            Write-Host "  $file" -ForegroundColor Gray
        }
    }
}

Write-Host ""
Write-Host "MERGE COMPLETE" -ForegroundColor Cyan
Write-Host "Source code, configs, docs copied selectively." -ForegroundColor Green
Write-Host "Skipped large binaries: .gguf, .safetensors, .bin, .exe, .dll, learning.db" -ForegroundColor Yellow
Write-Host "Original ABRASAX (196GB) kept intact." -ForegroundColor Yellow
