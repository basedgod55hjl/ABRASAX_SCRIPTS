# abraxas_health.ps1 — the single-command health check (master plan 53).
# Reports [OK]/[WARN]/[DOWN] for every subsystem with live evidence.
# Pure ASCII source (PowerShell 5.1 ANSI script reader).
$ErrorActionPreference = 'Continue'
$out = @()

function Check($name, $ok, $detail = "") {
    $tag = if ($ok) { "[OK]" } else { "[DOWN]" }
    $script:out += "$tag $name $detail"
}

# toolchain
Check "Windows" $true ((Get-CimInstance Win32_OperatingSystem).Caption)
foreach ($t in 'git','python','node','cargo','uv') {
    $c = Get-Command $t -ErrorAction SilentlyContinue
    $ver = ''
    if ($c) { $ver = ((& $t --version 2>&1 | Select-Object -First 1) -join ' ') }
    Check "tool:$t" ([bool]$c) $ver
}
$nvcc = Get-Command nvcc -ErrorAction SilentlyContinue
Check "cuda:nvcc" ([bool]$nvcc)
$gpu = nvidia-smi --query-gpu=name,memory.used,memory.total,temperature.gpu --format=csv,noheader 2>$null
Check "gpu:nvidia" ($LASTEXITCODE -eq 0) ($gpu.Trim())
$ram = Get-CimInstance Win32_OperatingSystem
Check "ram" ($ram.FreePhysicalMemory -gt 500MB) "free=$([math]::Round($ram.FreePhysicalMemory/1MB,1))GB/$([math]::Round($ram.TotalVisibleMemorySize/1MB,1))GB"
$cdisk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
Check "disk:C" ($cdisk.FreeSpace -gt 10GB) "free=$([math]::Round($cdisk.FreeSpace/1GB,1))GB"

# services
foreach ($p in @{1234="lm-studio";1235="gpt-oss(CPU)";1236="lfm-from-tiles";2645="gateway";8811="hub";8798="bot";9628="triune";4200="ts-runtime"}.GetEnumerator()) {
    $c = Get-NetTCPConnection -State Listen -LocalPort $p.Key -ErrorAction SilentlyContinue
    Check "svc:$($p.Value):$($p.Key)" ([bool]$c)
}

# registries
$mr = if (Test-Path 'C:\abrasax\registry\MODEL_REGISTRY.json') { (Get-Content 'C:\abrasax\registry\MODEL_REGISTRY.json' -Raw | ConvertFrom-Json).model_count } else { 0 }
Check "registry:models" ($mr -gt 0) "count=$mr"
$ar = if (Test-Path 'C:\abrasax\registry\AGENT_REGISTRY.json') { (Get-Content 'C:\abrasax\registry\AGENT_REGISTRY.json' -Raw | ConvertFrom-Json).running } else { 0 }
Check "registry:agents" ($ar -ge 14) "running=$ar"
$docs = (Get-ChildItem 'C:\abrasax\DOC' -File -Filter *.md -ErrorAction SilentlyContinue | Measure-Object).Count
Check "docs" ($docs -gt 5) "count=$docs"

# soul + TON + repos
$sb = Get-Content 'C:\abrasax\memory\soul_bond.json' -Raw | ConvertFrom-Json
Check "soul" $sb.bound "verified=$($sb.ts)"
$n = Get-Content 'C:\abrasax\memory\neo_ton_loop.json' -Raw | ConvertFrom-Json
Check "ton" $n.ton.ok "seqno=$($n.ton.seqno) transformer_ok=$($n.neo_transformer.ok)"
$st = Get-Content 'C:\abrasax\memory\f_entanglement_state.json' -Raw | ConvertFrom-Json
$alive = ($st.entanglement.node_f1.alive -and $st.entanglement.node_f2.alive -and $st.entanglement.node_f3.alive -and $st.entanglement.node_neo.alive)
Check "f-logic" $alive "F1=$($st.entanglement.node_f1.alive) F2=$($st.entanglement.node_f2.alive) F3=$($st.entanglement.node_f3.alive) NEO=$($st.entanglement.node_neo.alive)"

# repos: clean + pushed
$repos = @('ABRASAX-7D-Crystal','ABRASAX-Agents','ABRASAX-AI-Engine','abrasax-harness','ABRASAX-UI','ABRASAX_SCRIPTS','abraxas-mobile')
$dirty = 0
foreach ($r in $repos) {
    $d = "C:\abrasax\_BUILD\stage\$r"
    if (Test-Path "$d\.git") {
        $s = (git -C $d status --porcelain 2>$null | Measure-Object -Line).Lines
        $bond = Test-Path "$d\BOND_MANIFEST.json"
        if ($s -gt 0 -or -not $bond) { $dirty++ }
    }
}
Check "repos:bond+clean" ($dirty -eq 0) "dirty_or_unbonded=$dirty/6"

# bot error surface
$b = Invoke-RestMethod 'http://127.0.0.1:8798/health' -TimeoutSec 10
Check "bot" ($b.status -eq 'ok') "polls=$($b.polls) replies=$($b.replies) errors=$($b.errors)"

$script:out += "---"
$script:out += "SUMMARY: $((@($script:out | Where-Object { $_.StartsWith('[OK]') })).Count) OK / $((@($script:out | Where-Object { $_.StartsWith('[DOWN]') })).Count) DOWN"
$script:out
