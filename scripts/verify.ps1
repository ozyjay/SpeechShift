$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

& .venv/bin/python -m ruff check backend tests scripts/model_probe.py scripts/smoke_mock.py
& .venv/bin/python -m pytest
Push-Location frontend
npm run check
npm test
npm run build
npm run test:browser
Pop-Location
Write-Host "SpeechShift verification passed."
