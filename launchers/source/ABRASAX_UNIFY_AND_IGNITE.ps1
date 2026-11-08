<#
.SYNOPSIS
    ABRASAX_UNIFY_AND_IGNITE.ps1
    Bootstrap script for the Abrasax framework.
.DESCRIPTION
    Performs admin privilege check, displays the PRIMAL_HEX banner,
    initializes logging, sets up the .abrasax root directory tree,
    and prepares the environment for downstream operations.
.NOTES
    Author:  Jcode (auto-generated)
    Version: 1.0.0
#>

#Requires -Version 5.1

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# 1. ADMIN CHECK
# ---------------------------------------------------------------------------
function Test-AdminPrivilege {
    <#
    .SYNOPSIS
        Returns $true if the current session is elevated; $false otherwise.
    #>
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-AdminPrivilege)) {
    Write-Host 'ABRASAX requires administrator privileges.  Relaunch as Administrator.' -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# 2. PRIMAL_HEX BANNER
# ---------------------------------------------------------------------------
function Write-PrimalHexBanner {
    <#
    .SYNOPSIS
        Renders the PRIMAL_HEX ASCII-art banner.
    #>
    $banner = @"

     █████╗ ██████╗ ██████╗  █████╗ ███████╗ █████╗ ██╗  ██╗
    ██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗╚██╗██╔╝
    ███████║██████╔╝██████╔╝███████║███████╗███████║ ╚███╔╝
    ██╔══██║██╔══██╗██╔══██╗██╔══██║╚════██║██╔══██║ ██╔██╗
    ██║  ██║██████╔╝██║  ██║██║  ██║███████║██║  ██║██╔╝╚██╗
    ╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝

      ██████╗ ██████╗ ██╗███╗   ███╗ █████╗ ██╗         ██╗  ██╗███████╗██╗  ██╗
      ██╔══██╗██╔══██╗██║████╗ ████║██╔══██╗██║         ██║  ██║██╔════╝╚██╗██╔╝
      ██████╔╝██████╔╝██║██╔████╔██║███████║██║         ███████║█████╗   ╚███╔╝
      ██╔═══╝ ██╔══██╗██║██║╚██╔╝██║██╔══██║██║         ██╔══██║██╔══╝   ██╔██╗
      ██║     ██║  ██║██║██║ ╚═╝ ██║██║  ██║███████╗    ██║  ██║███████╗██╔╝╚██╗
      ╚═╝     ╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝    ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝

             ██╗   ██╗███╗   ██╗██╗███████╗██╗   ██╗
             ██║   ██║████╗  ██║██║██╔════╝╚██╗ ██╔╝
             ██║   ██║██╔██╗ ██║██║█████╗   ╚████╔╝
             ██║   ██║██║╚██╗██║██║██╔══╝    ╚██╔╝
             ╚██████╔╝██║ ╚████║██║██║        ██║
              ╚═════╝ ╚═╝  ╚═══╝╚═╝╚═╝        ╚═╝

"@
    Write-Host $banner -ForegroundColor Cyan
}

Write-PrimalHexBanner

# ---------------------------------------------------------------------------
# 3. LOG FUNCTION
# ---------------------------------------------------------------------------
$script:LogFilePath = $null  # assigned after root is created

function Write-AbrasaxLog {
    <#
    .SYNOPSIS
        Writes a timestamped message to the Abrasax log file and console.
    .PARAMETER Message
        The log message.
    .PARAMETER Level
        Severity level: INFO, WARN, ERROR, DEBUG.  Defaults to INFO.
    #>
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message,

        [ValidateSet('INFO', 'WARN', 'ERROR', 'DEBUG')]
        [string]$Level = 'INFO'
    )

    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff'
    $entry     = "[$timestamp] [$Level] $Message"

    # Colour mapping
    $colour = switch ($Level) {
        'ERROR' { 'Red'    }
        'WARN'  { 'Yellow' }
        'DEBUG' { 'Gray'   }
        default { 'White'  }
    }

    Write-Host $entry -ForegroundColor $colour

    if ($script:LogFilePath) {
        Add-Content -Path $script:LogFilePath -Value $entry -Encoding UTF8
    }
}

# ---------------------------------------------------------------------------
# 4. ENVIRONMENT & ROOT SETUP
# ---------------------------------------------------------------------------
$AbrasaxRoot = Join-Path $env:USERPROFILE '.abrasax'

# Sub-folders that Abrasax expects
$AbrasaxSubfolders = @(
    'logs',
    'config',
    'data',
    'cache',
    'scripts',
    'output'
)

if (-not (Test-Path $AbrasaxRoot)) {
    New-Item -Path $AbrasaxRoot -ItemType Directory -Force | Out-Null
    Write-Host "Created root: $AbrasaxRoot" -ForegroundColor Green
}

foreach ($sub in $AbrasaxSubfolders) {
    $subPath = Join-Path $AbrasaxRoot $sub
    if (-not (Test-Path $subPath)) {
        New-Item -Path $subPath -ItemType Directory -Force | Out-Null
        Write-Host "Created subfolder: $subPath" -ForegroundColor Green
    }
}

# Wire log file
$script:LogFilePath = Join-Path $AbrasaxRoot 'logs\abrasax.log'
Write-AbrasaxLog -Message 'ABRASAX_UNIFY_AND_IGNITE bootstrap started.' -Level INFO
Write-AbrasaxLog -Message "Abrasax root : $AbrasaxRoot"            -Level INFO
Write-AbrasaxLog -Message "Log file     : $script:LogFilePath"     -Level INFO

# Export root as an environment variable for child processes
$env:ABRASAX_ROOT = $AbrasaxRoot
[Environment]::SetEnvironmentVariable('ABRASAX_ROOT', $AbrasaxRoot, 'User')

Write-AbrasaxLog -Message 'Environment initialized.' -Level INFO
Write-Host "ABRASAX_ROOT = $AbrasaxRoot" -ForegroundColor Magenta

# ---------------------------------------------------------------------------
# FINAL SIGN-OFF
# ---------------------------------------------------------------------------
Write-Host "`nABRASAX UNIFY AND IGNITE — READY.`n" -ForegroundColor Green
