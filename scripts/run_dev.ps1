$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

& $PSScriptRoot/check_ports.ps1 -Port 3800
if (-not (Test-Path "frontend/dist/index.html")) {
    throw "The frontend has not been built. Run scripts/setup.ps1 first."
}

$env:DEMO_MODE = "development"
$env:SPEECH_PROVIDER = "replay"
& .venv/bin/python -m speechshift
