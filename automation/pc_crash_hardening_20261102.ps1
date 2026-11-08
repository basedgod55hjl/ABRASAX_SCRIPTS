# ABRASAX crash hardening - 2026-11-02
# Backs up every value it changes, writes LOGS\crash\hardening-20261102.json, then changes it.
$ErrorActionPreference = 'Continue'
$root = 'C:\abrasax\LOGS\crash'
$bk   = Join-Path $root 'backup-20261102'
New-Item -ItemType Directory -Force -Path $bk | Out-Null
$log  = @()

function Reg-Export($key, $file) {
    $p = Join-Path $bk $file
    & reg.exe export $key $p /y 2>&1 | Out-Null
    return (Test-Path $p)
}

# ---------- 0. backup ----------
$exports = [ordered]@{
    'HKLM\SYSTEM\CurrentControlSet\Services\CldFlt'            = 'CldFlt.reg'
    'HKLM\SYSTEM\CurrentControlSet\Services\FileInfo'          = 'FileInfo.reg'
    'HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers'    = 'GraphicsDrivers-20261102.reg'
    'HKCU\Software\Microsoft\Windows\CurrentVersion\Run'       = 'HKCU-Run.reg'
    'HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power' = 'Power-Hiberboot.reg'
}
foreach ($k in $exports.Keys) {
    $ok = Reg-Export $k $exports[$k]
    $log += [pscustomobject]@{ step="backup:$k"; ok=$ok; detail=$exports[$k] }
}
$pf = (Get-CimInstance Win32_PageFileSetting | Select-Object -First 1)
$log += [pscustomobject]@{ step='before:pagefile'; ok=$true; detail=("init={0} max={1}" -f $pf.InitialSize,$pf.MaximumSize) }
$gd = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers'
$log += [pscustomobject]@{ step='before:tdr'; ok=$true; detail=("TdrDelay={0} TdrDdiDelay={1}" -f $gd.TdrDelay,$gd.TdrDdiDelay) }
foreach ($svc in 'CldFlt','FileInfo') {
    $s = Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Services\$svc" -ErrorAction SilentlyContinue
    $log += [pscustomobject]@{ step="before:$svc"; ok=$true; detail=("Start={0} Image={1}" -f $s.Start, (Get-Item "C:\Windows\System32\drivers\$($svc.ToLower()).sys" -ErrorAction SilentlyContinue).VersionInfo.FileVersion) }
}
$log += [pscustomobject]@{ step='before:onedrive'; ok=$true; detail=((Get-Process OneDrive -ErrorAction SilentlyContinue).Id -join ',') }

# ---------- 1. remove the cloud-files minifilter path (proven 0x1E in cldflt!HsmFltPreSetRenameInformation) ----------
# OneDrive holds no cloud-only placeholders on this box (verified: 0 files with RECALL_ON_DATA_ACCESS/OFFLINE),
# so the filter buys nothing and its rename pre-op is the crash site.
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\CldFlt' -Name Start -Value 4 -Type DWord
$log += [pscustomobject]@{ step='set:CldFlt.Start=4'; ok=((Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\CldFlt').Start -eq 4); detail='disabled, takes effect next boot' }

# stop the client so no more HSM renames are issued this session
Get-Process OneDrive -ErrorAction SilentlyContinue | ForEach-Object {
    $null = & 'C:\Users\lucar\AppData\Local\Microsoft\OneDrive\OneDrive.exe' /shutdown 2>&1
    Start-Sleep -Seconds 3
    if (-not $_.HasExited) { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
}
$log += [pscustomobject]@{ step='stop:OneDrive'; ok=(-not (Get-Process OneDrive -ErrorAction SilentlyContinue)); detail='client stopped' }

# autostart: Run value + the per-user startup task
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$runVal = (Get-ItemProperty $runKey -ErrorAction SilentlyContinue).OneDrive
if ($runVal) { Remove-ItemProperty $runKey -Name OneDrive -ErrorAction SilentlyContinue }
$log += [pscustomobject]@{ step='disable:OneDrive.Run'; ok=$true; detail="was: $runVal" }
$taskName = '\OneDrive Startup Task-S-1-5-21-2220358478-1661082693-2815614824-1001'
$t = Get-ScheduledTask -TaskName ($taskName.TrimStart('\')) -ErrorAction SilentlyContinue
if ($t) { Disable-ScheduledTask -TaskName $t.TaskName -TaskPath $t.TaskPath | Out-Null }
$log += [pscustomobject]@{ step='disable:OneDrive.StartupTask'; ok=([bool]$t); detail=$taskName }

# ---------- 2. FileInfo minifilter: 0x162 KERNEL_AUTO_BOOST_INVALID_LOCK_RELEASE in fileinfo!FIStreamQueryInfo ----------
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\FileInfo' -Name Start -Value 4 -Type DWord
$log += [pscustomobject]@{ step='set:FileInfo.Start=4'; ok=((Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\FileInfo').Start -eq 4); detail='disabled, takes effect next boot' }

# ---------- 3. TDR: a 60 s watchdog turns every GPU hang into a 60 s desktop freeze ----------
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers' -Name TdrDelay    -Value 10 -Type DWord
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers' -Name TdrDdiDelay -Value 10 -Type DWord
$gd2 = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers'
$log += [pscustomobject]@{ step='set:TdrDelay=10'; ok=($gd2.TdrDelay -eq 10 -and $gd2.TdrDdiDelay -eq 10); detail=("TdrDelay={0} TdrDdiDelay={1}" -f $gd2.TdrDelay,$gd2.TdrDdiDelay) }

# ---------- 4. USB: no selective suspend, no hub power-off, high performance ----------
& powercfg.exe /setacvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0 2>&1 | Out-Null
& powercfg.exe /setdcvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0 2>&1 | Out-Null
& powercfg.exe /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c 2>&1 | Out-Null   # High performance
& powercfg.exe /setactive SCHEME_CURRENT 2>&1 | Out-Null
$scheme = (& powercfg.exe /getactivescheme) -join ' '
$log += [pscustomobject]@{ step='power:usb-selective-suspend=off'; ok=$true; detail=$scheme }

$hubs = Get-CimInstance -ClassName MSPower_DeviceEnable -Namespace root\wmi -ErrorAction SilentlyContinue |
        Where-Object { $_.InstanceName -match 'USB\\ROOT_HUB|USB\\VID' }
$nOff = 0
foreach ($h in $hubs) {
    try { $h.Enable = $false; Set-WmiInstance -InputObject $h -Namespace root\wmi | Out-Null; $nOff++ } catch {}
}
$log += [pscustomobject]@{ step='power:usb-hubs-keep-awake'; ok=($nOff -gt 0); detail="$nOff devices set Enable=false" }

# ---------- 5. fast startup off: a hybrid boot after a hang reuses a dirty session ----------
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -Name HiberbootEnabled -Value 0 -Type DWord
$log += [pscustomobject]@{ step='set:HiberbootEnabled=0'; ok=((Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power').HiberbootEnabled -eq 0); detail='fast startup disabled, hibernate kept' }

$log | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $root 'hardening-20261102.json') -Encoding UTF8
$log | Format-Table -AutoSize | Out-String -Width 200
