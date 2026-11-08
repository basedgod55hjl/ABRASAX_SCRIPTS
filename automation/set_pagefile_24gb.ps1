# Fixed 24 GB pagefile on C: so the next hang can write a kernel dump.
# Reason: RAM is 16 GB, CrashDumpEnabled=7 (automatic), the system-managed
# pagefile was 2.9 GB, and volmgr logged event 161 "Dump file creation failed
# due to error during dump creation" on 2026-11-01 12:08:59 -- i.e. at least one
# crash produced no dump. Four of five hangs in the last 25 hours have no dump
# for exactly this reason: without one there is no stack to attribute them to.
$cs = Get-CimInstance Win32_ComputerSystem
if ($cs.AutomaticManagedPagefile) {
    Set-CimInstance -InputObject $cs -Property @{ AutomaticManagedPagefile = $false }
}
$existing = Get-CimInstance Win32_PageFileSetting | Where-Object { $_.Name -like 'C:*' }
if ($existing) {
    $existing | Set-CimInstance -Property @{ InitialSize = 24576; MaximumSize = 24576 }
} else {
    New-CimInstance -ClassName Win32_PageFileSetting -Property @{
        Name = 'C:\pagefile.sys'; InitialSize = 24576; MaximumSize = 24576
    } | Out-Null
}
'--- pagefile setting ---'
Get-CimInstance Win32_PageFileSetting | Format-List Name, InitialSize, MaximumSize
'--- automatic managed ---'
(Get-CimInstance Win32_ComputerSystem).AutomaticManagedPagefile
'--- crash control ---'
Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\CrashControl' |
    Format-List CrashDumpEnabled, DumpFile, MinidumpDir, AutoReboot, Overwrite
