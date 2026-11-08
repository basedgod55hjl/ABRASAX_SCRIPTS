<#
.SYNOPSIS
    Installs Unity <version> (editor + build-support modules) on a non-system drive
    using the STANDALONE NSIS installers (Unity Hub's --headless CLI hangs; do not use it).

.DESCRIPTION
    Source of truth is the API snapshot written by the caller:
        C:\ABRASAX\CONFIG\unity-7000.0.0a10-windows.json
    which lists every editor/module download URL and its exact byte size.

    Two traps this script exists to avoid:
      1. Unity's NSIS installers unpack the whole payload into $TEMP before moving it to
         the target. If TEMP lives on C: that costs ~8 GB on the system drive. Every
         installer is therefore launched with TMP/TEMP pointed at <Root>\temp.
      2. curl -C - against a partially written file silently appends and corrupts it.
         Downloads are verified against the byte count in the JSON; a mismatch deletes
         and re-fetches from scratch instead of resuming.

.PARAMETER Root          Install root, e.g. J:\Unity  (editor goes to <Root>\<Version>)
.PARAMETER Version       Unity version string, e.g. 7000.0.0a10
.PARAMETER Config        Path to the API snapshot JSON
.PARAMETER ModulesOnly   Skip the editor (already installed) and only do modules
.PARAMETER OnlyModule    Install a single module id, e.g. webgl
.PARAMETER Force         Reinstall even if the module marker directory already exists

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File install_unity.ps1
.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File install_unity.ps1 -ModulesOnly -OnlyModule webgl
#>
[CmdletBinding()]
param(
    [string]$Root      = 'J:\Unity',
    [string]$Version   = '7000.0.0a10',
    [string]$Config    = 'C:\ABRASAX\CONFIG\unity-7000.0.0a10-windows.json',
    [switch]$ModulesOnly,
    [string]$OnlyModule = '',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'   # huge speedup for Invoke-WebRequest
Add-Type -AssemblyName System.IO.Compression.FileSystem

$EditorDir = Join-Path $Root $Version
$CacheDir  = Join-Path $Root 'cache'
$TempDir   = Join-Path $Root 'temp'
$LogDir    = Join-Path $Root 'logs'
$StateFile = Join-Path $LogDir 'module-state.json'

foreach ($d in @($Root, $EditorDir, $CacheDir, $TempDir, $LogDir)) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}

# Any native installer we spawn inherits these -> payload never touches C:
$env:TMP  = $TempDir
$env:TEMP = $TempDir

function Write-Log([string]$msg) {
    $line = "{0}  {1}" -f (Get-Date -Format 'HH:mm:ss'), $msg
    Write-Host $line
    Add-Content -Path (Join-Path $LogDir 'install-unity.log') -Value $line
}

function Get-FreeGB([string]$drive) {
    $d = Get-PSDrive -Name $drive.TrimEnd(':') -ErrorAction SilentlyContinue
    if ($d) { return [math]::Round($d.Free / 1GB, 2) }
    return -1
}

# --- download -----------------------------------------------------------------
function Get-Installer([string]$Url, [long]$Bytes, [switch]$SizeTolerant) {
    $name = Split-Path $Url -Leaf
    if ($name -eq '' -or $name -notmatch '\.(exe|zip)$') { $name = ($Url -replace '[^\w\.\-]', '_') + '.bin' }
    $out  = Join-Path $CacheDir $name

    # Docs zips are rebuilt server-side without the API snapshot being updated, so their
    # byte count drifts. Accept a cached copy that still opens as a valid archive.
    if ($SizeTolerant -and (Test-Path $out) -and (Get-Item $out).Length -gt 0) {
        try {
            $z = [System.IO.Compression.ZipFile]::OpenRead($out)
            $n = $z.Entries.Count
            $z.Dispose()
            Write-Log "  download: cached $name ($((Get-Item $out).Length) bytes, $n entries OK; API said $Bytes)"
            return $out
        } catch {
            Write-Log "  download: cached $name is not a valid archive -> re-fetching"
            Remove-Item $out -Force
        }
    }
    if ((Test-Path $out) -and ((Get-Item $out).Length -eq $Bytes)) {
        Write-Log "  download: cached $name ($Bytes bytes)"
        return $out
    }
    if (Test-Path $out) {
        $have = (Get-Item $out).Length
        Write-Log "  download: $name size mismatch (have $have, want $Bytes) -> re-fetching from scratch"
        Remove-Item $out -Force
    }

    Write-Log "  download: $Url -> $name ($([math]::Round($Bytes/1GB,2)) GB)"
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        # -UseBasicParsing: no IE engine dependency. No -Resume: resume corrupts these files.
        Invoke-WebRequest -Uri $Url -OutFile $out -UseBasicParsing -Headers @{ 'User-Agent' = 'UnityInstallScript' }
        $got = (Get-Item $out).Length
        if ($got -eq $Bytes) { Write-Log "  download: OK $name"; return $out }
        Write-Log "  download: attempt $attempt got $got / $Bytes -> retry"
        Remove-Item $out -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 5
    }
    throw "download failed after 3 attempts: $Url (want $Bytes bytes)"
}

