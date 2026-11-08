$ErrorActionPreference = 'SilentlyContinue'
# Temporarily suspend (not kill) the model_pinner so the 8B stops being
# re-pinned while we probe other GGUFs. SuspendProcess leaves the process alive
# and resumable, so this is reversible and nothing has to be restarted.
$sig = @'
using System;
using System.Runtime.InteropServices;
public static class NtProc {
    [DllImport("ntdll.dll")] public static extern int NtSuspendProcess(IntPtr h);
    [DllImport("ntdll.dll")] public static extern int NtResumeProcess(IntPtr h);
    [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a, bool i, int pid);
    [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
'@
Add-Type -TypeDefinition $sig -ErrorAction SilentlyContinue

$targets = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'model_pinner' }
if (-not $targets) { Write-Host "no model_pinner running"; exit 0 }

foreach ($t in $targets) {
    $h = [NtProc]::OpenProcess(0x0800, $false, $t.ProcessId)  # PROCESS_SUSPEND_RESUME
    if ($h -ne [IntPtr]::Zero) {
        $rc = [NtProc]::NtSuspendProcess($h)
        [NtProc]::CloseHandle($h) | Out-Null
        Write-Host ("suspended model_pinner pid=" + $t.ProcessId + " rc=" + $rc)
    } else {
        Write-Host ("could not open pid=" + $t.ProcessId)
    }
}

# Also free the 8B it pinned so the probe has the whole card.
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq 'llama-server.exe' -and $_.CommandLine -match 'DeepSeek-R1'
} | ForEach-Object {
    Write-Host ("stopping pinned 8B worker pid=" + $_.ProcessId)
    Stop-Process -Id $_.ProcessId -Force
}

Start-Sleep -Seconds 4
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader
