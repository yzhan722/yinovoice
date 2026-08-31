$ErrorActionPreference = "Stop"
$expected = "SEND 867542127@qq.com"
$packageRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Write-Host "From: yinoagent@gmail.com"
Write-Host "To:   867542127@qq.com"
$confirmation = Read-Host "Type '$expected' to send one fictional report"
if ($confirmation -cne $expected) {
  Write-Output "email_test_not_confirmed"
  exit 1
}

$securePassword = $null
$passwordPtr = [IntPtr]::Zero
try {
  $securePassword = Read-Host "Gmail application password" -AsSecureString
  $passwordPtr =
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
  $env:REAL_EMAIL_TEST_CONFIRM = $expected
  $env:GMAIL_TEST_APP_PASSWORD =
    [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPtr)

  $previousErrorActionPreference = $ErrorActionPreference
  try {
    $ErrorActionPreference = "Continue"
    $global:LASTEXITCODE = $null
    $childOutput = @(npm --silent --prefix $packageRoot run test:email 2>&1)
    $childExitCode = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }
  if ($null -eq $childExitCode) {
    throw "email_test_launcher_failed"
  }
  if ($childExitCode -ne 0) {
    Write-Output "email_test_send_failed"
    exit $childExitCode
  }
  if (
    $childOutput.Count -ne 1 -or
    [string]$childOutput[0] -cne '{"status":"sent"}'
  ) {
    Write-Output "email_test_send_failed"
    exit 1
  }
  Write-Output '{"status":"sent"}'
} catch {
  Write-Output "email_test_send_failed"
  exit 1
} finally {
  Remove-Item Env:REAL_EMAIL_TEST_CONFIRM -ErrorAction SilentlyContinue
  Remove-Item Env:GMAIL_TEST_APP_PASSWORD -ErrorAction SilentlyContinue
  if ($passwordPtr -ne [IntPtr]::Zero) {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPtr)
  }
  $securePassword = $null
}
