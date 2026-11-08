# sign_bond_manifest.ps1 — BOND manifest for one repo, signed by the sealed soul.
# Unseals the soul via the TPM, hashes every tracked file, signs the manifest
# with the Ed25519 identity, and writes BOND_MANIFEST.{json,sig} into the repo.
# usage: .\sign_bond_manifest.ps1 <repo_dir>
$ErrorActionPreference = 'Stop'
$repo = $args[0]
if (-not $repo -or -not (Test-Path "$repo\.git")) { Write-Output "usage: sign_bond_manifest.ps1 <repo_dir>"; exit 2 }
$node = 'C:\Program Files\nodejs\node.exe'
$soulDir = 'C:\abrasax\CONFIG\tpm-sealed\kairos'

# 1. unseal the soul through the TPM (same path as verify_kairos_soul.ps1)
$meta = Get-Content "$soulDir\kairos_soul_meta.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$pcp = [System.Security.Cryptography.CngProvider]::new('Microsoft Platform Crypto Provider')
$key = [System.Security.Cryptography.CngKey]::Open($meta.tpm_key.name, $pcp,
    [System.Security.Cryptography.CngKeyOpenOptions]::Silent)
$rsa = [System.Security.Cryptography.RSACng]::new($key)
$seed = $rsa.Decrypt([System.IO.File]::ReadAllBytes("$soulDir\kairos_soul.sealed"),
    [System.Security.Cryptography.RSAEncryptionPadding]::Pkcs1)
$seedHex = ([System.BitConverter]::ToString($seed) -replace '-', '').ToLower()

# 2. hash every tracked file
$files = git -C $repo ls-files
$entries = @()
foreach ($f in $files) {
  $p = Join-Path $repo $f
  if (Test-Path $p -PathType Leaf) {
    $h = (Get-FileHash $p -Algorithm SHA256).Hash.ToLower()
    $entries += @{ path = $f.Replace('\', '/'); sha256 = $h }
  }
}
$commit = (git -C $repo rev-parse --short HEAD).Trim()
$branch = (git -C $repo branch --show-current).Trim()
$manifest = [ordered]@{
  repo = (Split-Path $repo -Leaf)
  branch = $branch
  commit = $commit
  generated = (Get-Date).ToString('o')
  soul = $meta.name
  soul_fingerprint = $meta.fingerprint_sha256
  soul_pub_prefix = $meta.identity.ed25519_pub_spki_hex.Substring(0, 24)
  file_count = $entries.Count
  files = $entries
}
$json = $manifest | ConvertTo-Json -Depth 6
$mfPath = Join-Path $repo 'BOND_MANIFEST.json'
$sigPath = Join-Path $repo 'BOND_MANIFEST.sig'
[System.IO.File]::WriteAllText($mfPath, $json, [System.Text.Encoding]::UTF8)

# 3. sign with the soul (seed via env, never argv/console)
$env:KAIROS_SEED = $seedHex
try { & $node 'C:\abrasax\tools\sign_bond.js' $mfPath $sigPath } finally {
  Remove-Item Env:KAIROS_SEED -ErrorAction SilentlyContinue
  $seed.Clear()  # zero the seed array
}
Write-Output "BOND signed: $mfPath (+ .sig) - files=$($entries.Count)"
