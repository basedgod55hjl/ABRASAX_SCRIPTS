$enginePath = "C:\Users\BASEDGOD\Desktop\ABRASAX AGI\abrasax_rs\target\release\abrasax.exe"
$workDir = "C:\Users\BASEDGOD\Desktop\ABRASAX AGI\abrasax_rs"

$cmd = "-NoExit -Command `$host.UI.RawUI.WindowTitle = 'ABRASAX ALL ENGINES'; Set-Location '$workDir'; Write-Host 'ABRASAX v4.1.0 - ALL ENGINES' -ForegroundColor Magenta; & '$enginePath' all"

Start-Process -FilePath powershell.exe -Verb RunAs -ArgumentList $cmd -WindowStyle Normal

Write-Host "ABRASAX ALL ENGINES launching in new elevated window..." -ForegroundColor Green
