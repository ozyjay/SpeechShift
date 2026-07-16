$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if (-not (Test-Path ".venv")) {
    python3 -m venv .venv
}

& .venv/bin/python -m pip install --upgrade pip
& .venv/bin/python -m pip install -e ".[dev]"
Push-Location frontend
npm install
npm run build
Pop-Location

Write-Host "SpeechShift setup complete."
