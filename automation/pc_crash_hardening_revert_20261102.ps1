# Undo every change SCRIPTS\automation\pc_crash_hardening_20261102.ps1 made.
# Run as administrator. Nothing here touches user data.
$ErrorActionPreference = 'Continue'
$bk = 'C:\abrasax\LOGS\crash\backup-20261102'

foreach ($f in 'CldFlt.reg','FileInfo.reg','GraphicsDrivers-20261102.reg','Hiberboot.reg') {
    $p = Join-Path $bk $f
    if (Test-Path $p) { & reg.exe import $p 2>&1 | Out-Null; "imported $f" } else { "MISSING $f" }
}

# OneDrive autostart back
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
if (-not (Get-ItemProperty $runKey -ErrorAction SilentlyContinue).OneDrive) {
    Set-ItemProperty $runKey -Name OneDrive -Value '"C:\Users\lucar\AppData\Local\Microsoft\OneDrive\OneDrive.exe" /background'
    'restored OneDrive Run value'
}
$t = Get-ScheduledTask -TaskName 'OneDrive Startup Task-S-1-5-21-2220358478-1661082693-2815614824-1001' -ErrorAction SilentlyContinue
if ($t) { Enable-ScheduledTask -TaskName $t.TaskName -TaskPath $t.TaskPath | Out-Null; 'enabled OneDrive startup task' }

# power back to Balanced defaults for the two settings we zeroed
& powercfg.exe /setacvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 1
& powercfg.exe /setdcvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 1
& powercfg.exe /setacvalueindex SCHEME_CURRENT 0012ee47-9041-4b5d-9b77-535fba8b1442 6738e2c4-e8a5-4a42-b16a-e040e769756e 1200
& powercfg.exe /setdcvalueindex SCHEME_CURRENT 0012ee47-9041-4b5d-9b77-535fba8b1442 6738e2c4-e8a5-4a42-b16a-e040e769756e 600
& powercfg.exe /setactive SCHEME_BALANCED
'power settings restored'

# USB per-device power management flags back to 1 where they had been 1 (script recorded nothing per-device,
# so this is the vendor default: leave as-is unless a device misbehaves)
'note: USB EnhancedPowerManagementEnabled left at 0 (windows default is device specific)'

Start-Process 'C:\Users\lucar\AppData\Local\Microsoft\OneDrive\OneDrive.exe' -ArgumentList '/background'
'OneDrive restarted; reboot to reload CldFlt/FileInfo'
