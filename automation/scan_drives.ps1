$ErrorActionPreference = 'SilentlyContinue'
$out = 'C:\ABRASAX\logs\scan_drives.json'

$drives = @()
foreach ($d in (Get-CimInstance Win32_LogicalDisk)) {
    $drives += [pscustomobject]@{
        id       = $d.DeviceID
        type     = switch ($d.DriveType) { 2 {'removable'} 3 {'fixed'} 4 {'network'} 5 {'cdrom'} default {'other'} }
        fs       = $d.FileSystem
        size_gb  = if ($d.Size) { [math]::Round($d.Size / 1GB, 1) } else { $null }
        free_gb  = if ($d.FreeSpace) { [math]::Round($d.FreeSpace / 1GB, 1) } else { $null }
        label    = $d.VolumeName
    }
}

$result = [pscustomobject]@{
    scanned_at = (Get-Date).ToString('o')
    host       = $env:COMPUTERNAME
    user       = $env:USERNAME
    drives     = $drives
}
$result | ConvertTo-Json -Depth 4 | Set-Content -Path $out -Encoding UTF8
$result.drives | Format-Table -AutoSize
Write-Host ("`nwrote " + $out)
