$launcher = Join-Path $PSScriptRoot '..\start-yino-demo.cmd'

$forbiddenEnvReaderPatterns = @(
    '(?im)^\s*@?(?:type|more|findstr)(?:\.exe)?\b[^\r\n]*\.env(?:\.local)?\b',
    '(?im)^\s*@?for\s+/f\b',
    '(?im)^\s*@?(?:powershell|pwsh)(?:\.exe)?\b[^\r\n]*\bGet-Content\b',
    '(?im)^\s*@?set\s+/p\b[^\r\n]*<[^\r\n]*\.env(?:\.local)?\b'
)

function Test-ContainsForbiddenEnvReader {
    param([string]$Source)

    foreach ($pattern in $forbiddenEnvReaderPatterns) {
        if ($Source -match $pattern) {
            return $true
        }
    }
    return $false
}

function Assert-PreflightTokenBeforeFirstStart {
    param(
        [string]$Source,
        [string]$Token
    )

    $firstStart = $Source.IndexOf('start "Yino Demo 1 - LiveKit"')
    if ($firstStart -le -1) {
        throw 'first service launch is missing'
    }
    $tokenIndex = $Source.IndexOf($Token)
    if ($tokenIndex -le -1) {
        throw "preflight token is missing: $Token"
    }
    if ($tokenIndex -ge $firstStart) {
        throw "preflight token appears after launch: $Token"
    }
}

Describe 'start-yino-demo.cmd' {
    BeforeAll {
        $content = Get-Content -Raw -Encoding UTF8 $launcher
    }

    It 'resolves its root from its own absolute script directory' {
        $content | Should Match '%~dp0\.\.'
        $content | Should Match '%%~fI'
    }

    It 'checks every dependency and local environment file before any launch' {
        $firstStart = $content.IndexOf('start "Yino Demo 1 - LiveKit"')
        $firstStart | Should BeGreaterThan 0

        $preflightTokens = @(
            'where.exe livekit-server',
            'platform-api\.venv\Scripts\python.exe',
            'voice-agent\.venv\Scripts\python.exe',
            'where.exe pnpm',
            'platform-api\.env.local',
            'voice-agent\.env.local',
            'front\.env.local',
            'if "%YINO_DEMO_PREFLIGHT_FAILED%"=="1"'
        )

        $preflightTokens | ForEach-Object {
            $tokenIndex = $content.IndexOf($_)
            $tokenIndex | Should BeGreaterThan -1
            $tokenIndex | Should BeLessThan $firstStart
        }

        $missingTokenVariant = $content.Replace(
            'where.exe pnpm >nul 2>nul',
            'REM pnpm preflight removed'
        )
        {
            Assert-PreflightTokenBeforeFirstStart `
                -Source $missingTokenVariant `
                -Token 'where.exe pnpm'
        } | Should Throw 'preflight token is missing: where.exe pnpm'
    }

    It 'starts exactly four titled windows in the required order' {
        $matches = [regex]::Matches($content, '(?m)^start "Yino Demo [1-4] - ')
        $matches.Count | Should Be 4

        $livekit = $content.IndexOf('start "Yino Demo 1 - LiveKit"')
        $platform = $content.IndexOf('start "Yino Demo 2 - Platform API"')
        $voice = $content.IndexOf('start "Yino Demo 3 - Voice Agent"')
        $front = $content.IndexOf('start "Yino Demo 4 - Frontend"')
        $platform | Should BeGreaterThan $livekit
        $voice | Should BeGreaterThan $platform
        $front | Should BeGreaterThan $voice
        $content | Should Not Match 'cd /d "%YINO_DEMO_ROOT%'
        ([regex]::Matches($content, 'pushd "%YINO_DEMO_ROOT%').Count) | Should Be 4
    }

    It 'falls back to Corepack when pnpm is not installed as a standalone command' {
        $content | Should Match 'where\.exe corepack'
        $content | Should Match 'set "YINO_PNPM_CMD=corepack pnpm"'
        $content | Should Match ([regex]::Escape('%YINO_PNPM_CMD% run dev -- --port 3003'))
    }

    It 'uses pushd so every service can start directly from a UNC share' {
        $content | Should Match ([regex]::Escape('pushd "%YINO_DEMO_ROOT%"'))
        $content | Should Match ([regex]::Escape('pushd "%YINO_DEMO_ROOT%\platform-api"'))
        $content | Should Match ([regex]::Escape('pushd "%YINO_DEMO_ROOT%\voice-agent"'))
        $content | Should Match ([regex]::Escape('pushd "%YINO_DEMO_ROOT%\front"'))
    }

    It 'does not print or inspect environment file contents' {
        (Test-ContainsForbiddenEnvReader -Source $content) | Should Be $false
        $content | Should Not Match '(?i)DASHSCOPE_API_KEY|LIVEKIT_API_SECRET|OPENAI_API_KEY'

        @(
            'type "%YINO_DEMO_ROOT%\voice-agent\.env.local"',
            '@type "%YINO_DEMO_ROOT%\voice-agent\.env.local"',
            'more "%YINO_DEMO_ROOT%\voice-agent\.env.local"',
            '@more "%YINO_DEMO_ROOT%\voice-agent\.env.local"',
            'findstr ".*" "%YINO_DEMO_ROOT%\voice-agent\.env.local"',
            '@findstr ".*" "%YINO_DEMO_ROOT%\voice-agent\.env.local"',
            'for /f "usebackq delims=" %%V in ("%YINO_DEMO_ROOT%\voice-agent\.env.local") do echo %%V',
            '@for /f "usebackq delims=" %%V in ("%YINO_DEMO_ROOT%\voice-agent\.env.local") do echo %%V',
            'powershell.exe -Command "Get-Content .env.local"',
            '@powershell.exe -Command "Get-Content .env.local"',
            'pwsh -Command "Get-Content .env.local"',
            '@pwsh -Command "Get-Content .env.local"',
            'set /p VALUE=<"%YINO_DEMO_ROOT%\voice-agent\.env.local"',
            '@set /p VALUE=<"%YINO_DEMO_ROOT%\voice-agent\.env.local"'
        ) | ForEach-Object {
            $unsafeVariant = $content + [Environment]::NewLine + $_
            (Test-ContainsForbiddenEnvReader -Source $unsafeVariant) | Should Be $true
        }

        $safeVariant = @'
if not exist "%YINO_DEMO_ROOT%\voice-agent\.env.local" (
  echo [MISSING] voice-agent .env.local.
)
'@
        (Test-ContainsForbiddenEnvReader -Source $safeVariant) | Should Be $false
    }

    It 'returns nonzero without launching when prerequisites are absent' {
        $isolatedRoot = Join-Path $TestDrive 'YinoVoicePlatform'
        $isolatedScripts = Join-Path $isolatedRoot 'scripts'
        New-Item -ItemType Directory -Path $isolatedScripts | Out-Null
        $isolatedLauncher = Join-Path $isolatedScripts 'start-yino-demo.cmd'
        Copy-Item $launcher $isolatedLauncher

        $originalPath = $env:PATH
        try {
            $env:PATH = Join-Path $env:SystemRoot 'System32'
            $output = & (Join-Path $env:SystemRoot 'System32\cmd.exe') /d /c $isolatedLauncher 2>&1

            $LASTEXITCODE | Should Be 1
            [string]::Join("`n", $output) | Should Match 'No service windows were started'
        }
        finally {
            $env:PATH = $originalPath
        }
    }
}
