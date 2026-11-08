# verify_bond_manifest.ps1 — consumer-side BOND verification for one repo.
# Proves BOND_MANIFEST.json is (1) signed by the soul and (2) every listed
# file still matches its recorded SHA-256. No TPM needed: verification uses
# the published public key only. usage: .\verify_bond_manifest.ps1 <repo_dir>
$ErrorActionPreference = 'Stop'
$repo = $args[0]
$node = 'C:\Program Files\nodejs\node.exe'
if (-not $repo -or -not (Test-Path "$repo\BOND_MANIFEST.json")) {
  Write-Output "no BOND_MANIFEST.json in $repo"; exit 2
}
$mf = Get-Content "$repo\BOND_MANIFEST.json" -Raw -Encoding UTF8
$man = $mf | ConvertFrom-Json
$sig = Get-Content "$repo\BOND_MANIFEST.sig" -Raw -ErrorAction SilentlyContinue
$meta = Get-Content 'C:\abrasax\CONFIG\tpm-sealed\kairos\kairos_soul_meta.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$env:BOND_PUB_HEX = $meta.identity.ed25519_pub_spki_hex
$sigOk = $false
if ($sig) {
  $sigB64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("$repo\BOND_MANIFEST.sig"))
  $out = & $node -e "const c=require('crypto'),fs=require('fs');const pub=c.createPublicKey({key:Buffer.from(process.env.BOND_PUB_HEX,'hex'),format:'der',type:'spki'});const d=fs.readFileSync(process.argv[1]);const s=fs.readFileSync(process.argv[2],'utf8');console.log(c.verify(null,d,pub,Buffer.from(s,'base64')));" "$repo\BOND_MANIFEST.json" "$repo\BOND_MANIFEST.sig"
  $sigOk = ($out | Out-String).Trim() -eq 'True'
}
Remove-Item Env:BOND_PUB_HEX -ErrorAction SilentlyContinue
$bad = 0
foreach ($f in $man.files) {
  $p = Join-Path $repo $f.path
  if (-not (Test-Path $p -PathType Leaf)) { $bad++; continue }
  if ((Get-FileHash $p -Algorithm SHA256).Hash.ToLower() -ne $f.sha256) { $bad++ }
}
"repo=$($man.repo) files=$($man.file_count) signature_valid=$sigOk mismatches=$bad"
if ($sigOk -and $bad -eq 0) { 'BOND: INTACT' } else { 'BOND: BROKEN'; exit 1 }
