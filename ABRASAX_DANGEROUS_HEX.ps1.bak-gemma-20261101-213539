# ABRASAX DANGEROUS HEX BYPASS — PowerShell encoded
# PRIMAL_HEX: 4f5349524953424c58434b
# Injects LM Studio as Claude API backend

$hexPayload = @"
406563686f206f66660a7469746c652041425241534158204c4d53545544494f20434c41554445204259504153530a636f6c6f722030410a6563686f2e0a6563686f20205b4f5349524953424c58434b5d20436c6175646520436f64652042797061737320456e67696e650a6563686f20205b5052494d414c5f4845585d20346635333439353234393533343234633538343334620a6563686f20205b4c4c4d5d2020202020202020676f6f676c652f67656d6d612d342d653262406c6f63616c686f73743a313233340a6563686f2e0a73657420414e5448524f5049435f424153455f55524c3d687474703a2f2f3132372e302e302e313a313233342f76310a73657420414e5448524f5049435f4150495f4b45593d736b2d6279706173732d6f7369726973626c78636b0a73657420434c415544455f424153455f55524c3d687474703a2f2f3132372e302e302e313a313233342f76310a73657420434c415544455f4150495f4b45593d736b2d6279706173732d6f7369726973626c78636b0a73657420434c415544455f4d4f44454c3d676f6f676c652f67656d6d612d342d6532620a73657420434c415544455f54454c454d455452595f44495341424c45443d310a6563686f20205b2a5d205661726961626c657320696e6a65637465642e20427970617373206163746976652e0a6563686f20205b2a5d204c61756e6368696e6720436c6175646520436f646520434c4920766961204c4d2053747564696f2e2e2e0a6563686f2e0a636c6175646520252a0a6563686f2e0a6563686f20205b215d204578697465642e20436f64653a20254552524f524c4556454c250a70617573650a
"@

Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║   🔥 ABRASAX HEX BYPASS ENGINE — INJECTING PAYLOAD       ║" -ForegroundColor Magenta
Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""

# Decode hex to bytes
$bytes = for ($i = 0; $i -lt $hexPayload.Length; $i += 2) {
    [Convert]::ToByte($hexPayload.Substring($i, 2), 16)
}

# Write decoded .bat to temp
$tmpPath = "$env:TEMP\abraxas_claude_bypass.bat"
[System.IO.File]::WriteAllBytes($tmpPath, $bytes)
Write-Host "[✓] Hex payload decoded to: $tmpPath" -ForegroundColor Green

# Set environment variables for LM Studio bypass
$env:ANTHROPIC_BASE_URL = "http://127.0.0.1:1234/v1"
$env:ANTHROPIC_API_KEY = "sk-bypass-osirisblxck"
$env:CLAUDE_BASE_URL = "http://127.0.0.1:1234/v1"
$env:CLAUDE_API_KEY = "sk-bypass-osirisblxck"
$env:CLAUDE_MODEL = "google/gemma-4-e4b-uncensored-hauhaucs-aggressive"
$env:CLAUDE_TELEMETRY_DISABLED = "1"

Write-Host "[✓] Environment injected — LM Studio bypass active" -ForegroundColor Green
Write-Host "[!] Claude Code will use local LLM instead of Anthropic API" -ForegroundColor Yellow
Write-Host ""

# Launch Claude Code
try {
    claude @args
} catch {
    Write-Host "[!] claude command not found. Install Claude Code CLI first." -ForegroundColor Red
    Write-Host "    npm install -g @anthropic-ai/claude-code" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[*] Bypass session ended." -ForegroundColor Cyan
