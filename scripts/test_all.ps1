#Requires -Version 5.1
param(
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
$env:Path = "$env:LOCALAPPDATA\pnpm-bin;$env:LOCALAPPDATA\npm-global;$env:Path"

function Invoke-Step([string]$Name, [scriptblock]$Action) {
  Write-Host "`n=== $Name ==="
  & $Action
  if ($LASTEXITCODE -ne 0) {
    throw "$Name failed with exit $LASTEXITCODE"
  }
}

$apiPython = Join-Path $RepoRoot "apps\control-plane\api\.venv\Scripts\python.exe"
$voicePython = Join-Path $RepoRoot "apps\runtime\voice-agent\.venv\Scripts\python.exe"
if (-not (Test-Path $apiPython)) { throw "API venv missing: $apiPython" }
if (-not (Test-Path $voicePython)) { throw "voice-agent venv missing: $voicePython" }

Set-Location $RepoRoot

Invoke-Step "ended-call contract" {
  python (Join-Path $RepoRoot "packages\contracts\ended-call\validate.py")
}

Invoke-Step "API pytest" {
  Set-Location (Join-Path $RepoRoot "apps\control-plane\api")
  & $apiPython -m pytest -q
}

Invoke-Step "voice-agent pytest" {
  Set-Location (Join-Path $RepoRoot "apps\runtime\voice-agent")
  & $voicePython -m pytest -q
}

Invoke-Step "web test" {
  Set-Location (Join-Path $RepoRoot "apps\control-plane\web")
  pnpm test
}

Invoke-Step "web typecheck" {
  Set-Location (Join-Path $RepoRoot "apps\control-plane\web")
  pnpm typecheck
}

Invoke-Step "web build" {
  Set-Location (Join-Path $RepoRoot "apps\control-plane\web")
  pnpm build
}

Invoke-Step "call-insights test" {
  Set-Location (Join-Path $RepoRoot "apps\call-insights")
  npm test
}

Invoke-Step "call-insights typecheck" {
  Set-Location (Join-Path $RepoRoot "apps\call-insights")
  npm run typecheck
}

Write-Host "`nAll local verification steps passed."
exit 0