# --- install ------------------------------------------------------------------
function Invoke-Nsis([string]$Exe, [string]$Target) {
    # /S silent, /D last, unquoted, no trailing backslash (NSIS requirement)
    $args = @('/S', "/D=$Target")
    $p = Start-Process -FilePath $Exe -ArgumentList $args -Wait -PassThru -WorkingDirectory $TempDir
    return $p.ExitCode
}

function Install-Editor($ed) {
    $unityExe = Join-Path $EditorDir 'Editor\Unity.exe'
    if ((Test-Path $unityExe) -and -not $Force) {
        Write-Log "editor: already present at $unityExe"
        return
    }
    $exe = Get-Installer -Url $ed.url -Bytes ([long]$ed.download_bytes)
    $before = Get-FreeGB $Root.Substring(0,1)
    Write-Log "editor: installing -> $EditorDir (free ${before} GB)"
    $rc = Invoke-Nsis -Exe $exe -Target $EditorDir
    Write-Log "editor: installer exit code $rc"
    if ($rc -ne 0) { throw "editor installer exited $rc" }
    if (-not (Test-Path $unityExe)) { throw "editor installer returned 0 but $unityExe missing" }
    $after = Get-FreeGB $Root.Substring(0,1)
    Write-Log "editor: OK (free ${after} GB, used $([math]::Round($before-$after,2)) GB)"
}

function Get-PlaybackEngines {
    $pe = Join-Path $EditorDir 'Editor\Data\PlaybackEngines'
    if (-not (Test-Path $pe)) { return @() }
    return @(Get-ChildItem $pe -Directory | Select-Object -ExpandProperty Name | Sort-Object)
}

