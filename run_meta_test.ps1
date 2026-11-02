$env:RUST_BACKTRACE="full"
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "C:\Users\BASEDGOD\Desktop\ABRASAX\abrasax_rs\target\release\abrasax.exe"
$psi.Arguments = "meta"
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true

$p = [System.Diagnostics.Process]::Start($psi)
$exited = $p.WaitForExit(120000)

if ($exited) {
    $out = $p.StandardOutput.ReadToEnd()
    $err = $p.StandardError.ReadToEnd()
    Write-Output "EXIT_CODE: $($p.ExitCode)"
    Write-Output "=== STDOUT ==="
    Write-Output $out
    Write-Output "=== STDERR ==="
    Write-Output $err
} else {
    $p.Kill()
    Write-Output "TIMEOUT (120s)"
}
Write-Output "DONE"
