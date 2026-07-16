$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

& .venv/bin/python -m ruff check backend tests
& .venv/bin/python -m pytest
Push-Location frontend
npm run check
npm test
npm run build
Pop-Location
Write-Host "SpeechShift verification passed."