function Install-Module($m, [hashtable]$state) {
    $id = $m.id
    $markers = @{
        'android'                    = 'AndroidPlayer'
        'ios'                        = 'iOS'
        'appletv'                    = 'AppleTV'
        'visionos'                   = 'VisionOS'
        'linux-il2cpp'               = 'LinuxStandalone'
        'linux-coreclr'              = 'LinuxStandalone'
        'linux-server'               = 'LinuxServerStandalone'
        'mac-coreclr'                = 'MacStandaloneSupport'
        'mac-server-coreclr'         = 'MacServerStandaloneCoreCLR'
        'mac-server'                 = 'MacServerStandalone'
        'universal-windows-platform' = 'MetroSupport'
        'webgl'                      = 'WebGLSupport'
        # windows-il2cpp and windows-server add build variations under the editor's
        # built-in windowsstandalonesupport dir, so they have no distinct marker folder;
        # they are tracked through module-state.json only.
    }

    if (-not $OnlyModule -and $state.ContainsKey($id) -and $state[$id].exit -eq 0 -and -not $Force) {
        Write-Log "module ${id}: already recorded installed, skipping"
        return
    }
    if ($markers.ContainsKey($id)) {
        $mp = Join-Path $EditorDir ("Editor\Data\PlaybackEngines\" + $markers[$id])
        if ((Test-Path $mp) -and -not $Force) {
            Write-Log "module ${id}: marker $($markers[$id]) present, skipping"
            $state[$id] = @{ exit = 0; marker = $markers[$id]; note = 'already present' }
            return
        }
    }

    $before = Get-PlaybackEngines
    try {
        $exe = Get-Installer -Url $m.url -Bytes ([long]$m.download_bytes)
        Write-Log "module ${id}: installing ($($m.name))"
        $rc = Invoke-Nsis -Exe $exe -Target $EditorDir
    } catch {
        Write-Log "module ${id}: FAILED $($_.Exception.Message)"
        $state[$id] = @{ exit = -1; error = $_.Exception.Message }
        return
    }
    Start-Sleep -Seconds 2
    $after = Get-PlaybackEngines
    $new   = @($after | Where-Object { $before -notcontains $_ })
    Write-Log "module ${id}: exit $rc; new engine dirs: $(if($new){$new -join ', '}else{'(none detected)'})"
    $state[$id] = @{ exit = $rc; new_dirs = $new; marker = $markers[$id] }
}

function Install-Docs($m) {
    $docsDir = Join-Path $EditorDir 'Editor\Data\Documentation'
    if ((Test-Path (Join-Path $docsDir 'en')) -and -not $Force) {
        Write-Log 'documentation: already present, skipping'
        return
    }
    $zip = Get-Installer -Url $m.url -Bytes ([long]$m.download_bytes) -SizeTolerant
    Write-Log "documentation: extracting $zip -> Editor\Data"
    $dataDir = Join-Path $EditorDir 'Editor\Data'
    # .NET ZipFile is path-safe here; the MSYS `tar` on PATH is GNU tar and chokes on
    # native Windows paths like J:\... (that caused a bogus 'Cannot connect to J:' error).
    try {
        [System.IO.Compression.ZipFile]::ExtractToDirectory($zip, $dataDir)
    } catch {
        Write-Log "documentation: ZipFile extract failed ($($_.Exception.Message)); trying System32\tar.exe"
        & "$env:SystemRoot\System32\tar.exe" -xf $zip -C $dataDir
    }
    if (Test-Path (Join-Path $docsDir 'en')) { Write-Log 'documentation: OK' }
    else { Write-Log 'documentation: WARNING - Documentation\en not found after extract' }
}

# --- main ---------------------------------------------------------------------
Write-Log "=== install_unity.ps1 version=$Version root=$Root ==="
Write-Log "TEMP redirected to $TempDir; free on $($Root.Substring(0,1)): $((Get-FreeGB $Root.Substring(0,1))) GB"

$cfg = Get-Content $Config -Raw | ConvertFrom-Json
$state = @{}
if (Test-Path $StateFile) {
    (Get-Content $StateFile -Raw | ConvertFrom-Json).PSObject.Properties |
        ForEach-Object { $state[$_.Name] = @{ exit = $_.Value.exit; marker = $_.Value.marker } }
}

if (-not $ModulesOnly) { Install-Editor $cfg.editor }

# User-requested order. visualstudio* entries are Visual Studio bootstrappers, not
# Unity NSIS modules, and are intentionally not handled here.
$order = @(
    'android','ios','appletv','visionos','linux-il2cpp','linux-server','mac-coreclr',
    'linux-coreclr','mac-server-coreclr','mac-server','universal-windows-platform',
    'webgl','windows-il2cpp','windows-server'
)
$byId = @{}
foreach ($m in $cfg.modules) { $byId[$m.id] = $m }

foreach ($id in $order) {
    if ($OnlyModule -and $id -ne $OnlyModule) { continue }
    if (-not $byId.ContainsKey($id)) { Write-Log "module ${id}: not present in config, skipping"; continue }
    Install-Module $byId[$id] $state
}

$doc = $byId['documentation']
if ($doc -and (-not $OnlyModule -or $OnlyModule -eq 'documentation')) { Install-Docs $doc }

# persist state
$out = @{}
foreach ($k in $state.Keys) { $out[$k] = $state[$k] }
$out | ConvertTo-Json -Depth 5 | Set-Content -Path $StateFile -Encoding UTF8

# --- verify -------------------------------------------------------------------
Write-Log '=== verification ==='
$unityExe = Join-Path $EditorDir 'Editor\Unity.exe'
if (Test-Path $unityExe) {
    $vi = (Get-Item $unityExe).VersionInfo
    Write-Log "Unity.exe FileVersion=$($vi.FileVersion) ProductVersion=$($vi.ProductVersion)"
} else {
    Write-Log "MISSING: $unityExe"
}
Write-Log ("PlaybackEngines: " + ((Get-PlaybackEngines) -join ', '))
Write-Log "free on $($Root.Substring(0,1)): $((Get-FreeGB $Root.Substring(0,1))) GB"
Write-Log '=== done ==='
