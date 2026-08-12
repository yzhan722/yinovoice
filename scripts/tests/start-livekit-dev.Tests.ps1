$launcher = Join-Path $PSScriptRoot '..\start-livekit-dev.ps1'

Describe 'start-livekit-dev.ps1' {
    It 'fails with the official release URL when livekit-server is unavailable' {
        $originalPath = $env:PATH

        try {
            $env:PATH = $TestDrive

            { & $launcher } | Should Throw 'livekit-server is not installed. Download the Windows release from https://github.com/livekit/livekit/releases'
        }
        finally {
            $env:PATH = $originalPath
        }
    }

    It 'starts the discovered server in dev mode on every local interface' {
        $originalPath = $env:PATH
        $originalArgsPath = $env:YINO_LIVEKIT_TEST_ARGS
        $argsPath = Join-Path $TestDrive 'arguments.txt'
        $shimPath = Join-Path $TestDrive 'livekit-server.ps1'

        @'
$args | Set-Content -Encoding UTF8 $env:YINO_LIVEKIT_TEST_ARGS
'@ | Set-Content -Encoding UTF8 $shimPath

        try {
            $env:PATH = "$TestDrive;$originalPath"
            $env:YINO_LIVEKIT_TEST_ARGS = $argsPath

            & $launcher

            [string]::Join('|', (Get-Content -Encoding UTF8 $argsPath)) | Should Be '--dev|--bind|0.0.0.0'
        }
        finally {
            $env:PATH = $originalPath
            $env:YINO_LIVEKIT_TEST_ARGS = $originalArgsPath
        }
    }
}
