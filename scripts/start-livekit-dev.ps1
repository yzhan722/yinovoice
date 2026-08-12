$ErrorActionPreference = 'Stop'

$server = Get-Command livekit-server -ErrorAction SilentlyContinue
if (-not $server) {
    throw 'livekit-server is not installed. Download the Windows release from https://github.com/livekit/livekit/releases'
}

& $server.Source --dev --bind 0.0.0.0
