$ErrorActionPreference = "Stop"
$expected = "SEND 867542127@qq.com"
$packageRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$defaultCallId = "019ffebb-795d-711f-ae46-1674252cc39c"
$callId = $defaultCallId
if (-not [string]::IsNullOrWhiteSpace($env:TRIAL_CALL_ID)) {
  $callId = $env:TRIAL_CALL_ID
}
$vapiKeyFile = "C:\Users\yino\vapi api.txt"
if (-not [string]::IsNullOrWhiteSpace($env:TRIAL_VAPI_KEY_FILE)) {
  $vapiKeyFile = $env:TRIAL_VAPI_KEY_FILE
}
$deepseekKeyFile = "C:\Users\Public\ds_api.log"
if (-not [string]::IsNullOrWhiteSpace($env:TRIAL_DEEPSEEK_KEY_FILE)) {
  $deepseekKeyFile = $env:TRIAL_DEEPSEEK_KEY_FILE
}

Write-Host "From: yinoagent@gmail.com"
Write-Host "To:   867542127@qq.com"
Write-Host "Subject: Call Report for <customer_name> <create_time>"
Write-Host "Subject: [质量分析] Luca AI 评分: <score>/10 - <customer_name>"
Write-Host "Profile: lucaplus"
Write-Host "Call:  $callId"

if (-not (Test-Path -LiteralPath $deepseekKeyFile)) {
  Write-Output "trial_credentials_missing"
  exit 1
}
if (-not (Test-Path -LiteralPath $vapiKeyFile)) {
  Write-Output "trial_credentials_missing"
  exit 1
}

$confirmation = Read-Host "Type '$expected' to send the LucaPlus trial reports"
if ($confirmation -cne $expected) {
  Write-Output "trial_not_confirmed"
  exit 1
}

$vapiKey = ([string](Get-Content -LiteralPath $vapiKeyFile -Raw)).Trim()
$deepseekKey = ([string](Get-Content -LiteralPath $deepseekKeyFile -Raw)).Trim()
if (
  [string]::IsNullOrWhiteSpace($vapiKey) -or
  [string]::IsNullOrWhiteSpace($deepseekKey)
) {
  Write-Output "trial_credentials_missing"
  exit 1
}

$securePassword = $null
$passwordPtr = [IntPtr]::Zero
$previousAiProvider = $env:AI_PROVIDER
$previousVapiKey = $env:VAPI_API_KEY
$previousDeepseekKey = $env:DEEPSEEK_API_KEY
try {
  $securePassword = Read-Host "Gmail application password" -AsSecureString
  $passwordPtr =
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
  $env:REAL_EMAIL_TEST_CONFIRM = $expected
  $env:GMAIL_TEST_APP_PASSWORD =
    [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPtr)
  $env:VAPI_API_KEY = $vapiKey
  $env:DEEPSEEK_API_KEY = $deepseekKey
  $env:AI_PROVIDER = "deepseek"

  $previousErrorActionPreference = $ErrorActionPreference
  try {
    $ErrorActionPreference = "Continue"
    $global:LASTEXITCODE = $null
    $childOutput = @(npm --silent --prefix $packageRoot run test:trial-email 2>&1)
    $childExitCode = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }
  if ($null -eq $childExitCode) {
    throw "trial_launcher_failed"
  }
  if ($childExitCode -ne 0) {
    Write-Output "trial_send_failed"
    exit $childExitCode
  }
  if (
    $childOutput.Count -ne 1 -or
    [string]$childOutput[0] -cne '{"status":"sent"}'
  ) {
    Write-Output "trial_send_failed"
    exit 1
  }
  Write-Output '{"status":"sent"}'
} catch {
  Write-Output "trial_send_failed"
  exit 1
} finally {
  Remove-Item Env:REAL_EMAIL_TEST_CONFIRM -ErrorAction SilentlyContinue
  Remove-Item Env:GMAIL_TEST_APP_PASSWORD -ErrorAction SilentlyContinue
  if ([string]::IsNullOrEmpty($previousVapiKey)) {
    Remove-Item Env:VAPI_API_KEY -ErrorAction SilentlyContinue
  } else {
    $env:VAPI_API_KEY = $previousVapiKey
  }
  if ([string]::IsNullOrEmpty($previousDeepseekKey)) {
    Remove-Item Env:DEEPSEEK_API_KEY -ErrorAction SilentlyContinue
  } else {
    $env:DEEPSEEK_API_KEY = $previousDeepseekKey
  }
  if ([string]::IsNullOrEmpty($previousAiProvider)) {
    Remove-Item Env:AI_PROVIDER -ErrorAction SilentlyContinue
  } else {
    $env:AI_PROVIDER = $previousAiProvider
  }
  if ($passwordPtr -ne [IntPtr]::Zero) {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPtr)
  }
  $securePassword = $null
  $vapiKey = $null
  $deepseekKey = $null
}
