@echo off
setlocal EnableExtensions DisableDelayedExpansion

for %%I in ("%~dp0..") do set "YINO_DEMO_ROOT=%%~fI"
set "YINO_DEMO_PREFLIGHT_FAILED=0"
set "YINO_PNPM_CMD="

echo [Yino Demo] Checking local prerequisites...

where.exe livekit-server >nul 2>nul
if errorlevel 1 (
  echo [MISSING] livekit-server is not available on PATH.
  set "YINO_DEMO_PREFLIGHT_FAILED=1"
) else (
  echo [OK] livekit-server command found.
)

if not exist "%YINO_DEMO_ROOT%\platform-api\.venv\Scripts\python.exe" (
  echo [MISSING] Platform API virtual environment.
  set "YINO_DEMO_PREFLIGHT_FAILED=1"
) else (
  echo [OK] Platform API Python found.
)

if not exist "%YINO_DEMO_ROOT%\voice-agent\.venv\Scripts\python.exe" (
  echo [MISSING] Voice agent virtual environment.
  set "YINO_DEMO_PREFLIGHT_FAILED=1"
) else (
  echo [OK] Voice agent Python found.
)

where.exe pnpm >nul 2>nul
if errorlevel 1 (
  where.exe corepack >nul 2>nul
  if errorlevel 1 (
    echo [MISSING] Neither pnpm nor Corepack is available on PATH.
    set "YINO_DEMO_PREFLIGHT_FAILED=1"
  ) else (
    set "YINO_PNPM_CMD=corepack pnpm"
    echo [OK] Corepack found; it will run pnpm.
  )
) else (
  set "YINO_PNPM_CMD=pnpm"
  echo [OK] pnpm command found.
)

if not exist "%YINO_DEMO_ROOT%\platform-api\.env.local" (
  echo [MISSING] platform-api .env.local.
  set "YINO_DEMO_PREFLIGHT_FAILED=1"
) else (
  echo [OK] Platform API local environment file found.
)

if not exist "%YINO_DEMO_ROOT%\voice-agent\.env.local" (
  echo [MISSING] voice-agent .env.local.
  set "YINO_DEMO_PREFLIGHT_FAILED=1"
) else (
  echo [OK] Voice agent local environment file found.
)

if not exist "%YINO_DEMO_ROOT%\front\.env.local" (
  echo [MISSING] front .env.local.
  set "YINO_DEMO_PREFLIGHT_FAILED=1"
) else (
  echo [OK] Frontend local environment file found.
)

if "%YINO_DEMO_PREFLIGHT_FAILED%"=="1" (
  echo [Yino Demo] Preflight failed. No service windows were started.
  exit /b 1
)

echo [Yino Demo] Preflight passed. Starting four service windows...
start "Yino Demo 1 - LiveKit" cmd.exe /k "pushd "%YINO_DEMO_ROOT%" && powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\start-livekit-dev.ps1""
start "Yino Demo 2 - Platform API" cmd.exe /k "pushd "%YINO_DEMO_ROOT%\platform-api" && ".venv\Scripts\python.exe" -m uvicorn yino_platform_api.app:app --reload --port 8000"
start "Yino Demo 3 - Voice Agent" cmd.exe /k "pushd "%YINO_DEMO_ROOT%\voice-agent" && ".venv\Scripts\python.exe" -m yino_voice_agent.server dev"
start "Yino Demo 4 - Frontend" cmd.exe /k "pushd "%YINO_DEMO_ROOT%\front" && %YINO_PNPM_CMD% run dev -- --port 3003"

echo [Yino Demo] Startup commands were dispatched. Open http://localhost:3003 after all windows are ready.
exit /b 0
