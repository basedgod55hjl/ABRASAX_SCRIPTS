$enginePath = "C:\Users\BASEDGOD\Desktop\ABRASAX AGI\abrasax_rs\target\release\abrasax.exe"
$workDir = "C:\Users\BASEDGOD\Desktop\ABRASAX AGI\abrasax_rs"

# Launch system monitor - visible elevated window
Start-Process -FilePath powershell.exe -Verb RunAs -ArgumentList "-NoExit", "-Command", "Set-Location '$workDir'; Write-Host 'ABRASAX v4.1.0 - SYSTEM MONITOR' -ForegroundColor Green; & '$enginePath' monitor" -WindowStyle Normal

# Launch duckboard - visible elevated window
Start-Process -FilePath powershell.exe -Verb RunAs -ArgumentList "-NoExit", "-Command", "Set-Location '$workDir'; Write-Host 'ABRASAX v4.1.0 - DUCKBOARD DASHBOARD' -ForegroundColor Cyan; & '$enginePath' duckboard" -WindowStyle Normal

Write-Host "ABRASAX AGI windows launched - check your desktop for new PowerShell windows" -ForegroundColor Green
