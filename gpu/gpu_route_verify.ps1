# gpu_route_verify.ps1 — prove WHICH adapter a given process is actually rendering on.
#
# Method: Windows exposes per-process GPU utilisation through the GPU Engine performance
# counters, whose instance names encode both the process and the adapter:
#     pid_1234_luid_0x00000000_0x0000ABCD_phys_0_eng_0_engtype_3D
# The luid_ pair is the adapter. We map those LUIDs back to adapter names via each adapter's
# registry key (AdapterLuid), then show which adapter each of the supplied processes is using.
#
# Usage: gpu_route_verify.ps1 -ProcessName vlc,ffmpeg -Seconds 8
param(
    [string[]]$ProcessName = @('vlc'),
    [int]$Seconds = 8,
    [int]$TopN = 12
)

function Get-AdapterLuidMap {
    $map = @{}
    $base = 'HKLM:\SYSTEM\CurrentControlSet\Control\Video'
    if (-not (Test-Path $base)) { return $map }
    foreach ($guidKey in Get-ChildItem $base -ErrorAction SilentlyContinue) {
        foreach ($inst in Get-ChildItem $guidKey.PSPath -ErrorAction SilentlyContinue) {
            $p = Get-ItemProperty $inst.PSPath -ErrorAction SilentlyContinue
            if ($null -eq $p.AdapterLuid) { continue }
            $bytes = $p.AdapterLuid
            if ($bytes -isnot [byte[]] -or $bytes.Length -lt 8) { continue }
            $low  = [uint32]([BitConverter]::ToUInt32($bytes, 0))
            $high = [uint32]([BitConverter]::ToUInt32($bytes, 4))
            $key = ('0x{0:x8}_0x{1:x8}' -f $high, $low)
            if (-not $map.ContainsKey($key)) {
                $name = $p.'*ErrorControl'  # placeholder, real name fetched below
                $map[$key] = $null
            }
            # Adapter description lives under ...\Video\{GUID}\0000\... in Device Description
            $desc = (Get-ItemProperty $inst.PSPath -ErrorAction SilentlyContinue).DeviceDescription
            if ($desc) { $map[$key] = $desc }
        }
    }
    return $map
}

$luidMap = Get-AdapterLuidMap
Write-Host "=== adapter LUID map (from registry) ==="
if ($luidMap.Count -eq 0) { Write-Host '  (none resolved - will report raw LUIDs)' }
else { $luidMap.GetEnumerator() | ForEach-Object { Write-Host ("  {0}  ->  {1}" -f $_.Key, $_.Value) } }
Write-Host ''

$procs = @{}
# -File invocation delivers "-ProcessName vlc,python" as ONE literal string, so split on comma
$names = $ProcessName | ForEach-Object { $_ -split ',' } | Where-Object { $_.Trim() } | ForEach-Object { $_.Trim() }
foreach ($n in $names) {
    Get-Process -Name $n -ErrorAction SilentlyContinue | ForEach-Object {
        $procs[[string]$_.Id] = $_.ProcessName
    }
}
if ($procs.Count -eq 0) {
    Write-Host "No running process matched: $($ProcessName -join ', ')"
    return
}
Write-Host "=== watching: $(( $procs.GetEnumerator() | ForEach-Object { "$($_.Value)[$($_.Key)]" }) -join ', ') for $Seconds s ==="
Write-Host ''

# sample a few times, keep the max per (pid, luid, engtype)
$agg = @{}
for ($i = 0; $i -lt $Seconds; $i++) {
    try {
        $s = (Get-Counter '\GPU Engine(*)\Utilization Percentage' -ErrorAction Stop).CounterSamples
    } catch { Start-Sleep -Milliseconds 400; continue }
    foreach ($c in $s) {
        if ($c.InstanceName -notmatch 'pid_(\d+)_luid_(0x[0-9a-f]+)_(0x[0-9a-f]+).*engtype_(.+)') { continue }
        $pidNum = $Matches[1]; $lh = $Matches[2]; $ll = $Matches[3]; $eng = $Matches[4]
        if (-not $procs.ContainsKey($pidNum)) { continue }
        $key = "$pidNum|$lh|$ll|$eng"
        if (-not $agg.ContainsKey($key) -or $c.CookedValue -gt $agg[$key]) { $agg[$key] = $c.CookedValue }
    }
    Start-Sleep -Milliseconds 500
}

Write-Host '=== adapter attribution (max % observed) ==='
if ($agg.Count -eq 0) {
    Write-Host '  no GPU counter samples attributed to the watched processes'
} else {
    $agg.GetEnumerator() |
        Sort-Object { -$_.Value } |
        Select-Object -First $TopN |
        ForEach-Object {
            $p = $_.Key -split '\|'
            $luid = "$($p[1])_$($p[2])"
            $adapter = if ($luidMap.ContainsKey($luid) -and $luidMap[$luid]) { $luidMap[$luid] } else { "(luid $luid)" }
            Write-Host ("  {0,-8} {1,-14} {2,-30} {3,6:N1} %" -f $p[0], $p[3], $adapter, $_.Value)
        }
}
Write-Host ''
Write-Host '=== nvidia-smi view (compute processes only) ==='
& nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv 2>&1 | Write-Host
